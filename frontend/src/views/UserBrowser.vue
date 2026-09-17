<template>
  <v-app class="user-app">
    <v-app-bar color="primary" elevation="1">
      <v-app-bar-title class="d-flex align-center">
        <v-avatar v-if="store.brand.logo_uri" :size="32" class="mr-3 bg-surface">
          <v-img :src="store.brand.logo_uri" contain />
        </v-avatar>
        <template v-if="!store.brand.logo_uri">
          <v-icon class="mr-2" color="white">mdi-shield-lock-outline</v-icon>
        </template>
        <span class="text-white">{{ store.brand.site_name || 'Client Portal' }}</span>
      </v-app-bar-title>

      <template #append>
        <v-chip variant="tonal" color="white" class="mr-2 text-caption">
          signed in as <b class="ml-1">{{ whoami.username || store.identity?.username }}</b>
        </v-chip>
        <v-btn color="white" variant="text" prepend-icon="mdi-logout" @click="logout">Log out</v-btn>
      </template>
    </v-app-bar>

    <v-main class="pa-4" style="max-width: 1100px; margin: 0 auto; width: 100%">
      <v-alert v-if="error" type="error" variant="tonal" closable dense class="mb-3" @update:model-value="error = ''">
        {{ error }}
      </v-alert>
      <v-alert v-if="message" type="success" variant="tonal" closable dense class="mb-3" @update:model-value="message = ''">
        {{ message }}
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
            <v-btn v-if="user.allow_download" variant="tonal" prepend-icon="mdi-folder-zip-outline" size="small" class="ml-2 mb-2" @click="zipFolder">
              Zip folder
            </v-btn>
            <v-btn v-if="user.allow_upload" variant="tonal" prepend-icon="mdi-folder-plus" size="small" class="ml-2 mb-2" @click="dirDialog = true">
              New folder
            </v-btn>
            <v-btn v-if="user.allow_upload" variant="tonal" :prepend-icon="showUpload ? 'mdi-close' : 'mdi-upload'" size="small" class="ml-2 mb-2" @click="showUpload = !showUpload">
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
            :downloadable="user.allow_download"
            :deletable="user.allow_delete"
            :thumbnail-endpoint="thumbnailEndpoint"
            :shareable="user.allow_share"
            @open="onOpen"
            @download="onDownload"
            @preview="onPreview"
            @delete="onDelete"
            @share="onShare"
          />
          <v-empty-state v-else icon="mdi-folder-open-outline" title="This folder is empty" text="Upload files to get started." class="rounded-xl" />
        </v-card-text>

        <v-card-text v-else class="pa-4">
          <UploadDropzone
            :endpoint="'/api/user/upload'"
            :upload-path="currentPath"
            :chunk-mb="store.config.upload_chunk_mb"
            :max-upload-mb="user.max_upload_size_mb"
            :allowed-extensions="extList(user.allowed_extensions)"
            @uploaded="onUploaded"
            @error="error = $event"
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
  </v-app>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { apiJSON, apiRaw } from '../api/client'
import { store, logoutUser } from '../store'
import FileTable from '../components/FileTable.vue'
import UploadDropzone from '../components/UploadDropzone.vue'
import PreviewDialog from '../components/PreviewDialog.vue'
import { kindOf } from '../utils/preview'

const router = useRouter()
const entries = ref([])
const currentPath = ref('')
const loading = ref(false)
const error = ref('')
const message = ref('')
const whoami = ref({})
const user = ref({ allow_download: true, allow_upload: false, allow_delete: false, max_upload_size_mb: 100 })
const showUpload = ref(false)
const dirDialog = ref(false)
const dirName = ref('')
const mkdirBusy = ref(false)
const previewOpen = ref(false)
const previewFile = ref(null)

const crumbs = computed(() => {
  const parts = currentPath.value ? currentPath.value.split('/') : []
  const items = [{ title: 'Home', href: '' }]
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
  return `/api/user/preview?path=${encodeURIComponent(file.relative)}`
}
function downloadEndpoint(file) {
  return `/api/user/download?path=${encodeURIComponent(file.relative)}`
}
function thumbnailEndpoint(file) {
  return `/api/user/thumbnail?path=${encodeURIComponent(file.relative)}`
}

function extList(raw) {
  if (!raw) return []
  return raw.split(',').map((e) => e.trim().toLowerCase())
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await apiJSON('GET', `/api/user/ls?path=${encodeURIComponent(currentPath.value)}`)
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
    await apiRaw('POST', '/api/user/delete', { body: form })
    load()
  } catch (e) {
    error.value = e.error || 'Delete failed'
  }
}

async function onShare(entry) {
  try {
    const res = await apiJSON('POST', '/api/user/share', {
      body: { path: entry.relative, name: entry.name },
    })
    await copyText(res.url)
    message.value = `Public link copied: ${res.url}`
  } catch (e) {
    error.value = e.error || 'Could not create share link'
  }
}

function zipFolder() {
  window.location.href = `/api/user/zip?path=${encodeURIComponent(currentPath.value)}`
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
    await apiRaw('POST', '/api/user/mkdir', { body: form })
    dirDialog.value = false
    dirName.value = ''
    load()
  } catch (e) {
    error.value = e.error || 'Could not create folder'
  } finally {
    mkdirBusy.value = false
  }
}

async function logout() {
  await logoutUser()
  router.replace({ name: 'user-login' })
}

onMounted(async () => {
  whoami.value = await apiJSON('GET', '/api/user/whoami')
  user.value = { ...user.value, ...whoami.value }
  load()
})

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
  }
}
</script>
