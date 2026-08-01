<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import { Button } from '$lib/components/ui/button';
  import X from 'lucide-svelte/icons/x';
  import GripHorizontal from 'lucide-svelte/icons/grip-horizontal';
  import type { WidgetDefinition } from './types';
  import { dashboardStore } from './widgetStore.svelte';

  let { 
    widget,
    editMode,
    children 
  }: { 
    widget: WidgetDefinition;
    editMode: boolean;
    children?: import('svelte').Snippet;
  } = $props();

  function hideWidget() {
    dashboardStore.toggleWidget(widget.id, true);
  }
</script>

<Card.Root class="w-full h-full flex flex-col shadow-sm border overflow-hidden relative group">
  {#if widget.title || editMode}
    <Card.Header class="grid-drag-handle flex flex-row items-center justify-between p-3 pb-0 space-y-0 min-h-[40px] {editMode ? 'cursor-move' : ''}">
      <div class="flex items-center gap-2 overflow-hidden">
        {#if editMode}
          <div class="text-muted-foreground">
            <GripHorizontal class="w-4 h-4" />
          </div>
        {/if}
        <Card.Title class="text-sm font-medium truncate">
          {widget.title || widget.id}
        </Card.Title>
      </div>

      {#if editMode}
        <Button variant="ghost" size="icon" class="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity" onclick={hideWidget}>
          <X class="w-4 h-4 text-muted-foreground hover:text-destructive" />
          <span class="sr-only">Masquer widget</span>
        </Button>
      {/if}
    </Card.Header>
  {/if}

  <Card.Content class="flex-1 p-0 overflow-auto {widget.title ? 'pt-2' : ''}">
    {#if children}
      {@render children()}
    {/if}
  </Card.Content>
</Card.Root>
