<template>
  <AdminShell>
    <div class="d-flex align-center mb-4">
      <v-btn variant="text" prepend-icon="mdi-arrow-left" :to="{ name: 'admin-users' }" class="mr-2">Back</v-btn>
      <h1 class="text-h5 font-weight-bold">{{ isEdit ? 'Edit user' : 'New user' }}</h1>
    </div>

    <v-alert v-if="error" type="error" variant="tonal" closable dense class="mb-3">{{ error }}</v-alert>

    <v-card class="rounded-xl elevation-1 pa-4">
      <v-form @submit.prevent="save">
        <v-row>
          <v-col cols="12" md="6">
            <v-text-field v-model="form.username" label="Username" prepend-inner-icon="mdi-account-outline" autocomplete="off" />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field
              v-model="form.password"
              label="Password"
              type="password"
              prepend-inner-icon="mdi-lock-outline"
              autocomplete="new-password"
              :hint="isEdit ? 'Leave blank to keep the current password' : 'Set an initial password'"
              persistent-hint
            />
          </v-col>
        </v-row>

        <v-row align="center">
          <v-col cols="12" md="4"><v-switch v-model="form.enabled" label="Account active" color="success" /></v-col>
          <v-col cols="12" md="4"><v-switch v-model="form.allow_download" label="Can download" /></v-col>
          <v-col cols="12" md="4"><v-switch v-model="form.allow_upload" label="Can upload" /></v-col>
        </v-row>
        <v-row align="center">
          <v-col cols="12" md="4"><v-switch v-model="form.allow_delete" label="Can delete" /></v-col>
          <v-col cols="12" md="4">
            <v-text-field v-model="form.max_upload_size_mb" label="Max upload (MB)" type="number" min="1" />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field v-model="form.subfolder" label="Folder scope" prepend-inner-icon="mdi-folder-outline" hint="Relative to storage root. '/' = everything" />
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12" md="6">
            <v-text-field v-model="form.allowed_extensions" label="Allowed extensions" hint="Comma separated. Empty = any" />
          </v-col>
          <v-col cols="12" md="6">
            <v-text-field v-model="form.note" label="Internal note (optional)" prepend-inner-icon="mdi-note-text-outline" />
          </v-col>
        </v-row>

        <div class="d-flex justify-end mt-4">
          <v-btn variant="text" class="mr-2" :to="{ name: 'admin-users' }">Cancel</v-btn>
          <v-btn color="primary" type="submit" :loading="busy">{{ isEdit ? 'Save changes' : 'Create user' }}</v-btn>
        </div>
      </v-form>
    </v-card>
  </AdminShell>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiJSON, apiRaw } from '../api/client'
import AdminShell from '../components/AdminShell.vue'

const route = useRoute()
const router = useRouter()
const userId = computed(() => route.params.id)
const isEdit = computed(() => Boolean(userId.value))

const busy = ref(false)
const error = ref('')
const form = ref(blank())

function blank() {
  return {
    username: '',
    password: '',
    enabled: true,
    allow_download: true,
    allow_upload: false,
    allow_delete: false,
    max_upload_size_mb: 100,
    allowed_extensions: '',
    subfolder: '/',
    note: '',
  }
}

onMounted(async () => {
  if (!isEdit.value) return
  try {
    const data = await apiJSON('GET', '/api/admin/users')
    const user = data.users.find((u) => String(u.id) === String(userId.value))
    if (!user) return
    Object.assign(form.value, {
      username: user.username,
      enabled: user.enabled,
      allow_download: user.allow_download,
      allow_upload: user.allow_upload,
      allow_delete: user.allow_delete,
      max_upload_size_mb: user.max_upload_size_mb,
      allowed_extensions: user.allowed_extensions || '',
      subfolder: user.subfolder,
      note: user.note || '',
    })
  } catch (e) {
    error.value = e.error || 'Failed to load user'
  }
})

async function save() {
  busy.value = true
  error.value = ''
  const payload = {
    username: form.value.username,
    enabled: form.value.enabled,
    allow_download: form.value.allow_download,
    allow_upload: form.value.allow_upload,
    allow_delete: form.value.allow_delete,
    max_upload_size_mb: Number(form.value.max_upload_size_mb) || 1,
    allowed_extensions: form.value.allowed_extensions,
    subfolder: form.value.subfolder,
    note: form.value.note,
  }
  if (form.value.password) payload.password = form.value.password
  try {
    if (isEdit.value) {
      await apiRaw('PUT', `/api/admin/users/${userId.value}`, { body: JSON.stringify(payload) })
    } else {
      await apiJSON('POST', '/api/admin/users', { body: payload })
    }
    router.push({ name: 'admin-users' })
  } catch (e) {
    error.value = e.error || 'Save failed'
  } finally {
    busy.value = false
  }
}
</script>