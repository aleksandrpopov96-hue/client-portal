<template>
  <AdminShell>
    <div class="d-flex align-center mb-4">
      <h1 class="text-h5 font-weight-bold">Settings</h1>
      <v-spacer />
      <v-btn color="primary" prepend-icon="mdi-content-save" :loading="busy" @click="save">Save</v-btn>
    </div>

    <v-alert v-if="message" type="success" variant="tonal" closable dense class="mb-3">{{ message }}</v-alert>
    <v-alert v-if="error" type="error" variant="tonal" closable dense class="mb-3">{{ error }}</v-alert>

    <v-alert type="info" variant="tonal" class="mb-4">
      These settings protect your Cloudflare tunnel from being overloaded. Changes apply immediately without restarting.
    </v-alert>

    <v-card class="rounded-xl elevation-1 pa-4 mb-4">
      <p class="text-subtitle-2 font-weight-bold mb-3">Transfer limits</p>
      <v-row>
        <v-col cols="12" md="4">
          <v-text-field v-model="form.max_active_transfers" label="Max simultaneous transfers" type="number" min="1" hint="Total active uploads/downloads" />
        </v-col>
        <v-col cols="12" md="4">
          <v-text-field v-model="form.max_active_transfers_per_ip" label="Max transfers per connection" type="number" min="1" />
        </v-col>
        <v-col cols="12" md="4">
          <v-text-field v-model="form.upload_chunk_mb" label="Upload chunk size (MB)" type="number" min="1" hint="Keep under Cloudflare's 100MB proxy cap" />
        </v-col>
      </v-row>
    </v-card>

    <v-card class="rounded-xl elevation-1 pa-4 mb-4">
      <p class="text-subtitle-2 font-weight-bold mb-3">Request rate limits (per connection / per minute)</p>
      <v-row>
        <v-col cols="6" md="3"><v-text-field v-model="form.ratelimit_login_per_min" label="Login attempts" type="number" min="1" /></v-col>
        <v-col cols="6" md="3"><v-text-field v-model="form.ratelimit_api_per_min" label="General API" type="number" min="1" /></v-col>
        <v-col cols="6" md="3"><v-text-field v-model="form.ratelimit_download_per_min" label="Downloads" type="number" min="1" /></v-col>
        <v-col cols="6" md="3"><v-text-field v-model="form.ratelimit_upload_chunk_per_min" label="Upload chunks" type="number" min="1" /></v-col>
      </v-row>
    </v-card>

    <v-card class="rounded-xl elevation-1 pa-4">
      <p class="text-subtitle-2 font-weight-bold mb-3">Features</p>
      <v-row>
        <v-col cols="12" md="4"><v-switch v-model="form.ratelimit_enabled" label="Enable rate limiting" color="primary" /></v-col>
        <v-col cols="12" md="4"><v-switch v-model="form.preview_enabled" label="Enable file previews" color="primary" /></v-col>
        <v-col cols="12" md="4"><v-text-field v-model="form.session_lifetime_hours" label="Session lifetime (hours)" type="number" min="1" /></v-col>
      </v-row>
    </v-card>
  </AdminShell>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { apiJSON } from '../api/client'
import { store } from '../store'
import AdminShell from '../components/AdminShell.vue'

const form = reactive({
  max_active_transfers: 4,
  max_active_transfers_per_ip: 2,
  upload_chunk_mb: 20,
  ratelimit_login_per_min: 10,
  ratelimit_api_per_min: 120,
  ratelimit_download_per_min: 60,
  ratelimit_upload_chunk_per_min: 60,
  ratelimit_enabled: true,
  preview_enabled: true,
  session_lifetime_hours: 12,
})

const busy = ref(false)
const message = ref('')
const error = ref('')

onMounted(async () => {
  try {
    const s = await apiJSON('GET', '/api/admin/settings')
    Object.assign(form, s)
  } catch (e) {
    error.value = e.error || 'Failed to load settings'
  }
})

async function save() {
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    await apiJSON('POST', '/api/admin/settings', { body: { ...form } })
    Object.assign(store.config, { upload_chunk_mb: Number(form.upload_chunk_mb) })
    message.value = 'Settings saved'
  } catch (e) {
    error.value = e.error || 'Save failed'
  } finally {
    busy.value = false
  }
}
</script>