<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import { getContext } from 'svelte';
  
  let { 
    value,
    change,
    trend = 'neutral',
    icon: IconComponent
  }: { 
    value: string;
    change?: string;
    trend?: 'up' | 'down' | 'neutral';
    icon?: any;
  } = $props();

  // Les widgets peuvent récupérer le contexte de filtres s'ils ont besoin de refetch de la data
  // const globalFilters = getContext('dashboardFilters');
</script>

<div class="h-full w-full flex flex-col justify-center p-4 md:p-6">
  <div class="flex items-center justify-between">
    <div class="text-3xl font-bold tracking-tight">
      {value}
    </div>
    {#if IconComponent}
      <div class="p-2 bg-muted rounded-full text-muted-foreground">
        <IconComponent class="h-5 w-5" />
      </div>
    {/if}
  </div>
  {#if change}
    <p class="text-xs text-muted-foreground mt-2">
      <span class={
        trend === 'up' ? 'text-emerald-500 font-medium' : 
        trend === 'down' ? 'text-destructive font-medium' : ''
      }>
        {change}
      </span>
    </p>
  {/if}
</div>
