<template>
  <AdminShell>
    <div class="d-flex align-center mb-4">
      <v-btn variant="text" prepend-icon="mdi-arrow-left" :to="{ name: 'admin-shares' }" class="mr-2">Back</v-btn>
      <h1 class="text-h5 font-weight-bold">{{ isEdit ? 'Edit share' : 'New share' }}</h1>
    </div>

    <v-alert v-if="error" type="error" variant="tonal" closable dense class="mb-3">{{ error }}</v-alert>
    <v-alert v-if="createdUrl" type="success" variant="tonal" class="mb-3">
      <div>Share created. Share this link with your client:</div>
      <div class="d-flex align-center mt-1">
        <code>{{ createdUrl }}</code>
        <v-btn size="x-small" variant="text" icon="mdi-content-copy" @click="copy(createdUrl)" />
      </div>
    </v-alert>

    <v-alert v-if="isEdit" type="info" variant="tonal" class="mb-3">
      <div class="d-flex align-center">
        <code class="text-truncate" style="max-width: 70%">{{ shareUrl }}</code>
        <v-btn size="x-small" variant="text" icon="mdi-content-copy" @click="copy(shareUrl)" class="ml-1" />
        <v-spacer />
        <v-btn size="small" variant="tonal" color="primary" target="_blank" :href="shareUrl" icon="mdi-open-in-new" />
      </div>
    </v-alert>

    <v-card class="rounded-xl elevation-1 pa-4">
      <v-form @submit.prevent="save">
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field v-model="form.name" label="Share name" prepend-inner-icon="mdi-tag-outline" hint="What the client sees as the share title" />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field v-model="form.subfolder" label="Folder path" prepend-inner-icon="mdi-folder-outline" hint="Relative to the storage root, e.g. /acme/proposals" />
          </v-col>

          <v-col cols="12" md="4">
            <v-select
              v-model="form.mode"
              label="Link type"
              :items="modeItems"
              item-title="text"
              item-value="value"
              prepend-inner-icon="mdi-tune-variant"
            />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field
              v-model="form.expires_at"
              label="Expires (optional)"
              type="datetime-local"
              prepend-inner-icon="mdi-clock-outline"
            />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field
              v-model="form.branding_color"
              label="Brand color (optional)"
              type="color"
              hide-details
              class="pt-2"
            />
          </v-col>
        </v-row>

        <v-divider class="my-3" />

        <p class="text-subtitle-2 font-weight-bold mb-2">Client access</p>
        <v-row align="center">
          <v-col cols="12" md="4"><v-switch v-model="form.allow_download" label="Can download files" /></v-col>
          <v-col cols="12" md="4"><v-switch v-model="form.allow_upload" label="Can upload files" /></v-col>
          <v-col cols="12" md="4"><v-switch v-model="form.allow_delete" label="Can delete files" /></v-col>
        </v-row>

        <v-row>
          <v-col cols="12" md="4">
            <v-switch v-model="form.enabled" label="Share is active" color="success" />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field v-model="form.max_upload_size_mb" label="Max upload size (MB)" type="number" min="1" />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field v-model="form.allowed_extensions" label="Allowed extensions" hint="Comma separated, e.g. pdf,jpg. Empty = any" />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="form.password"
              label="Share password"
              type="password"
              prepend-inner-icon="mdi-lock-outline"
              :hint="isEdit ? 'Leave blank to keep the current password' : 'Optional password clients must enter'"
              persistent-hint
            />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field v-model="form.note" label="Internal note (optional)" prepend-inner-icon="mdi-note-text-outline" />
          </v-col>
        </v-row>

        <div class="d-flex justify-end mt-4">
          <v-btn variant="text" class="mr-2" :to="{ name: 'admin-shares' }">Cancel</v-btn>
          <v-btn color="primary" type="submit" :loading="busy">{{ isEdit ? 'Save changes' : 'Create share' }}</v-btn>
        </div>
      </v-form>
    </v-card>
  </AdminShell>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiJSON, apiRaw } from '../api/client'
import AdminShell from '../components/AdminShell.vue'

const route = useRoute()
const router = useRouter()
const shareId = computed(() => route.params.id)
const isEdit = computed(() => Boolean(shareId.value))

const busy = ref(false)
const error = ref('')
const createdUrl = ref('')
const shareUrl = ref('')

const modeItems = [
  { value: 'both', text: 'Browse + Upload' },
  { value: 'browse', text: 'Browse only' },
  { value: 'upload', text: 'Upload only (dropzone)' },
]

const form = ref(blankForm())

function blankForm() {
  return {
    name: '',
    subfolder: '/',
    mode: 'both',
    enabled: true,
    allow_download: true,
    allow_upload: false,
    allow_delete: false,
    max_upload_size_mb: 100,
    allowed_extensions: '',
    expires_at: '',
    branding_color: '#2563eb',
    password: '',
    keep_password: false,
    note: '',
  }
}

onMounted(async () => {
  if (!isEdit.value) return
  try {
    const data = await apiJSON('GET', '/api/admin/shares')
    const share = data.shares.find((s) => String(s.id) === String(shareId.value))
    if (!share) return
    Object.assign(form.value, {
      name: share.name,
      subfolder: share.subfolder,
      mode: share.mode,
      enabled: share.enabled,
      allow_download: share.allow_download,
      allow_upload: share.allow_upload,
      allow_delete: share.allow_delete,
      max_upload_size_mb: share.max_upload_size_mb,
      allowed_extensions: share.allowed_extensions || '',
      expires_at: toLocalInput(share.expires_at),
      branding_color: share.branding_color || '#2563eb',
      note: share.note || '',
    })
    shareUrl.value = data.base_url + '/s/' + share.token
  } catch (e) {
    error.value = e.error || 'Failed to load share'
  }
})

function toLocalInput(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d)) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function save() {
  busy.value = true
  error.value = ''
  const payload = {
    name: form.value.name,
    subfolder: form.value.subfolder,
    mode: form.value.mode,
    enabled: form.value.enabled,
    allow_download: form.value.allow_download,
    allow_upload: form.value.allow_upload,
    allow_delete: form.value.allow_delete,
    max_upload_size_mb: Number(form.value.max_upload_size_mb) || 1,
    allowed_extensions: form.value.allowed_extensions,
    expires_at: form.value.expires_at ? new Date(form.value.expires_at).toISOString() : null,
    branding_color: form.value.branding_color,
    note: form.value.note,
  }
  try {
    if (isEdit.value) {
      payload.keep_password = form.value.keep_password
      if (form.value.password) payload.password = form.value.password
      await apiRaw('PUT', `/api/admin/shares/${shareId.value}`, { body: JSON.stringify(payload) })
      router.push({ name: 'admin-shares' })
    } else {
      if (form.value.password) payload.password = form.value.password
      const res = await apiJSON('POST', '/api/admin/shares', { body: payload })
      createdUrl.value = res.token ? `${location.origin}/s/${res.token}` : ''
      form.value = blankForm()
      await copy(createdUrl.value)
    }
  } catch (e) {
    error.value = e.error || 'Save failed'
  } finally {
    busy.value = false
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {}
}
</script>