<script lang="ts">
  import { chart } from './echarts';
  import type { EChartsOption } from 'echarts';

  let { 
    options 
  }: { 
    options: EChartsOption;
  } = $props();
</script>

<div class="w-full h-full p-2">
  <div use:chart={options} class="w-full h-full min-h-[200px]"></div>
</div>
