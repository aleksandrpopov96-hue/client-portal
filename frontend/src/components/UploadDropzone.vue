<template>
  <div>
    <div
      class="dropzone pa-6 d-flex flex-column align-center justify-center rounded-xl"
      :class="{ 'dropzone-active': dragging, 'dropzone-empty': queue.length === 0 }"
      @dragenter.prevent="dragging = true"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
      @click="input?.click()"
    >
      <v-icon size="48" color="primary" class="mb-2">mdi-cloud-upload-outline</v-icon>
      <p class="text-body-1 font-weight-medium mb-1">Drag &amp; drop files here</p>
      <p class="text-caption text-medium-emphasis mb-0">
        or click to browse
        <template v-if="maxUploadMb"> &middot; max {{ maxUploadMb }} MB per file</template>
        <template v-if="allowedExtensions && allowedExtensions !== 'all'"> &middot; allowed: {{ allowedExtensions.join(', ') }}</template>
      </p>
      <input
        ref="input"
        type="file"
        multiple
        class="d-none"
        @change="onInputChange"
      />
    </div>

    <v-list v-if="queue.length" class="mt-3 rounded-xl elevation-1" density="comfortable">
      <v-list-item v-for="item in queue" :key="item.id" :class="{ 'opacity-50': item.done }">
        <template #prepend>
          <v-icon class="mr-3">{{ itemIcon(item.name) }}</v-icon>
        </template>

        <template #title>
          <div class="d-flex align-center">
            <span class="text-truncate">{{ item.name }}</span>
            <v-spacer />
            <span class="text-caption text-medium-emphasis mr-2">{{ item.statusLabel }}</span>
            <v-btn
              v-if="item.status === 'error'"
              size="x-small"
              variant="tonal"
              color="error"
              @click="retry(item)"
            >
              Retry
            </v-btn>
            <v-btn
              v-if="!item.done && inFlightIds.has(item.id)"
              size="x-small"
              variant="text"
              icon="mdi-close"
              @click="cancel(item)"
            />
          </div>
        </template>

        <template #subtitle>
          <v-progress-linear
            v-model="item.progress"
            :color="item.status === 'error' ? 'error' : item.status === 'done' ? 'success' : 'primary'"
            height="6"
            rounded
            class="mt-1"
          />
          <p v-if="item.message" class="text-caption text-error mt-1 mb-0">{{ item.message }}</p>
        </template>
      </v-list-item>
    </v-list>
  </div>
</template>

<script setup>
import { ref, nextTick, onBeforeUnmount } from 'vue'
import { uploadFile } from '../api/client'
import { iconFor } from '../utils/preview'
import { humanSize } from '../utils/format'

const props = defineProps({
  endpoint: { type: String, required: true },
  uploadPath: { type: String, default: '' },
  chunkMb: { type: Number, default: 20 },
  maxUploadMb: { type: Number, default: null },
  allowedExtensions: { type: [Array, String], default: () => [] },
  maxConcurrent: { type: Number, default: 2 },
})

const emit = defineEmits(['uploaded', 'error', 'complete'])

const input = ref(null)
const dragging = ref(false)
const queue = ref([])
const inFlightIds = ref(new Set())
let idCounter = 0
let running = 0

function allowedList() {
  const raw = props.allowedExtensions || []
  if (typeof raw === 'string' && raw.trim()) return raw.split(',').map((e) => e.trim().toLowerCase())
  if (Array.isArray(raw)) return raw.map((e) => String(e).toLowerCase())
  return []
}

function extOf(name) {
  const i = name.lastIndexOf('.')
  return i > 0 ? name.slice(i + 1).toLowerCase() : ''
}

function validate(name, size) {
  const allowed = allowedList()
  if (allowed.length && !allowed.includes(extOf(name))) {
    return `Extension .${extOf(name)} is not allowed`
  }
  if (props.maxUploadMb && size > props.maxUploadMb * 1024 * 1024) {
    return `Exceeds ${props.maxUploadMb} MB limit`
  }
  return null
}

function addFiles(files) {
  for (const file of files) {
    if (!file || !file.name) continue
    const err = validate(file.name, file.size)
    if (err) {
      queue.value.push({
        id: ++idCounter,
        name: file.name,
        size: file.size,
        file,
        progress: 0,
        status: 'error',
        statusLabel: 'Error',
        message: err,
        done: false,
      })
      emit('error', err)
      continue
    }
    queue.value.push({
      id: ++idCounter,
      name: file.name,
      size: file.size,
      file,
      progress: 0,
      status: 'waiting',
      statusLabel: humanSize(file.size),
      message: '',
      done: false,
    })
    pump()
  }
}

function onDrop(e) {
  dragging.value = false
  if (e.dataTransfer?.files) addFiles(e.dataTransfer.files)
}

function onInputChange() {
  if (input.value?.files) addFiles(input.value.files)
  if (input.value) input.value.value = ''
}

function pump() {
  while (running < props.maxConcurrent) {
    const item = queue.value.find((q) => q.status === 'waiting' && !inFlightIds.value.has(q.id))
    if (!item) break
    running++
    inFlightIds.value.add(item.id)
    uploadItem(item)
  }
}

async function uploadItem(item) {
  item.status = 'uploading'
  item.statusLabel = 'Uploading…'
  const chunkSize = Math.max(1, props.chunkMb || 20) * 1024 * 1024
  const total = Math.max(1, Math.ceil(item.file.size / chunkSize))
  let sessionName = item.name
  try {
    for (let i = 0; i < total; i++) {
      const start = i * chunkSize
      const end = Math.min(start + chunkSize, item.file.size)
      const slice = item.file.slice(start, end, item.file.type)
      const form = new FormData()
      form.append('path', props.uploadPath)
      form.append('file', slice, item.name)
      form.append('chunk_index', String(i))
      form.append('chunk_total', String(total))
      if (i > 0) form.append('basename', sessionName)
      const res = await uploadFile(props.endpoint, form, {
        onProgress: (loaded) => {
          item.progress = Math.round(((i * chunkSize + loaded) / item.file.size) * 100)
        },
      })
      if (res.name) sessionName = res.name
      if (res.done) break
    }
    item.progress = 100
    item.status = 'done'
    item.statusLabel = 'Uploaded'
    item.done = true
    emit('uploaded', { name: item.name, size: item.size })
  } catch (err) {
    item.status = 'error'
    item.statusLabel = 'Failed'
    item.message = err.error || err.message || 'Upload failed'
    emit('error', item.message)
  } finally {
    running--
    inFlightIds.value.delete(item.id)
    if (queue.value.every((q) => q.done || q.status === 'error')) {
      emit('complete')
    }
    pump()
  }
}

function retry(item) {
  item.progress = 0
  item.status = 'waiting'
  item.statusLabel = humanSize(item.size)
  item.message = ''
  pump()
}

function cancel(item) {
  if (!item.done) {
    item.status = 'waiting'
    item.statusLabel = 'Cancelled'
    item.message = ''
  }
}

function resetQueue() {
  queue.value = []
}

defineExpose({ resetQueue })

onBeforeUnmount(() => queue.value = [])
</script>

<style scoped>
.dropzone {
  border: 2px dashed rgba(37, 99, 235, 0.35);
  background: rgba(37, 99, 235, 0.04);
  cursor: pointer;
  transition: all 0.15s;
}
.dropzone-active {
  border-color: #2563eb;
  background: rgba(37, 99, 235, 0.12);
}
</style>