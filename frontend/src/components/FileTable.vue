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
        @click="$emit('open', item.raw)"
      >
        <v-icon :class="{ 'text-amber': item.raw.is_dir, 'text-blue-grey': !item.raw.is_dir }" class="mr-3">
          {{ iconFor(item.raw.name, item.raw.is_dir) }}
        </v-icon>
        <span class="text-truncate" style="max-width: 320px">{{ item.raw.name }}</span>
      </div>
    </template>

    <template #item.size="{ item }">
      <span class="text-body-2 text-medium-emphasis">{{ item.raw.is_dir ? '—' : humanSize(item.raw.size) }}</span>
    </template>

    <template #item.mtime="{ item }">
      <span class="text-body-2 text-medium-emphasis">{{ fmtDate(item.raw.mtime * 1000) }}</span>
    </template>

    <template #item.actions="{ item }">
      <div class="d-flex justify-end">
        <v-tooltip v-if="previewEnabled && !item.raw.is_dir" location="top" text="Preview">
          <template #activator="{ props }">
            <v-btn v-bind="props" variant="text" icon="mdi-eye-outline" size="small" @click="$emit('preview', item.raw)" />
          </template>
        </v-tooltip>
        <v-tooltip v-if="downloadable && !item.raw.is_dir" location="top" text="Download">
          <template #activator="{ props }">
            <v-btn v-bind="props" variant="text" icon="mdi-download" size="small" @click="$emit('download', item.raw)" />
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
              @click="$emit('delete', item.raw)"
            />
          </template>
        </v-tooltip>
      </div>
    </template>

    <template #bottom />
  </v-data-table>
</template>

<script setup>
import { computed } from 'vue'
import { humanSize, fmtDate } from '../utils/format'
import { iconFor } from '../utils/preview'

defineProps({
  entries: { type: Array, default: () => [] },
  previewEnabled: { type: Boolean, default: true },
  downloadable: { type: Boolean, default: true },
  deletable: { type: Boolean, default: false },
})

defineEmits(['open', 'download', 'preview', 'delete', 'zip'])

const headers = [
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Size', key: 'size', sortable: true },
  { title: 'Modified', key: 'mtime', sortable: true, width: 180 },
  { title: '', key: 'actions', sortable: false, align: 'end' },
]
</script>

<style scoped>
.file-table :deep(.v-data-table__tr) {
  cursor: default;
}
</style>