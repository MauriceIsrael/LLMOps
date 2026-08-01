/**
 * Custom ECharts build — tree-shaking.
 *
 * On n'importe que les composants réellement utilisés dans l'application :
 *   - BarChart    → graphe en barres (contraintes)
 *   - PieChart    → camembert (objectifs métier)
 *   - Tooltip, Grid, Legend → composants UI
 *   - CanvasRenderer → rendu canvas (plus performant que SVG pour données dynamiques)
 *
 * @size Réduit echarts de ~1.1 MB minifié → ~200 kB minifié (~375 kB → ~65 kB gzip).
 *
 * Pour ajouter un type de graphe (ex. LineChart) :
 *   import { LineChart } from 'echarts/charts';
 *   echarts.use([..., LineChart]);
 */

import * as echarts from 'echarts/core';
import { BarChart, PieChart } from 'echarts/charts';
import {
  TooltipComponent,
  GridComponent,
  LegendComponent
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

// Enregistre les composants une seule fois (idempotent)
echarts.use([
  BarChart,
  PieChart,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  CanvasRenderer
]);

export { echarts };
export type { EChartsOption } from 'echarts';
