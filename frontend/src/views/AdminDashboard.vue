<template>
  <AdminShell>
    <div class="d-flex align-center mb-4">
      <v-spacer />
      <v-btn color="primary" prepend-icon="mdi-logout-variant" @click="logout">Log out</v-btn>
    </div>

    <h1 class="text-h5 font-weight-bold mb-4">Dashboard</h1>

    <v-row>
      <v-col cols="12" sm="6" md="3">
        <v-card class="rounded-xl elevation-1">
          <v-card-text class="d-flex align-center">
            <v-avatar color="primary" size="44" rounded="lg" class="mr-3">
              <v-icon color="white">mdi-link-variant</v-icon>
            </v-avatar>
            <div>
              <p class="text-h6 font-weight-bold mb-0">{{ stats.shares?.total ?? '—' }}</p>
              <p class="text-caption text-medium-emphasis mb-0">{{ stats.shares?.enabled ?? 0 }} active shares</p>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" md="3">
        <v-card class="rounded-xl elevation-1">
          <v-card-text class="d-flex align-center">
            <v-avatar color="success" size="44" rounded="lg" class="mr-3">
              <v-icon color="white">mdi-account-group-outline</v-icon>
            </v-avatar>
            <div>
              <p class="text-h6 font-weight-bold mb-0">{{ stats.users?.total ?? '—' }}</p>
              <p class="text-caption text-medium-emphasis mb-0">{{ stats.users?.enabled ?? 0 }} enabled users</p>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" md="3">
        <v-card class="rounded-xl elevation-1">
          <v-card-text class="d-flex align-center">
            <v-avatar color="warning" size="44" rounded="lg" class="mr-3">
              <v-icon color="white">mdi-swap-horizontal</v-icon>
            </v-avatar>
            <div>
              <p class="text-h6 font-weight-bold mb-0">{{ stats.access_log?.total_entries ?? 0 }}</p>
              <p class="text-caption text-medium-emphasis mb-0">total activities</p>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" md="3">
        <v-card class="rounded-xl elevation-1">
          <v-card-text class="d-flex align-center">
            <v-avatar :color="stats.transfers?.active > 0 ? 'error' : 'info'" size="44" rounded="lg" class="mr-3">
              <v-icon color="white">mdi-transfer</v-icon>
            </v-avatar>
            <div>
              <p class="text-h6 font-weight-bold mb-0">{{ stats.transfers?.active ?? 0 }}/{{ stats.transfers?.max_global ?? 4 }}</p>
              <p class="text-caption text-medium-emphasis mb-0">active transfers</p>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card class="rounded-xl elevation-1 mt-4">
      <v-toolbar density="comfortable" color="surface">
        <v-toolbar-title class="text-subtitle-1 font-weight-bold">Top share &amp; user activity</v-toolbar-title>
      </v-toolbar>
      <v-data-table
        :headers="headers"
        :items="actorRows"
        :items-per-page="5"
        density="comfortable"
      >
        <template #item.downloads="{ item }">
          <v-chip size="small" color="info" variant="tonal">{{ item.downloads }}</v-chip>
        </template>
        <template #item.uploads="{ item }">
          <v-chip size="small" color="success" variant="tonal">{{ item.uploads }}</v-chip>
        </template>
        <template #item.total_bytes="{ item }">
          <span class="text-body-2">{{ humanSize(item.total_bytes) }}</span>
        </template>
      </v-data-table>
    </v-card>

    <v-card class="rounded-xl elevation-1 mt-4">
      <v-card-text class="text-caption text-medium-emphasis">
        <v-icon size="16" class="mr-1">mdi-folder-outline</v-icon>
        Storage root: <code>{{ stats.storage_root }}</code>
      </v-card-text>
    </v-card>
  </AdminShell>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { apiJSON } from '../api/client'
import { logoutAdmin } from '../store'
import { humanSize } from '../utils/format'
import AdminShell from '../components/AdminShell.vue'

const router = useRouter()
const stats = ref({})

const actorRows = computed(() =>
  (stats.value.access_log?.actors || []).map((a) => ({ ...a }))
)
const headers = [
  { title: 'Actor', key: 'actor', sortable: true },
  { title: 'Downloads', key: 'downloads', sortable: true },
  { title: 'Uploads', key: 'uploads', sortable: true },
  { title: 'Data moved', key: 'total_bytes', sortable: true },
  { title: 'Actions', key: 'n', sortable: true },
]

async function logout() {
  await logoutAdmin()
  router.replace({ name: 'admin-login' })
}

onMounted(async () => {
  stats.value = await apiJSON('GET', '/api/admin/stats')
})
</script>