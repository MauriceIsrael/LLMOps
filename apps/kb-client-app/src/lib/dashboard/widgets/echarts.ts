import type { EChartsOption } from 'echarts';

/**
 * Svelte Action to render ECharts.
 * Usage: <div use:chart={options} class="w-full h-full"></div>
 *
 * @performance
 * - Import dynamique (lazy) → exclu du bundle principal.
 * - Import depuis echarts-custom.ts → tree-shaking radical.
 *   Seuls BarChart + PieChart + composants UI sont chargés.
 *   ~1.1 MB minifié → ~200 kB minifié (375 kB → ~65 kB gzip).
 */
export function chart(node: HTMLElement, options: EChartsOption) {
  let chartInstance: any;

  async function init() {
    // Import dynamique du module custom (tree-shaken)
    const { echarts } = await import('./echarts-custom');
    chartInstance = echarts.init(node);
    chartInstance.setOption(options);
  }

  // Lance l'init sans bloquer — le ResizeObserver est déjà actif
  init();

  // ResizeObserver to handle gridstack resizes automatically
  const resizeObserver = new ResizeObserver(() => {
    if (chartInstance) {
      chartInstance.resize();
    }
  });
  
  resizeObserver.observe(node);

  return {
    update(newOptions: EChartsOption) {
      if (chartInstance) {
        chartInstance.setOption(newOptions, true);
      }
    },
    destroy() {
      resizeObserver.disconnect();
      if (chartInstance) {
        chartInstance.dispose();
      }
    }
  };
}
