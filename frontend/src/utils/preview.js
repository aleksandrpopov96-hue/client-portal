const IMAGE = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'avif', 'bmp', 'svg']
const VIDEO = ['mp4', 'webm', 'mov', 'm4v', 'ogv']
const AUDIO = ['mp3', 'wav', 'ogg', 'oga', 'm4a', 'flac', 'aac', 'opus']
const TEXT = [
  'txt', 'md', 'markdown', 'json', 'csv', 'log', 'py', 'js', 'ts', 'css',
  'sh', 'yaml', 'yml', 'toml', 'ini', 'xml', 'conf', 'sql', 'java', 'c',
  'cpp', 'h', 'go', 'rs', 'rb', 'php',
]
const PDF = ['pdf']

export function ext(filename) {
  const i = filename.lastIndexOf('.')
  return i > 0 ? filename.slice(i + 1).toLowerCase() : ''
}

export function kindOf(filename) {
  const e = ext(filename)
  if (IMAGE.includes(e)) return 'image'
  if (VIDEO.includes(e)) return 'video'
  if (AUDIO.includes(e)) return 'audio'
  if (PDF.includes(e)) return 'pdf'
  if (TEXT.includes(e)) return 'text'
  return null
}

export function iconFor(filename, isDir) {
  if (isDir) return 'mdi-folder'
  const k = kindOf(filename)
  const map = {
    image: 'mdi-file-image',
    video: 'mdi-file-video',
    audio: 'mdi-file-music',
    pdf: 'mdi-file-pdf-box',
    text: 'mdi-file-document-outline',
  }
  if (map[k]) return map[k]
  const e = ext(filename)
  if (['zip', 'rar', '7z', 'tar', 'gz'].includes(e)) return 'mdi-folder-zip'
  if (['xls', 'xlsx', 'csv'].includes(e)) return 'mdi-file-excel'
  if (['doc', 'docx'].includes(e)) return 'mdi-file-word'
  if (['ppt', 'pptx'].includes(e)) return 'mdi-file-powerpoint'
  return 'mdi-file'
}

export function previewLabel(kind) {
  return {
    image: 'Image',
    video: 'Video',
    audio: 'Audio',
    pdf: 'PDF',
    text: 'Text',
  }[kind] || 'File'
}