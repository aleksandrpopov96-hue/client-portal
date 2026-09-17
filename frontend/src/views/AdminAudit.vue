<template>
  <AdminShell>
    <div class="d-flex align-center mb-2">
      <h1 class="text-h5 font-weight-bold">Activity log</h1>
      <v-spacer />
      <v-btn variant="tonal" prepend-icon="mdi-refresh" @click="load">Refresh</v-btn>
    </div>

    <p class="text-caption text-medium-emphasis mb-3">Recent logins, downloads, uploads, previews and deletions.</p>

    <v-card class="rounded-xl elevation-1">
      <v-data-table :headers="headers" :items="entries" :items-per-page="25" density="comfortable">
        <template #item.action="{ item }">
          <v-chip :color="chipColor(item.action)" size="small" variant="tonal">{{ item.action }}</v-chip>
        </template>
        <template #item.bytes="{ item }">
          <span class="text-body-2 text-medium-emphasis">{{ item.bytes != null ? humanSize(item.bytes) : '—' }}</span>
        </template>
        <template #item.created_at="{ item }">
          <span class="text-body-2">{{ fmtDate(item.created_at) }}</span>
        </template>
      </v-data-table>
    </v-card>
  </AdminShell>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiJSON } from '../api/client'
import { humanSize, fmtDate } from '../utils/format'
import AdminShell from '../components/AdminShell.vue'

const entries = ref([])
const headers = [
  { title: 'When', key: 'created_at', sortable: true },
  { title: 'Who', key: 'actor', sortable: true },
  { title: 'Action', key: 'action', sortable: true },
  { title: 'Path', key: 'path', sortable: false },
  { title: 'IP', key: 'ip', sortable: true },
  { title: 'Size', key: 'bytes', sortable: true },
]

function chipColor(action) {
  if (action.includes('login:fail')) return 'error'
  if (action.startsWith('background')) return 'info'
  if (action.startsWith('upload')) return 'success'
  if (action.startsWith('download')) return 'primary'
  if (action.startsWith('preview')) return 'secondary'
  if (action === 'delete') return 'warning'
  return 'default'
}

async function load() {
  const data = await apiJSON('GET', '/api/admin/audit?limit=250')
  entries.value = data.entries
}

onMounted(load)
</script>