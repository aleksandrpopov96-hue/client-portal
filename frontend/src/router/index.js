import { createRouter, createWebHistory } from 'vue-router'
import { store, refreshSession } from '../store'

const routes = [
  { path: '/', name: 'home', component: () => import('../views/Home.vue') },
  { path: '/login', name: 'user-login', component: () => import('../views/UserLogin.vue') },
  { path: '/browser', name: 'browser', component: () => import('../views/UserBrowser.vue'), meta: { user: true } },
  { path: '/s/:token', name: 'share', component: () => import('../views/ShareView.vue') },
  { path: '/admin/login', name: 'admin-login', component: () => import('../views/AdminLogin.vue') },
  { path: '/admin', name: 'admin-home', component: () => import('../views/AdminDashboard.vue'), meta: { admin: true } },
  { path: '/admin/shares', name: 'admin-shares', component: () => import('../views/AdminShares.vue'), meta: { admin: true } },
  { path: '/admin/shares/new', name: 'admin-share-new', component: () => import('../views/AdminShareForm.vue'), meta: { admin: true } },
  { path: '/admin/shares/:id/edit', name: 'admin-share-edit', component: () => import('../views/AdminShareForm.vue'), meta: { admin: true } },
  { path: '/admin/users', name: 'admin-users', component: () => import('../views/AdminUsers.vue'), meta: { admin: true } },
  { path: '/admin/users/new', name: 'admin-user-new', component: () => import('../views/AdminUserForm.vue'), meta: { admin: true } },
  { path: '/admin/users/:id/edit', name: 'admin-user-edit', component: () => import('../views/AdminUserForm.vue'), meta: { admin: true } },
  { path: '/admin/branding', name: 'admin-branding', component: () => import('../views/AdminBranding.vue'), meta: { admin: true } },
  { path: '/admin/settings', name: 'admin-settings', component: () => import('../views/AdminSettings.vue'), meta: { admin: true } },
  { path: '/admin/audit', name: 'admin-audit', component: () => import('../views/AdminAudit.vue'), meta: { admin: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  if (!store.identity && !store.loading) {
    store.loading = true
    await refreshSession()
    store.loading = false
  }
  if (to.meta.admin && !(store.identity?.role === 'admin')) {
    return { name: 'admin-login', query: { next: to.fullPath } }
  }
  if (to.meta.user && !(store.identity?.role === 'user')) {
    return { name: 'user-login', query: { next: to.fullPath } }
  }
  if (to.name === 'user-login' && store.identity?.role === 'user') {
    return { name: 'browser' }
  }
  if (to.name === 'admin-login' && store.identity?.role === 'admin') {
    return { name: 'admin-home' }
  }
  return true
})

export default router