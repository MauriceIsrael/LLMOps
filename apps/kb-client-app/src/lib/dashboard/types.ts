export type WidgetSize = 'sm' | 'md' | 'lg' | 'xl';

export type WidgetType = 'stat' | 'chart' | 'table' | 'custom';

export interface WidgetDefinition {
  id: string;
  type: WidgetType;
  title?: string;
  defaultSize: WidgetSize;
  /** Component definition for custom widgets */
  component?: any; 
  /** Any widget-specific props */
  props?: Record<string, any>;
  /** GridStack coordinates, populated automatically */
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  hidden?: boolean;
}

export interface DashboardConfig {
  widgets: WidgetDefinition[];
  /** Optional global filters definition structure */
  filtersDef?: Record<string, any>; 
}
