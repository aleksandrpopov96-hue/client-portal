<template>
  <AdminShell>
    <div class="d-flex align-center mb-4">
      <h1 class="text-h5 font-weight-bold">Files</h1>
    </div>

    <v-alert v-if="error" type="error" variant="tonal" closable dense class="mb-3" @update:model-value="error = ''">
      {{ error }}
    </v-alert>

    <v-card class="rounded-xl elevation-1">
      <v-toolbar density="comfortable" color="surface">
        <v-btn
          icon="mdi-arrow-left"
          variant="text"
          :disabled="!currentPath"
          @click="navigate(parentPath)"
        />
        <v-breadcrumbs :items="crumbs" class="flex-grow-1" density="comfortable">
          <template #item="{ item }">
            <v-breadcrumbs-item @click="navigate(item.href)" class="cursor-pointer">
              {{ item.title }}
            </v-breadcrumbs-item>
          </template>
        </v-breadcrumbs>

        <template #extension>
          <v-btn variant="tonal" prepend-icon="mdi-folder-zip-outline" size="small" class="ml-2 mb-2" @click="zipFolder">
            Zip folder
          </v-btn>
          <v-btn variant="tonal" prepend-icon="mdi-folder-plus" size="small" class="ml-2 mb-2" @click="dirDialog = true">
            New folder
          </v-btn>
          <v-btn variant="tonal" :prepend-icon="showUpload ? 'mdi-close' : 'mdi-upload'" size="small" class="ml-2 mb-2" @click="showUpload = !showUpload">
            {{ showUpload ? 'Close upload' : 'Upload files' }}
          </v-btn>
        </template>
      </v-toolbar>

      <v-card-text v-if="!showUpload" class="pa-0">
        <v-skeleton-loader v-if="loading" type="table" />
        <FileTable
          v-else-if="entries.length"
          :entries="entries"
          :preview-enabled="store.config.preview_enabled"
          downloadable
          deletable
          @open="onOpen"
          @download="onDownload"
          @preview="onPreview"
          @delete="onDelete"
        />
        <v-empty-state v-else icon="mdi-folder-open-outline" title="This folder is empty" text="Upload files to get started." class="rounded-xl" />
      </v-card-text>

      <v-card-text v-else class="pa-4">
        <UploadDropzone
          :endpoint="'/api/admin/browser/upload'"
          :upload-path="currentPath"
          :chunk-mb="store.config.upload_chunk_mb"
          @uploaded="onUploaded"
          @error="error = $event"
        />
      </v-card-text>
    </v-card>

    <PreviewDialog
      v-model="previewOpen"
      :file="previewFile"
      :preview-endpoint="previewEndpoint"
      :download-endpoint="downloadEndpoint"
    />

    <v-dialog v-model="dirDialog" max-width="420">
      <v-card class="pa-4">
        <v-card-title class="text-h6 font-weight-bold">New folder</v-card-title>
        <v-card-text>
          <v-text-field v-model="dirName" label="Folder name" density="comfortable" autofocus @keyup.enter="createDir" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="dirDialog = false">Cancel</v-btn>
          <v-btn color="primary" :loading="mkdirBusy" @click="createDir">Create</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </AdminShell>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiJSON, apiRaw } from '../api/client'
import { store } from '../store'
import AdminShell from '../components/AdminShell.vue'
import FileTable from '../components/FileTable.vue'
import UploadDropzone from '../components/UploadDropzone.vue'
import PreviewDialog from '../components/PreviewDialog.vue'

const entries = ref([])
const currentPath = ref('')
const loading = ref(false)
const error = ref('')
const showUpload = ref(false)
const dirDialog = ref(false)
const dirName = ref('')
const mkdirBusy = ref(false)
const previewOpen = ref(false)
const previewFile = ref(null)

const crumbs = computed(() => {
  const parts = currentPath.value ? currentPath.value.split('/') : []
  const items = [{ title: 'Files', href: '' }]
  let acc = ''
  for (const p of parts) {
    acc = acc ? `${acc}/${p}` : p
    items.push({ title: p, href: acc })
  }
  return items
})

const parentPath = computed(() => {
  const parts = currentPath.value.split('/').filter(Boolean)
  parts.pop()
  return parts.join('/')
})

function previewEndpoint(file) {
  return `/api/admin/browser/preview?path=${encodeURIComponent(file.relative)}`
}
function downloadEndpoint(file) {
  return `/api/admin/browser/download?path=${encodeURIComponent(file.relative)}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await apiJSON('GET', `/api/admin/browser/ls?path=${encodeURIComponent(currentPath.value)}`)
    entries.value = data.entries
  } catch (e) {
    error.value = e.error || 'Failed to load folder'
    entries.value = []
  } finally {
    loading.value = false
  }
}

function navigate(path) {
  if (path === currentPath.value) return
  currentPath.value = path || ''
  load()
}

function onOpen(entry) {
  if (entry.is_dir) navigate(entry.relative)
}

function onDownload(entry) {
  window.location.href = downloadEndpoint(entry)
}

function onPreview(entry) {
  previewFile.value = entry
  previewOpen.value = true
}

async function onDelete(entry) {
  if (!confirm(`Delete "${entry.name}"? This cannot be undone.`)) return
  try {
    const form = new FormData()
    form.append('path', entry.relative)
    await apiRaw('POST', '/api/admin/browser/delete', { body: form })
    load()
  } catch (e) {
    error.value = e.error || 'Delete failed'
  }
}

function zipFolder() {
  window.location.href = `/api/admin/browser/zip?path=${encodeURIComponent(currentPath.value)}`
}

function onUploaded() {
  load()
}

async function createDir() {
  const name = dirName.value.trim()
  if (!name) return
  mkdirBusy.value = true
  try {
    const form = new FormData()
    form.append('path', currentPath.value)
    form.append('name', name)
    await apiRaw('POST', '/api/admin/browser/mkdir', { body: form })
    dirDialog.value = false
    dirName.value = ''
    load()
  } catch (e) {
    error.value = e.error || 'Could not create folder'
  } finally {
    mkdirBusy.value = false
  }
}

onMounted(load)
</script>