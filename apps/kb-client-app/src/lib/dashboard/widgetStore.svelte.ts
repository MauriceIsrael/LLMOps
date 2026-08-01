import { browser } from '$app/environment';
import type { WidgetDefinition } from './types';

export class DashboardStore {
  widgets = $state<WidgetDefinition[]>([]);
  dashboardId = $state<string>('default');

  constructor(id: string = 'default') {
    this.dashboardId = id;
  }

  get storageKey() {
    return `dashboard-layout-${this.dashboardId}`;
  }

  load(defaultWidgets: WidgetDefinition[]) {
    if (!browser) {
      this.widgets = defaultWidgets;
      return;
    }

    const saved = localStorage.getItem(this.storageKey);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        // Merge saved layout with default definitions
        // (to pick up new component changes, titles, etc while keeping x,y,w,h)
        this.widgets = defaultWidgets.map(def => {
          const savedDef = parsed.find((w: any) => w.id === def.id);
          if (savedDef) {
            return { ...def, x: savedDef.x, y: savedDef.y, w: savedDef.w, h: savedDef.h, hidden: savedDef.hidden };
          }
          return def;
        });
      } catch (e) {
        console.error('Failed to parse dashboard layout', e);
        this.widgets = defaultWidgets;
      }
    } else {
      this.widgets = defaultWidgets;
    }
  }

  save(layoutUpdates: { id: string, x: number, y: number, w: number, h: number }[]) {
    // Update current state with new layout coords
    this.widgets = this.widgets.map(w => {
      const update = layoutUpdates.find(u => u.id === String(w.id));
      if (update) {
        return { ...w, x: update.x, y: update.y, w: update.w, h: update.h };
      }
      return w;
    });

    if (browser) {
      const serialized = this.widgets.map(w => ({
        id: w.id,
        x: w.x, y: w.y, w: w.w, h: w.h, hidden: w.hidden
      }));
      localStorage.setItem(this.storageKey, JSON.stringify(serialized));
    }
  }

  reset(defaultWidgets: WidgetDefinition[]) {
    if (browser) {
      localStorage.removeItem(this.storageKey);
    }
    this.widgets = [...defaultWidgets];
  }

  toggleWidget(id: string, hidden: boolean) {
    this.widgets = this.widgets.map(w => w.id === id ? { ...w, hidden } : w);
    this.save([]); // trigger save with existing coords
  }

  addWidget(widget: WidgetDefinition) {
    const existing = this.widgets.find(w => w.id === widget.id);
    if (existing) {
      this.toggleWidget(widget.id, false);
    } else {
      this.widgets = [...this.widgets, widget];
      this.save([]); // Persist the new widget immediately
    }
  }
}

// Default instance for simple apps, but can be instantiated per page if needed
export const dashboardStore = new DashboardStore();
