<script lang="ts">
  import { apiFetch } from '$lib/api/fetch';
  import { toast } from '$lib/toast/index.svelte';
  import { goto } from '$app/navigation';
  import { t } from 'svelte-i18n';
  import { Button } from '$lib/components/ui/button';
  import * as Card from '$lib/components/ui/card';
  import type { PageData } from './$types';

  // Granular icons
  import LogIn from 'lucide-svelte/icons/log-in';
  import Eye from 'lucide-svelte/icons/eye';
  import EyeOff from 'lucide-svelte/icons/eye-off';

  let { data }: { data: PageData } = $props();

  // Redirect if already logged in
  if (data.session) {
    goto('/');
  }

  let email = $state('');
  let password = $state('');
  let loading = $state(false);
  let showPassword = $state(false);

  const demoUsers = [
    { label: 'Admin', email: 'admin@example.com', password: 'admin123', role: 'admin' },
    { label: 'User', email: 'user@example.com', password: 'user123', role: 'user' },
  ];

  async function handleLogin(e: Event) {
    e.preventDefault();
    if (loading) return;

    loading = true;
    const { data: session, error } = await apiFetch<{ user: unknown; expires: string }>(
      '/api/auth/login',
      { method: 'POST', body: { email, password } }
    );

    if (error) {
      toast(error.message, { variant: 'error' });
      loading = false;
      return;
    }

    toast('Welcome back!', { variant: 'success' });
    await goto('/');
    window.location.reload();
  }

  function fillDemo(user: typeof demoUsers[0]) {
    email = user.email;
    password = user.password;
  }
</script>

<svelte:head>
  <title>{$t('auth.signIn', { default: 'Sign In' })} — {$t('app.title', { default: 'LLMOps explorer' })}</title>
</svelte:head>

<div class="min-h-screen flex items-center justify-center bg-muted/30 p-4">
  <div class="w-full max-w-md space-y-6">

    <!-- Header -->
    <div class="text-center">
      <div class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
        <LogIn class="h-6 w-6" />
      </div>
      <h1 class="text-2xl font-bold tracking-tight">Sign In</h1>
      <p class="mt-1 text-sm text-muted-foreground">Enter your credentials to access the app</p>
    </div>

    <!-- Demo accounts quick-fill -->
    <Card.Root>
      <Card.Header class="pb-3">
        <Card.Title class="text-sm font-medium text-muted-foreground">Demo accounts</Card.Title>
      </Card.Header>
      <Card.Content class="flex gap-2">
        {#each demoUsers as user}
          <button
            onclick={() => fillDemo(user)}
            class="flex-1 rounded-lg border px-3 py-2 text-left text-sm transition-colors hover:bg-muted"
          >
            <span class="font-medium">{user.label}</span>
            <span class="ml-2 inline-flex items-center rounded-full px-1.5 py-0.5 text-xs
              {user.role === 'admin' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'}">
              {user.role}
            </span>
            <div class="mt-0.5 text-xs text-muted-foreground">{user.email}</div>
          </button>
        {/each}
      </Card.Content>
    </Card.Root>

    <!-- Login form -->
    <Card.Root>
      <Card.Content class="pt-6">
        <form onsubmit={handleLogin} class="space-y-4">
          <div class="space-y-2">
            <label for="email" class="text-sm font-medium">Email</label>
            <input
              id="email"
              type="email"
              bind:value={email}
              required
              autocomplete="email"
              placeholder="admin@example.com"
              class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm
                     ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>

          <div class="space-y-2">
            <label for="password" class="text-sm font-medium">Password</label>
            <div class="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                bind:value={password}
                required
                autocomplete="current-password"
                placeholder="••••••••"
                class="w-full rounded-md border border-input bg-background px-3 py-2 pr-10 text-sm
                       ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <button
                type="button"
                onclick={() => (showPassword = !showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                class="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-foreground"
              >
                {#if showPassword}
                  <EyeOff class="h-4 w-4" />
                {:else}
                  <Eye class="h-4 w-4" />
                {/if}
              </button>
            </div>
          </div>

          <Button type="submit" class="w-full" disabled={loading}>
            {#if loading}
              <span class="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
              Signing in…
            {:else}
              Sign In
            {/if}
          </Button>
        </form>
      </Card.Content>
    </Card.Root>

  </div>
</div>
