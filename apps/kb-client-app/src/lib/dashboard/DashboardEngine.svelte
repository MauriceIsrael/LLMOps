<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import 'gridstack/dist/gridstack.min.css';
  import type { WidgetDefinition } from './types';
  import { dashboardStore } from './widgetStore.svelte';
  import WidgetShell from './WidgetShell.svelte';

  let { 
    dashboardId = 'default',
    widgets: defaultWidgets = [],
    editMode = false,
    filters
  }: { 
    dashboardId?: string;
    widgets: WidgetDefinition[];
    editMode?: boolean;
    filters?: import('svelte').Snippet;
  } = $props();

  let gridElement: HTMLElement;
  let grid: any; // Using any for GridStack instance to avoid complex types in this template

  // Initialize store with default widgets
  $effect(() => {
    dashboardStore.dashboardId = dashboardId;
    dashboardStore.load(defaultWidgets);
  });

  // Calculate gridstack w/h based on our custom sizes
  function getSizeProps(size: string) {
    switch(size) {
      case 'sm': return { w: 2, h: 2, minW: 2, minH: 2 };
      case 'md': return { w: 4, h: 2, minW: 3, minH: 2 };
      case 'lg': return { w: 6, h: 4, minW: 4, minH: 3 };
      case 'xl': return { w: 12, h: 4, minW: 6, minH: 3 };
      default: return { w: 4, h: 2 };
    }
  }

  onMount(async () => {
    if (!browser) return;

    // Dynamically import gridstack to avoid SSR issues
    const { GridStack } = await import('gridstack');

    grid = GridStack.init({
      cellHeight: 80,
      margin: 10,
      animate: true,
      float: true, // Allow widgets to be pushed up
      column: 12,
      handle: '.grid-drag-handle',
      staticGrid: false, // Must be false initially so plugins are attached
    }, gridElement);

    grid.on('change', (event: Event, items: any[]) => {
      const updates = items.map(item => ({
        id: item.el?.getAttribute('data-gs-id'),
        x: item.x,
        y: item.y,
        w: item.w,
        h: item.h
      })).filter(u => u.id);
      
      if (updates.length > 0) {
        dashboardStore.save(updates as any);
      }
    });
  });

  // Toggle edit mode in gridstack
  $effect(() => {
    if (grid) {
      grid.setStatic(!editMode);
    }
  });

  // Action to register elements to gridstack when Svelte renders them
  function gridItem(node: any) {
    if (grid) {
      // Small timeout to ensure DOM is fully ready
      setTimeout(() => {
        if (!node.gridstackNode) {
          grid.makeWidget(node);
        }
      }, 0);
    }
    return {
      destroy() {
        if (grid && node.gridstackNode) {
          grid.removeWidget(node, false);
        }
      }
    };
  }

  onDestroy(() => {
    if (grid) {
      grid.destroy(false);
    }
  });

  let visibleWidgets = $derived(dashboardStore.widgets.filter(w => !w.hidden));
  let hiddenWidgets = $derived(dashboardStore.widgets.filter(w => w.hidden));
</script>

<div class="dashboard-wrapper">
  {#if filters}
    {@render filters()}
  {/if}

  {#if editMode}
    <div class="mb-4 flex flex-col sm:flex-row sm:items-center justify-between p-4 bg-muted rounded-lg border border-dashed border-primary gap-4">
      <div class="flex items-center gap-2">
        <span class="text-sm font-medium">Mode Édition Actif</span>
        <div class="h-4 w-px bg-border mx-2"></div>
        <button 
          class="px-3 py-1 text-xs bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80"
          onclick={() => dashboardStore.reset(defaultWidgets)}
        >
          Réinitialiser le layout
        </button>
      </div>
      
      {#if hiddenWidgets.length > 0}
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-xs text-muted-foreground">Widgets masqués :</span>
          {#each hiddenWidgets as hw}
            <button 
              class="px-2 py-1 text-xs border bg-background rounded-md hover:bg-accent flex items-center gap-1"
              onclick={() => dashboardStore.toggleWidget(hw.id, false)}
            >
              + {hw.title || hw.id}
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {/if}

  <!-- GridStack Container -->
  <div bind:this={gridElement} class="grid-stack">
    {#each visibleWidgets as widget (widget.id)}
      {@const sizeProps = getSizeProps(widget.defaultSize)}
      <div 
        class="grid-stack-item"
        gs-id={widget.id}
        gs-x={widget.x}
        gs-y={widget.y}
        gs-w={widget.w || sizeProps.w}
        gs-h={widget.h || sizeProps.h}
        gs-min-w={sizeProps.minW}
        gs-min-h={sizeProps.minH}
        use:gridItem
      >
        <div class="grid-stack-item-content">
          <WidgetShell {widget} {editMode}>
            {#if widget.component}
              {@const Component = widget.component}
              <Component {...(widget.props || {})} />
            {:else if widget.type === 'stat'}
              <div class="p-4">Stat Widget Placeholder (id: {widget.id})</div>
            {:else}
              <div class="p-4">Widget (id: {widget.id})</div>
            {/if}
          </WidgetShell>
        </div>
      </div>
    {/each}
  </div>
</div>

<style>
  /* Customizing gridstack internals slightly for cleaner look */
  :global(.grid-stack-item-content) {
    background-color: transparent !important;
    overflow: hidden !important;
  }
</style>
