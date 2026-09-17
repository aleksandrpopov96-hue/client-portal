<template>
  <AdminShell>
    <div class="d-flex align-center mb-2">
      <h1 class="text-h5 font-weight-bold">Users</h1>
      <v-spacer />
      <v-btn color="primary" prepend-icon="mdi-plus" :to="{ name: 'admin-user-new' }">New user</v-btn>
    </div>

    <v-alert v-if="message" type="success" variant="tonal" closable dense class="mb-3">{{ message }}</v-alert>
    <v-alert v-if="error" type="error" variant="tonal" closable dense class="mb-3">{{ error }}</v-alert>

    <v-card class="rounded-xl elevation-1">
      <v-data-table :headers="headers" :items="users" :items-per-page="10" density="comfortable" hover>
        <template #item.username="{ item }">
          <div class="d-flex align-center">
            <v-avatar color="primary" size="32" class="mr-2">
              <span class="text-body-2 text-white font-weight-bold">{{ initials(item.username) }}</span>
            </v-avatar>
            <b>{{ item.username }}</b>
          </div>
        </template>

        <template #item.perms="{ item }">
          <div class="d-flex flex-wrap ga-1">
            <v-chip v-if="item.allow_download" size="x-small" color="info" variant="tonal">D</v-chip>
            <v-chip v-if="item.allow_upload" size="x-small" color="success" variant="tonal">U</v-chip>
            <v-chip v-if="item.allow_delete" size="x-small" color="warning" variant="tonal">X</v-chip>
            <v-chip v-if="item.allow_share" size="x-small" color="primary" variant="tonal">S</v-chip>
          </div>
        </template>

        <template #item.enabled="{ item }">
          <v-chip :color="item.enabled ? 'success' : 'grey'" size="small" variant="tonal">
            {{ item.enabled ? 'Active' : 'Disabled' }}
          </v-chip>
        </template>

        <template #item.last_login_at="{ item }">
          <span class="text-body-2 text-medium-emphasis">{{ fmtSince(item.last_login_at) }}</span>
        </template>

        <template #item.subfolder="{ item }">
          <code class="text-caption">{{ item.subfolder }}</code>
        </template>

        <template #item.actions="{ item }">
          <div class="d-flex justify-end">
            <v-btn size="small" variant="text" icon="mdi-pencil" :to="`/admin/users/${item.id}/edit`" />
            <v-btn size="small" variant="text" icon="mdi-delete-outline" color="error" @click="confirmDelete(item)" />
          </div>
        </template>
      </v-data-table>
    </v-card>
  </AdminShell>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiJSON, apiRaw } from '../api/client'
import { fmtSince } from '../utils/format'
import AdminShell from '../components/AdminShell.vue'

const users = ref([])
const message = ref('')
const error = ref('')

const headers = [
  { title: 'Username', key: 'username', sortable: true },
  { title: 'Access', key: 'perms', sortable: false },
  { title: 'Scope', key: 'subfolder', sortable: true },
  { title: 'Status', key: 'enabled', sortable: true },
  { title: 'Last login', key: 'last_login_at', sortable: true },
  { title: '', key: 'actions', sortable: false, align: 'end' },
]

function initials(name) {
  return (name || '?').slice(0, 2).toUpperCase()
}

async function load() {
  try {
    const data = await apiJSON('GET', '/api/admin/users')
    users.value = data.users
  } catch (e) {
    error.value = e.error || 'Failed to load users'
  }
}

async function confirmDelete(item) {
  if (!confirm(`Delete user "${item.username}"?`)) return
  try {
    await apiRaw('DELETE', `/api/admin/users/${item.id}`)
    message.value = `User "${item.username}" deleted`
    load()
  } catch (e) {
    error.value = e.error || 'Delete failed'
  }
}

onMounted(load)
</script>
