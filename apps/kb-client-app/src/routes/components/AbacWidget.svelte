<script lang="ts">
  import ShieldCheck from 'lucide-svelte/icons/shield-check';
  import ShieldAlert from 'lucide-svelte/icons/shield-alert';

  let { 
    session,
    abacStatus
  }: { 
    session: any;
    abacStatus: any;
  } = $props();
</script>

<div class="space-y-4 p-4">
  {#if session}
    <div class="rounded-lg bg-muted/50 p-3 text-[11px] font-mono overflow-auto max-h-32">
      <div class="text-muted-foreground mb-1">// User Attributes</div>
      <pre>{JSON.stringify(session.user.attributes, null, 2)}</pre>
    </div>

    <div class="grid gap-2">
      <div class="flex items-center justify-between rounded-md border p-2.5">
        <span class="text-sm font-medium">View Users</span>
        {#if abacStatus?.canManageUsers}
          <ShieldCheck class="h-5 w-5 text-green-500" />
        {:else}
          <ShieldAlert class="h-5 w-5 text-destructive" />
        {/if}
      </div>
      <div class="flex items-center justify-between rounded-md border p-2.5">
        <span class="text-sm font-medium">View Settings</span>
        {#if abacStatus?.canEditSettings}
          <ShieldCheck class="h-5 w-5 text-green-500" />
        {:else}
          <ShieldAlert class="h-5 w-5 text-destructive" />
        {/if}
      </div>
      <div class="flex items-center justify-between rounded-md border p-2.5">
        <span class="text-sm font-medium">Secret API Access</span>
        {#if abacStatus?.canAccessSecretAPI}
          <ShieldCheck class="h-5 w-5 text-green-500" />
        {:else}
          <ShieldAlert class="h-5 w-5 text-destructive" />
        {/if}
      </div>
    </div>
  {:else}
    <p class="text-sm text-muted-foreground italic">Sign in to see ABAC evaluation.</p>
  {/if}
</div>
