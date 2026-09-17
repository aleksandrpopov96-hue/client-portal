<template>
  <v-dialog :model-value="modelValue" :fullscreen="fullscreen" max-width="1200" transition="dialog-bottom-transition" @update:model-value="$emit('update:modelValue', $event)">
    <v-card v-if="file" class="d-flex flex-column preview-card">
      <v-toolbar color="surface-variant" density="comfortable">
        <v-icon class="mr-3">{{ iconFor(file.name, false) }}</v-icon>
        <v-toolbar-title class="text-truncate">{{ file.name }}</v-toolbar-title>
        <v-spacer />
        <v-tooltip text="Download original" location="top">
          <template #activator="{ props }">
            <v-btn v-bind="props" variant="text" icon="mdi-download" @click="onDownload" />
          </template>
        </v-tooltip>
        <v-tooltip text="Close" location="top">
          <template #activator="{ props }">
            <v-btn v-bind="props" variant="text" icon="mdi-close" @click="$emit('update:modelValue', false)" />
          </template>
        </v-tooltip>
      </v-toolbar>

      <v-card-text class="flex-grow-1 overflow-auto bg-black" style="min-height: 50vh">
        <div v-if="kind === 'text'" class="bg-surface pa-4 rounded-lg">
          <pre class="text-body-2 pa-0 ma-0" style="white-space: pre-wrap; word-break: break-word">{{ text }}</pre>
        </div>

        <div v-else-if="kind === 'image'" class="d-flex align-center justify-center fill-height">
          <img :src="previewUrl()" class="img-preview" loading="lazy" />
        </div>

        <div v-else-if="kind === 'video'" class="d-flex align-center justify-center fill-height">
          <video :src="previewUrl()" controls autoplay playsinline class="w-100 video-preview" />
        </div>

        <div v-else-if="kind === 'audio'" class="d-flex flex-column align-center justify-center fill-height">
          <audio :src="previewUrl()" controls class="w-75" />
        </div>

        <div v-else-if="kind === 'pdf'">
          <v-progress-circular v-if="pdfLoading" indeterminate color="primary" class="d-block mx-auto mt-8" />
          <iframe
            v-show="!pdfLoading"
            :src="previewUrl()"
            class="pdf-frame"
            @load="pdfLoading = false"
          />
        </div>

        <div v-else class="d-flex flex-column align-center justify-center fill-height pa-6 text-center">
          <v-icon size="56" color="medium-emphasis" class="mb-3">mdi-file-question-outline</v-icon>
          <p class="text-body-1">This file type can't be previewed.</p>
          <v-btn color="primary" variant="tonal" @click="onDownload">Download instead</v-btn>
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { iconFor, kindOf } from '../utils/preview'

const props = defineProps({
  modelValue: Boolean,
  file: { type: Object, default: null },
  previewEndpoint: { type: Function, required: true },
  downloadEndpoint: { type: Function, default: null },
  fullscreen: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue'])

const text = ref('')
const pdfLoading = ref(false)

const kind = computed(() => (props.file ? kindOf(props.file.name) : null))

function previewUrl() {
  return props.file ? props.previewEndpoint(props.file) : ''
}

watch(
  () => [props.modelValue, props.file?.relative],
  async ([open]) => {
    if (!open || !props.file) return
    text.value = ''
    pdfLoading.value = true
    if (kind.value === 'text') {
      try {
        const res = await fetch(previewUrl(), { credentials: 'same-origin' })
        if (res.ok) text.value = await res.text()
      } catch {
        text.value = 'Unable to load text preview.'
      }
    }
  },
  { immediate: true }
)

function onDownload() {
  if (props.downloadEndpoint && props.file) {
    window.location.href = props.downloadEndpoint(props.file)
  } else if (props.file) {
    window.location.href = previewUrl()
  }
}
</script>

<style scoped>
.preview-card { max-height: 90vh; }
.img-preview { max-width: 100%; max-height: 70vh; object-fit: contain; }
.video-preview { max-height: 70vh; }
.pdf-frame { width: 100%; height: 75vh; border: 0; background: #fff; }
</style>
