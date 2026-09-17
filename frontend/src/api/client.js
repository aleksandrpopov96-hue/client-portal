function readCookie(name) {
  const match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[2]) : ''
}

export function csrfToken() {
  return readCookie('portal_csrf')
}

async function ensureCsrf() {
  if (!csrfToken()) {
    await fetch('/api/csrf', { credentials: 'same-origin' })
  }
}

export async function apiJSON(method, path, { body, signal } = {}) {
  await ensureCsrf()
  const opts = {
    method,
    credentials: 'same-origin',
    headers: {
      'X-CSRF-Token': csrfToken(),
      'Content-Type': 'application/json',
    },
    signal,
  }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(path, opts)
  const data = await res.json()
  if (!res.ok) throw { status: res.status, ...data }
  return data
}

export async function apiRaw(method, path, { body, signal } = {}) {
  await ensureCsrf()
  const opts = {
    method,
    credentials: 'same-origin',
    headers: { 'X-CSRF-Token': csrfToken() },
    signal,
  }
  if (body !== undefined) opts.body = body
  const res = await fetch(path, opts)
  if (!res.ok) {
    const data = await res.json().catch(() => ({ error: 'Request failed' }))
    throw { status: res.status, ...data }
  }
  return res
}

export function uploadFile(path, formData, { onProgress, signal } = {}) {
  ensureCsrf()
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', path, true)
    xhr.withCredentials = true
    xhr.setRequestHeader('X-CSRF-Token', csrfToken())
    if (signal) {
      signal.addEventListener('abort', () => xhr.abort())
    }
    if (onProgress && xhr.upload) {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) onProgress(e.loaded, e.total)
      })
    }
    xhr.onload = () => {
      try {
        const data = JSON.parse(xhr.responseText)
        if (xhr.status < 200 || xhr.status >= 300) reject({ status: xhr.status, ...data })
        else resolve(data)
      } catch {
        reject({ status: xhr.status, error: 'Invalid response' })
      }
    }
    xhr.onerror = () => reject({ error: 'Network error' })
    xhr.send(formData)
  })
}

export function downloadUrl(path) {
  window.open(path, '_blank')
}

export function downloadBlob(path) {
  return apiRaw('GET', path).then((r) => r.blob())
}

export function revokeBlobUrl(url) {
  if (url && url.startsWith('blob:')) URL.revokeObjectURL(url)
}

export async function fetchConfig() {
  const res = await fetch('/api/config', { credentials: 'same-origin' })
  return await res.json()
}