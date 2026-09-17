<template>
  <AdminShell>
    <div class="d-flex align-center mb-4">
      <h1 class="text-h5 font-weight-bold">Branding</h1>
      <v-spacer />
      <v-btn color="primary" prepend-icon="mdi-content-save" :loading="busy" @click="save">Save</v-btn>
    </div>

    <v-alert v-if="message" type="success" variant="tonal" closable dense class="mb-3">{{ message }}</v-alert>
    <v-alert v-if="error" type="error" variant="tonal" closable dense class="mb-3">{{ error }}</v-alert>

    <v-row>
      <v-col cols="12" md="7">
        <v-card class="rounded-xl elevation-1 pa-4">
          <p class="text-subtitle-2 font-weight-bold mb-3">Portal identity</p>
          <v-text-field v-model="form.site_name" label="Site name" />
          <v-text-field v-model="form.tagline" label="Tagline" />
          <v-text-field v-model="form.welcome_title" label="Welcome title" />
          <v-textarea v-model="form.welcome_message" label="Welcome message" rows="2" />
          <v-text-field v-model="form.footer_text" label="Footer text" />

          <p class="text-subtitle-2 font-weight-bold mt-4 mb-3">Colors</p>
          <v-row>
            <v-col cols="6"><v-text-field v-model="form.primary_color" label="Primary" type="color" /></v-col>
            <v-col cols="6"><v-text-field v-model="form.accent_color" label="Accent" type="color" /></v-col>
            <v-col cols="6"><v-text-field v-model="form.background_color" label="Background" type="color" /></v-col>
            <v-col cols="6"><v-text-field v-model="form.card_color" label="Card" type="color" /></v-col>
            <v-col cols="6"><v-text-field v-model="form.text_color" label="Text" type="color" /></v-col>
          </v-row>
        </v-card>
      </v-col>

      <v-col cols="12" md="5">
        <v-card class="rounded-xl elevation-1 pa-4">
          <p class="text-subtitle-2 font-weight-bold mb-3">Logo</p>
          <div v-if="form.logo_uri" class="d-flex justify-center mb-3">
            <v-avatar :size="120" :rounded="8" color="surface-variant">
              <v-img :src="form.logo_uri" contain />
            </v-avatar>
          </div>
          <v-file-input
            label="Upload logo"
            accept=".png,.jpg,.jpeg,.svg,.webp,.gif"
            prepend-icon="mdi-image-outline"
            @change="uploadLogo"
          />
          <p class="text-caption text-medium-emphasis">PNG or SVG recommended. Replaces the current logo.</p>
        </v-card>

        <v-card class="rounded-xl elevation-1 pa-4 mt-4" :style="{ background: form.background_color }">
          <p class="text-subtitle-2 font-weight-bold" :style="{ color: form.text_color, background: form.card_color, padding: '8px 12px', borderRadius: '10px' }">
            Preview
          </p>
          <div class="d-flex align-center pa-2" :style="{ background: form.card_color, borderRadius: '10px' }">
            <v-icon :color="form.primary_color" class="mr-2" size="34">mdi-shield-lock-outline</v-icon>
            <div>
              <p class="font-weight-bold mb-0" :style="{ color: form.text_color }">{{ form.site_name }}</p>
              <p class="text-caption mb-0" :style="{ color: form.text_color }">{{ form.tagline }}</p>
            </div>
          </div>
        </v-card>
      </v-col>
    </v-row>
  </AdminShell>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { apiJSON, apiRaw } from '../api/client'
import { store } from '../store'
import AdminShell from '../components/AdminShell.vue'

const form = reactive({
  site_name: '',
  tagline: '',
  welcome_title: '',
  welcome_message: '',
  footer_text: '',
  primary_color: '#2563eb',
  accent_color: '#0ea5e9',
  background_color: '#f8fafc',
  card_color: '#ffffff',
  text_color: '#0f172a',
  logo_uri: '',
})

const busy = ref(false)
const message = ref('')
const error = ref('')

onMounted(async () => {
  try {
    const b = await apiJSON('GET', '/api/admin/branding')
    Object.assign(form, {
      site_name: b.site_name || '',
      tagline: b.tagline || '',
      welcome_title: b.welcome_title || '',
      welcome_message: b.welcome_message || '',
      footer_text: b.footer_text || '',
      primary_color: b.primary_color || '#2563eb',
      accent_color: b.accent_color || '#0ea5e9',
      background_color: b.background_color || '#f8fafc',
      card_color: b.card_color || '#ffffff',
      text_color: b.text_color || '#0f172a',
      logo_uri: b.logo_uri || '',
    })
    store.brand = { ...store.brand, ...b }
  } catch (e) {
    error.value = e.error || 'Failed to load branding'
  }
})

async function save() {
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const res = await apiJSON('POST', '/api/admin/branding', {
      body: {
        site_name: form.site_name,
        tagline: form.tagline,
        welcome_title: form.welcome_title,
        welcome_message: form.welcome_message,
        footer_text: form.footer_text,
        primary_color: form.primary_color,
        accent_color: form.accent_color,
        background_color: form.background_color,
        card_color: form.card_color,
        text_color: form.text_color,
      },
    })
    store.brand = { ...store.brand, ...res }
    message.value = 'Branding saved'
  } catch (e) {
    error.value = e.error || 'Save failed'
  } finally {
    busy.value = false
  }
}

async function uploadLogo(file) {
  if (!file) return
  const formData = new FormData()
  formData.append('logo', file)
  try {
    const res = await apiRaw('POST', '/api/admin/branding/logo', { body: formData })
    const data = await res.json()
    form.logo_uri = data.logo
    store.brand.logo_uri = data.logo
  } catch (e) {
    error.value = e.error || 'Logo upload failed'
  }
}
</script>