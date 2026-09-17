import { reactive } from 'vue'
import { apiJSON } from './api/client'

export const store = reactive({
  identity: null,
  brand: {},
  config: { upload_chunk_mb: 20, max_active_transfers: 4, preview_enabled: true },
  loading: false,
})

export async function refreshSession() {
  try {
    const data = await apiJSON('GET', '/api/session')
    store.identity = data.identity
    if (!store.brand.site_name) {
      const brand = await apiJSON('GET', '/api/branding')
      store.brand = brand
    }
    if (!store.config.upload_chunk_mb || store.config.upload_chunk_mb <= 1) {
      const cfg = await apiJSON('GET', '/api/config')
      Object.assign(store.config, cfg)
    }
  } catch {
    store.identity = null
  }
}

export async function logoutUser() {
  await apiJSON('POST', '/api/logout').catch(() => {})
  store.identity = null
}

export async function logoutAdmin() {
  await apiJSON('POST', '/api/admin/logout').catch(() => {})
  store.identity = null
}

export function isAdmin() {
  return store.identity?.role === 'admin'
}

export function isUser() {
  return store.identity?.role === 'user'
}