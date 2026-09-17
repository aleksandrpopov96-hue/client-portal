<template>
  <v-app>
    <v-main class="d-flex align-center justify-center" style="min-height: 100vh">
      <v-progress-circular indeterminate color="primary" />
    </v-main>
  </v-app>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { store } from '../store'

const router = useRouter()

onMounted(async () => {
  await import('../store').then((m) => m.refreshSession())
  if (store.identity?.role === 'admin') router.replace({ name: 'admin-home' })
  else if (store.identity?.role === 'user') router.replace({ name: 'browser' })
  else router.replace({ name: 'user-login' })
})
</script>