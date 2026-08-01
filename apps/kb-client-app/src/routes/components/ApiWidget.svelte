<script lang="ts">
  import { Button } from '$lib/components/ui/button';
  import { toastSuccess, toastError } from '$lib/toast/index.svelte';
  import { apiFetch } from '$lib/api/fetch';
  import { get } from 'svelte/store';
  import { t } from 'svelte-i18n';

  let newItemName = $state('');

  async function createItem() {
    if (!newItemName.trim()) return;
    const { data, error } = await apiFetch<any>('/api/demo', {
      method: 'POST',
      body: { name: newItemName },
    });
    if (error) { toastError(get(t)('feedback.somethingWentWrong')); return; }
    newItemName = '';
    toastSuccess(get(t)('feedback.created', { values: { name: data!.name } }));
  }
</script>

<div class="space-y-3 p-4">
  <div class="flex gap-2">
    <input bind:value={newItemName} placeholder="New item..." class="flex-1 rounded-md border px-3 py-1.5 text-sm" />
    <Button size="sm" onclick={createItem}>Add</Button>
  </div>
</div>
