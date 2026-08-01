<script lang="ts">
  import { Button } from '$lib/components/ui/button';
  import { toastSuccess, toastError } from '$lib/toast/index.svelte';
</script>

<div class="p-4">
  <div class="flex flex-wrap gap-2">
    <Button size="sm" variant="outline" onclick={() => toastSuccess('Success!')}>Success</Button>
    <Button size="sm" variant="outline" onclick={() => toastError('Error!')}>Error</Button>
  </div>
</div>
