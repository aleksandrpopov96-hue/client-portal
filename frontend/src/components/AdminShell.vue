<template>
  <v-app>
    <v-navigation-drawer v-model="drawer" class="border-e-warning" permanent>
      <v-list nav density="comfortable" class="mt-2">
        <v-list-item>
          <template #prepend>
            <v-avatar v-if="store.brand.logo_uri" :size="36" class="bg-surface">
              <v-img :src="store.brand.logo_uri" contain />
            </v-avatar>
            <v-icon v-else class="mr-2" color="primary">mdi-cog-outline</v-icon>
          </template>
          <v-list-item-title class="font-weight-bold">{{ store.brand.site_name || 'Client Portal' }}</v-list-item-title>
          <v-list-item-subtitle>Administration</v-list-item-subtitle>
        </v-list-item>
      </v-list>

      <v-divider class="mx-3" />

      <v-list nav density="comfortable">
        <v-list-item v-for="item in nav" :key="item.to" :to="item.to" :active="route.path.startsWith(item.to)" link>
          <template #prepend>
            <v-icon>{{ item.icon }}</v-icon>
          </template>
          <v-list-item-title>{{ item.title }}</v-list-item-title>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <v-main class="pa-4" style="max-width: 1200px; margin: 0 auto; width: 100%">
      <slot />
    </v-main>
  </v-app>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { store } from '../store'

const drawer = ref(null)
const route = useRoute()

const nav = [
  { to: '/admin', title: 'Dashboard', icon: 'mdi-view-dashboard-outline' },
  { to: '/admin/browser', title: 'Files', icon: 'mdi-folder-multiple-outline' },
  { to: '/admin/shares', title: 'Client shares', icon: 'mdi-link-variant' },
  { to: '/admin/users', title: 'Users', icon: 'mdi-account-group-outline' },
  { to: '/admin/branding', title: 'Branding', icon: 'mdi-palette-outline' },
  { to: '/admin/audit', title: 'Activity log', icon: 'mdi-chart-line' },
  { to: '/admin/settings', title: 'Settings', icon: 'mdi-tune-variant' },
]
</script>