<template>
  <v-data-table
    :headers="headers"
    :items="entries"
    :items-per-page="-1"
    :hide-default-footer="true"
    density="comfortable"
    hover
    class="file-table"
  >
    <template #item.name="{ item }">
      <div
        class="d-flex align-center cursor-pointer py-1"
        @click="$emit('open', row(item))"
      >
        <v-avatar rounded="lg" size="44" class="mr-3 bg-surface-variant">
          <v-img v-if="thumbnailEndpoint && !row(item).is_dir" :src="thumbnailEndpoint(row(item))" cover>
            <template #placeholder>
              <v-icon color="blue-grey">{{ iconFor(row(item).name, false) }}</v-icon>
            </template>
            <template #error>
              <v-icon color="blue-grey">{{ iconFor(row(item).name, false) }}</v-icon>
            </template>
          </v-img>
          <v-icon v-else :class="{ 'text-amber': row(item).is_dir, 'text-blue-grey': !row(item).is_dir }">
            {{ iconFor(row(item).name, row(item).is_dir) }}
          </v-icon>
        </v-avatar>
        <span class="text-truncate" style="max-width: 320px">{{ row(item).name }}</span>
      </div>
    </template>

    <template #item.size="{ item }">
      <span class="text-body-2 text-medium-emphasis">{{ row(item).is_dir ? '—' : humanSize(row(item).size) }}</span>
    </template>

    <template #item.mtime="{ item }">
      <span class="text-body-2 text-medium-emphasis">{{ fmtDate(row(item).mtime * 1000) }}</span>
    </template>

    <template #item.actions="{ item }">
      <div class="d-flex justify-end">
        <v-tooltip v-if="previewEnabled && !row(item).is_dir" location="top" text="Preview">
          <template #activator="{ props }">
            <v-btn v-bind="props" variant="text" icon="mdi-eye-outline" size="small" @click="$emit('preview', row(item))" />
          </template>
        </v-tooltip>
        <v-tooltip v-if="downloadable && !row(item).is_dir" location="top" text="Download">
          <template #activator="{ props }">
            <v-btn v-bind="props" variant="text" icon="mdi-download" size="small" @click="$emit('download', row(item))" />
          </template>
        </v-tooltip>
        <v-tooltip v-if="deletable" location="top" text="Delete">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              variant="text"
              icon="mdi-delete-outline"
              size="small"
              color="error"
              @click="$emit('delete', row(item))"
            />
          </template>
        </v-tooltip>
        <v-tooltip v-if="shareable" location="top" text="Create public link">
          <template #activator="{ props }">
            <v-btn v-bind="props" variant="text" icon="mdi-share-variant-outline" size="small" color="primary" @click="$emit('share', row(item))" />
          </template>
        </v-tooltip>
      </div>
    </template>

    <template #bottom />
  </v-data-table>
</template>

<script setup>
import { humanSize, fmtDate } from '../utils/format'
import { iconFor } from '../utils/preview'

defineProps({
  entries: { type: Array, default: () => [] },
  previewEnabled: { type: Boolean, default: true },
  downloadable: { type: Boolean, default: true },
  deletable: { type: Boolean, default: false },
  thumbnailEndpoint: { type: Function, default: null },
  shareable: { type: Boolean, default: false },
})

defineEmits(['open', 'download', 'preview', 'delete', 'share', 'zip'])

const headers = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Size', key: 'size', sortable: true },
  { title: 'Modified', key: 'mtime', sortable: true, width: 180 },
  { title: '', key: 'actions', sortable: false, align: 'end' },
]

function row(item) {
  return item?.raw || item
}
</script>

<style scoped>
.file-table :deep(.v-data-table__tr) {
  cursor: default;
}
</style>
