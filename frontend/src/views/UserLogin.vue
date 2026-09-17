<template>
  <v-app>
    <v-main class="fill-height">
      <v-container fluid class="d-flex align-center justify-center fill-height">
        <v-card width="420" class="pa-6 elevation-4">
          <div class="d-flex flex-column align-center mb-6">
            <v-avatar v-if="store.brand.logo_uri" :size="72" class="mb-3">
              <v-img :src="store.brand.logo_uri" contain />
            </v-avatar>
            <h1 class="text-h5 font-weight-bold">{{ store.brand.site_name || 'Client Portal' }}</h1>
            <p class="text-subtitle-2 text-medium-emphasis mt-1">{{ store.brand.tagline }}</p>
          </div>

          <v-alert v-if="error" type="error" variant="tonal" class="mb-4" density="compact">
            {{ error }}
          </v-alert>

          <v-form @submit.prevent="submit">
            <v-text-field
              v-model="username"
              label="Username"
              prepend-inner-icon="mdi-account-outline"
              autocomplete="username"
              required
            />
            <v-text-field
              v-model="password"
              label="Password"
              type="password"
              prepend-inner-icon="mdi-lock-outline"
              autocomplete="current-password"
              required
            />
            <v-btn type="submit" color="primary" block size="large" :loading="busy" class="mt-2">
              Sign in
            </v-btn>
          </v-form>

          <p class="text-caption text-medium-emphasis text-center mt-4">
            <router-link to="/admin/login" class="text-body-2 text-primary">Admin sign in</router-link>
          </p>
        </v-card>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiJSON } from '../api/client'
import { store, refreshSession } from '../store'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')

onMounted(async () => {
  await import('../store').then((m) => m.refreshSession())
  if (store.identity?.role === 'user') router.replace({ name: 'browser' })
})

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await apiJSON('POST', '/api/login', { body: { username: username.value, password: password.value } })
    await refreshSession()
    router.replace((route.query.next) || { name: 'browser' })
  } catch (e) {
    error.value = e.error || 'Sign in failed'
  } finally {
    busy.value = false
  }
}
</script>