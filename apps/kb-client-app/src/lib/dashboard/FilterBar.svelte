<script lang="ts">
  import { Filter } from 'lucide-svelte';

  let { 
    children 
  }: { 
    children?: import('svelte').Snippet;
  } = $props();
</script>

{#if children}
  <div class="flex items-center gap-4 bg-background/50 border rounded-lg p-3 mb-4 shadow-sm backdrop-blur">
    <div class="flex items-center gap-2 text-muted-foreground border-r pr-4">
      <Filter class="w-4 h-4" />
      <span class="text-sm font-medium">Filtres</span>
    </div>
    <div class="flex-1 flex flex-wrap gap-2 items-center">
      {@render children()}
    </div>
  </div>
{/if}
