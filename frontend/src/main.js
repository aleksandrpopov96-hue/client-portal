import { createApp } from 'vue'
import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { aliases, mdi } from 'vuetify/iconsets/mdi'
import '@mdi/font/css/materialdesignicons.css'

import App from './App.vue'
import router from './router'

const vuetify = createVuetify({
  components,
  directives,
  icons: { defaultSet: 'mdi', aliases, sets: { mdi } },
  theme: {
    defaultTheme: 'portal',
    themes: {
      portal: {
        dark: false,
        colors: {
          primary: '#2563eb',
          secondary: '#0ea5e9',
          accent: '#f97316',
          error: '#ef4444',
          info: '#0ea5e9',
          success: '#22c55e',
          warning: '#f59e0b',
          background: '#eef2f7',
          surface: '#ffffff',
        },
      },
    },
  },
  defaults: {
    VBtn: { rounded: 'lg', textTransform: 'none' },
    VCard: { rounded: 'xl' },
    VTextField: { variant: 'outlined', color: 'primary' },
    VTextarea: { variant: 'outlined', color: 'primary' },
    VSelect: { variant: 'outlined', color: 'primary' },
    VSwitch: { color: 'primary', inset: true },
    VCheckbox: { color: 'primary' },
    VDialog: { rounded: 'xl' },
    VListItem: { rounded: 'lg' },
  },
})

const app = createApp(App)
app.use(vuetify)
app.use(router)
app.mount('#app')