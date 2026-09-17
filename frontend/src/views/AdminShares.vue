<template>
  <AdminShell>
    <div class="d-flex align-center mb-2">
      <h1 class="text-h5 font-weight-bold">Client shares</h1>
      <v-spacer />
      <v-btn color="primary" prepend-icon="mdi-plus" :to="{ name: 'admin-share-new' }">New share</v-btn>
    </div>

    <v-alert v-if="message" type="success" variant="tonal" closable density="compact" class="mb-3">{{ message }}</v-alert>
    <v-alert v-if="error" type="error" variant="tonal" closable density="compact" class="mb-3">{{ error }}</v-alert>

    <v-card class="rounded-xl elevation-1">
      <v-data-table
        :headers="headers"
        :items="shares"
        :items-per-page="10"
        density="comfortable"
        hover

        @click:row="(e, { item }) => router.push(`/admin/shares/${item.id}/edit`)"
      >
        <template #item.name="{ item }">
          <div class="d-flex align-center">
            <v-icon color="primary" class="mr-2">mdi-link-variant</v-icon>
            <b>{{ item.name }}</b>
          </div>
        </template>

        <template #item.url="{ item }">
          <div class="d-flex align-center">
            <code class="text-caption text-truncate" style="max-width: 260px">{{ item.url }}</code>
            <v-btn size="x-small" variant="text" icon="mdi-content-copy" @click.stop="copy(item.url)" />
          </div>
        </template>

        <template #item.perms="{ item }">
          <div class="d-flex flex-wrap ga-1">
            <v-chip v-if="item.allow_download" size="x-small" color="info" variant="tonal">D</v-chip>
            <v-chip v-if="item.allow_upload" size="x-small" color="success" variant="tonal">U</v-chip>
            <v-chip v-if="item.allow_delete" size="x-small" color="warning" variant="tonal">X</v-chip>
            <v-chip v-if="!item.allow_download && !item.allow_upload" size="x-small" variant="tonal">none</v-chip>
          </div>
        </template>

        <template #item.mode="{ item }">
          <v-chip size="small" variant="tonal">{{ modeLabel(item.mode) }}</v-chip>
        </template>

        <template #item.enabled="{ item }">
          <v-chip :color="item.enabled ? 'success' : 'grey'" size="small" variant="tonal">
            {{ item.enabled ? 'Active' : 'Disabled' }}
          </v-chip>
        </template>

        <template #item.expires_at="{ item }">
          <span class="text-body-2" :class="{ 'text-error': expired(item) }">{{ expired(item) ? 'Expired' : fmtDate(item.expires_at) }}</span>
        </template>

        <template #item.last_used_at="{ item }">
          <span class="text-body-2 text-medium-emphasis">{{ fmtSince(item.last_used_at) }}</span>
        </template>

        <template #item.actions="{ item }">
          <div class="d-flex justify-end">
            <v-btn size="small" variant="text" icon="mdi-pencil" :to="`/admin/shares/${item.id}/edit`" @click.stop />
            <v-btn size="small" variant="text" icon="mdi-delete-outline" color="error" @click.stop="confirmDelete(item)" />
          </div>
        </template>
      </v-data-table>
    </v-card>
  </AdminShell>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { apiJSON, apiRaw } from '../api/client'
import { fmtDate, fmtSince } from '../utils/format'
import AdminShell from '../components/AdminShell.vue'

const router = useRouter()
const shares = ref([])
const message = ref('')
const error = ref('')

const headers = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Link', key: 'url', sortable: false },
  { title: 'Folder', key: 'subfolder', sortable: true },
  { title: 'Access', key: 'perms', sortable: false },
  { title: 'Mode', key: 'mode', sortable: true },
  { title: 'Status', key: 'enabled', sortable: true },
  { title: 'Expires', key: 'expires_at', sortable: true },
  { title: 'Last used', key: 'last_used_at', sortable: true },
  { title: '', key: 'actions', sortable: false, align: 'end' },
]

function modeLabel(mode) {
  return { browse: 'Browse', upload: 'Upload only', both: 'Browse + Upload' }[mode] || mode
}

function expired(item) {
  return item.expires_at && new Date(item.expires_at) < new Date()
}

async function load() {
  try {
    const data = await apiJSON('GET', '/api/admin/shares')
    shares.value = data.shares
  } catch (e) {
    error.value = e.error || 'Failed to load shares'
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text)
    message.value = 'Link copied to clipboard'
  } catch {
    error.value = 'Could not copy link'
  }
}

async function confirmDelete(item) {
  if (!confirm(`Delete share "${item.name}"? The link will stop working.`)) return
  try {
    await apiRaw('DELETE', `/api/admin/shares/${item.id}`)
    message.value = `Share "${item.name}" deleted`
    load()
  } catch (e) {
    error.value = e.error || 'Delete failed'
  }
}

onMounted(load)
</script>