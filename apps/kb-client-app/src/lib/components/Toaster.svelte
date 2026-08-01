<script lang="ts">
  import { toastQueue, dismiss, type Toast, type ToastVariant } from '$lib/toast/index.svelte';
  
  // Granular icons
  import CheckCircle2 from 'lucide-svelte/icons/check-circle-2';
  import XCircle from 'lucide-svelte/icons/x-circle';
  import AlertTriangle from 'lucide-svelte/icons/alert-triangle';
  import Info from 'lucide-svelte/icons/info';
  import X from 'lucide-svelte/icons/x';

  // Auto-dismiss timers per toast id
  const timers = new Map<string, ReturnType<typeof setTimeout>>();

  function scheduleAutoDismiss(t: Toast) {
    if (timers.has(t.id)) return;
    const timer = setTimeout(() => {
      dismiss(t.id);
      timers.delete(t.id);
    }, t.duration);
    timers.set(t.id, timer);
  }

  const variantConfig: Record<ToastVariant, { icon: any; classes: string }> = {
    default: {
      icon: Info,
      classes: 'bg-background border-border text-foreground',
    },
    success: {
      icon: CheckCircle2,
      classes: 'bg-background border-green-500 text-foreground',
    },
    error: {
      icon: XCircle,
      classes: 'bg-background border-destructive text-foreground',
    },
    warning: {
      icon: AlertTriangle,
      classes: 'bg-background border-yellow-500 text-foreground',
    },
    info: {
      icon: Info,
      classes: 'bg-background border-primary text-foreground',
    },
  };

  const iconColor: Record<ToastVariant, string> = {
    default: 'text-muted-foreground',
    success: 'text-green-500',
    error: 'text-destructive',
    warning: 'text-yellow-500',
    info: 'text-primary',
  };

  // Schedule dismiss for every toast in the queue
  $effect(() => {
    toastQueue.items.forEach(scheduleAutoDismiss);
  });
</script>

<div
  role="status"
  aria-live="polite"
  aria-atomic="false"
  class="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none"
>
  {#each toastQueue.items as t (t.id)}
    {@const cfg = variantConfig[t.variant]}
    {@const Icon = cfg.icon}

    <div
      class="pointer-events-auto flex items-start gap-3 min-w-[280px] max-w-sm
             rounded-lg border px-4 py-3 shadow-lg
             animate-in slide-in-from-right-2 duration-300
             {cfg.classes}"
    >
      <Icon class="h-5 w-5 shrink-0 mt-0.5 {iconColor[t.variant]}" aria-hidden="true" />

      <p class="flex-1 text-sm leading-snug">{t.message}</p>

      <button
        onclick={() => {
          clearTimeout(timers.get(t.id));
          timers.delete(t.id);
          dismiss(t.id);
        }}
        aria-label="Dismiss notification"
        class="shrink-0 rounded p-0.5 opacity-60 hover:opacity-100 hover:bg-muted transition-opacity"
      >
        <X class="h-4 w-4" />
      </button>
    </div>
  {/each}
</div>
