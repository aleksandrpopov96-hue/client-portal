<template>
  <v-app>
    <v-app-bar :color="headerColor" elevation="1">
      <v-app-bar-title class="d-flex align-center">
        <v-avatar v-if="store.brand.logo_uri" :size="32" class="mr-3 bg-surface">
          <v-img :src="store.brand.logo_uri" contain />
        </v-avatar>
        <template v-if="!store.brand.logo_uri">
          <v-icon class="mr-2" color="white">mdi-tray-arrow-up</v-icon>
        </template>
        <span class="text-white">{{ share?.name || store.brand.site_name }}</span>
      </v-app-bar-title>
    </v-app-bar>

    <v-main class="pa-4" style="max-width: 1100px; margin: 0 auto; width: 100%">
      <template v-if="loading">
        <v-skeleton-loader type="card" class="rounded-xl elevation-1" />
      </template>

      <v-alert v-else-if="errorMsg" :type="errorType" variant="tonal" class="mb-3">
        {{ errorMsg }}
      </v-alert>

      <!-- Password gate -->
      <v-card v-else-if="locked" width="420" class="pa-6 mx-auto mt-10 elevation-2 rounded-xl">
        <div class="text-center mb-4">
          <v-icon size="42" color="primary">mdi-lock-outline</v-icon>
          <h2 class="text-h6 font-weight-bold mt-2">Protected share</h2>
          <p class="text-body-2 text-medium-emphasis mb-0">Enter the password to continue.</p>
        </div>
        <v-alert v-if="gateError" type="error" variant="tonal" density="compact" class="mb-3">{{ gateError }}</v-alert>
        <v-form @submit.prevent="unlock">
          <v-text-field
            v-model="password"
            label="Share password"
            type="password"
            prepend-inner-icon="mdi-lock"
            autofocus
            @keyup.enter="unlock"
          />
          <v-btn type="submit" color="primary" block size="large" :loading="gateBusy">Unlock</v-btn>
        </v-form>
      </v-card>

      <!-- Upload-only mode -->
      <v-card v-else-if="share?.mode === 'upload'" class="rounded-xl elevation-1 pa-4">
        <div class="text-center mb-4 mt-2">
          <h2 class="text-h6 font-weight-bold">{{ store.brand.welcome_title }}</h2>
          <p class="text-body-2 text-medium-emphasis mb-0">{{ store.brand.welcome_message }}</p>
        </div>
        <UploadDropzone
          :endpoint="`/api/s/${token}/upload`"
          :upload-path="''"
          :chunk-mb="store.config.upload_chunk_mb"
          :max-upload-mb="share.max_upload_size_mb"
          :allowed-extensions="extList(share.allowed_extensions)"
          @uploaded="lastUploaded = $event"
          @error="errorMsg = $event; errorType = 'error'"
        />
        <v-alert v-if="lastUploaded" type="success" variant="tonal" closable class="mt-4">
          <b>{{ lastUploaded.name }}</b> was uploaded successfully.
        </v-alert>
      </v-card>

      <!-- Browse / both mode -->
      <v-card v-else class="rounded-xl elevation-1">
        <v-toolbar density="comfortable" color="surface">
          <v-btn icon="mdi-arrow-left" variant="text" :disabled="!currentPath" @click="navigate(parentPath)" />
          <v-breadcrumbs :items="crumbs" class="flex-grow-1" density="comfortable">
            <template #item="{ item }">
              <v-breadcrumbs-item @click="navigate(item.href)" class="cursor-pointer">{{ item.title }}</v-breadcrumbs-item>
            </template>
          </v-breadcrumbs>

          <template #extension>
            <v-btn v-if="share.allow_download && !share.root_is_file" variant="tonal" prepend-icon="mdi-folder-zip-outline" size="small" class="ml-2 mb-2" @click="zipFolder">
              Zip folder
            </v-btn>
            <v-btn v-if="share.allow_upload && share.mode === 'both' && !share.root_is_file" variant="tonal" :prepend-icon="showUpload ? 'mdi-close' : 'mdi-upload'" size="small" class="ml-2 mb-2" @click="showUpload = !showUpload">
              {{ showUpload ? 'Close upload' : 'Upload files' }}
            </v-btn>
          </template>
        </v-toolbar>

        <v-card-text v-if="!showUpload || share.mode !== 'both'" class="pa-0">
          <v-skeleton-loader v-if="browseLoading" type="table" />
          <FileTable
            v-else-if="entries.length"
            :entries="entries"
            :preview-enabled="store.config.preview_enabled"
            :downloadable="share.allow_download"
            :deletable="share.allow_delete"
            :thumbnail-endpoint="thumbnailEndpoint"
            @open="onOpen"
            @download="onDownload"
            @preview="onPreview"
            @delete="onDelete"
          />
          <v-empty-state v-else icon="mdi-folder-open-outline" title="This folder is empty" class="rounded-xl" />
        </v-card-text>

        <v-card-text v-else class="pa-4">
          <UploadDropzone
            :endpoint="`/api/s/${token}/upload`"
            :upload-path="relative"
            :chunk-mb="store.config.upload_chunk_mb"
            :max-upload-mb="share.max_upload_size_mb"
            :allowed-extensions="extList(share.allowed_extensions)"
            @uploaded="load"
            @error="errorMsg = $event; errorType = 'error'"
          />
        </v-card-text>
      </v-card>

      <p class="text-caption text-center text-medium-emphasis mt-4">{{ store.brand.footer_text }}</p>
    </v-main>

    <PreviewDialog
      v-model="previewOpen"
      :file="previewFile"
      :preview-endpoint="previewEndpoint"
      :download-endpoint="downloadEndpoint"
    />
  </v-app>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { apiJSON, apiRaw } from '../api/client'
import { store } from '../store'
import FileTable from '../components/FileTable.vue'
import UploadDropzone from '../components/UploadDropzone.vue'
import PreviewDialog from '../components/PreviewDialog.vue'

const route = useRoute()
const token = computed(() => route.params.token)

const share = ref(null)
const locked = ref(false)
const loading = ref(true)
const errorMsg = ref('')
const errorType = ref('error')
const password = ref('')
const gateBusy = ref(false)
const gateError = ref('')
const browseLoading = ref(false)
const entries = ref([])
const currentPath = ref('')
const showUpload = ref(false)
const lastUploaded = ref(null)
const previewOpen = ref(false)
const previewFile = ref(null)

const headerColor = computed(() => share.value?.branding_color || 'primary')

const crumbs = computed(() => {
  const parts = currentPath.value ? currentPath.value.split('/') : []
  const items = [{ title: share.value?.name || 'Share', href: '' }]
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

const relative = computed(() => currentPath.value)

function extList(raw) {
  if (!raw) return []
  return raw.split(',').map((e) => e.trim().toLowerCase())
}

function previewEndpoint(file) {
  return `/api/s/${token.value}/preview?path=${encodeURIComponent(file.relative)}`
}
function downloadEndpoint(file) {
  return `/api/s/${token.value}/download?path=${encodeURIComponent(file.relative)}`
}
function thumbnailEndpoint(file) {
  return `/api/s/${token.value}/thumbnail?path=${encodeURIComponent(file.relative)}`
}

async function init() {
  loading.value = true
  try {
    const meta = await apiJSON('GET', `/api/s/${token.value}/meta`)
    share.value = meta
    locked.value = meta.locked === true
    if (!meta.locked) load()
  } catch (e) {
    errorMsg.value = e.error || 'Share not found'
    errorType.value = e.status === 410 ? 'warning' : 'error'
  } finally {
    loading.value = false
  }
}

async function unlock() {
  gateBusy.value = true
  gateError.value = ''
  try {
    await apiJSON('POST', `/api/s/${token.value}/unlock`, { body: { password: password.value } })
    locked.value = false
    load()
  } catch (e) {
    gateError.value = e.error || 'Incorrect password'
  } finally {
    gateBusy.value = false
  }
}

async function load() {
  browseLoading.value = true
  try {
    if (share.value?.root_is_file) {
      entries.value = [{
        name: share.value.filename,
        is_dir: false,
        size: share.value.size,
        mtime: share.value.mtime,
        relative: '',
      }]
      errorMsg.value = ''
      return
    }
    const data = await apiJSON('GET', `/api/s/${token.value}/ls?path=${encodeURIComponent(currentPath.value)}`)
    entries.value = data.entries
    errorMsg.value = ''
  } catch (e) {
    errorMsg.value = e.error || 'Failed to load folder'
    errorType.value = 'error'
    entries.value = []
  } finally {
    browseLoading.value = false
  }
}

function navigate(path) {
  if (share.value?.root_is_file) return
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
  if (!confirm(`Delete "${entry.name}"?`)) return
  try {
    const form = new FormData()
    form.append('path', entry.relative)
    await apiRaw('POST', `/api/s/${token.value}/delete`, { body: form })
    load()
  } catch (e) {
    errorMsg.value = e.error || 'Delete failed'
    errorType.value = 'error'
  }
}
function zipFolder() {
  window.location.href = `/api/s/${token.value}/zip?path=${encodeURIComponent(currentPath.value)}`
}

onMounted(init)
</script>
