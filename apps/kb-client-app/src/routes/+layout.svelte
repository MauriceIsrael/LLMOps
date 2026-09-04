<script lang="ts">
  import '../app.css';
  import type { Snippet } from 'svelte';
  import { get } from 'svelte/store';
  
  // Granular Lucide imports for better dev performance
  import Menu from 'lucide-svelte/icons/menu';
  import LayoutDashboard from 'lucide-svelte/icons/layout-dashboard';
  import Box from 'lucide-svelte/icons/box';
  import FileText from 'lucide-svelte/icons/file-text';
  import Settings from 'lucide-svelte/icons/settings';
  import PanelLeftClose from 'lucide-svelte/icons/panel-left-close';
  import PanelLeftOpen from 'lucide-svelte/icons/panel-left-open';
  import Shield from 'lucide-svelte/icons/shield';
  import LogIn from 'lucide-svelte/icons/log-in';
  import LogOut from 'lucide-svelte/icons/log-out';
  import Lightbulb from 'lucide-svelte/icons/lightbulb';

  import Sparkles from 'lucide-svelte/icons/sparkles';
  import Users from 'lucide-svelte/icons/users';

  import { Button } from '$lib/components/ui/button';
  import * as Sheet from '$lib/components/ui/sheet';
  import * as Avatar from '$lib/components/ui/avatar';
  import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
  import LanguageSwitcher from '$lib/components/LanguageSwitcher.svelte';
  import ThemeSelector from '$lib/components/ThemeSelector.svelte';
  import Toaster from '$lib/components/Toaster.svelte';
  import { t, locale } from 'svelte-i18n';
  import { preferences } from '$lib/stores/preferences.svelte';
  import { hasRole } from '$lib/auth/guard';
  import { apiFetch } from '$lib/api/fetch';
  import { toast } from '$lib/toast/index.svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import '$lib/i18n';
  import type { PageData } from './$types';

  let { children, data }: { children: Snippet; data: PageData } = $props();

  let sidebarOpen = $state(false);

  // Sidebar collapse — now from unified preferences store
  const sidebarCollapsed = $derived(preferences.sidebarCollapsed);
  function toggleSidebar() {
    preferences.sidebarCollapsed = !preferences.sidebarCollapsed;
  }

  // Session shorthand
  const session = $derived(data.session);
  const isAdmin = $derived(hasRole(session, 'admin'));

  /**
   * Navigation items.
   */
  const menuItems = [
    { href: '/',                      labelKey: 'nav.dashboard',  icon: LayoutDashboard, color: 'text-indigo-400', bg: 'bg-indigo-500/10' },
    { href: '/explorer',              labelKey: 'nav.explorer',   icon: Box,             color: 'text-cyan-400',   bg: 'bg-cyan-500/10' },
    { href: '/assets',                labelKey: 'nav.assets',     icon: FileText,        color: 'text-emerald-400',bg: 'bg-emerald-500/10' },
    { href: '/governance/suggestions', labelKey: 'nav.governance', icon: Sparkles,        color: 'text-amber-400',  bg: 'bg-amber-500/10' },
    { href: '/governance/staffing',   labelKey: 'nav.staffing',   icon: Users,           color: 'text-blue-400',   bg: 'bg-blue-500/10' },
    { href: '/ideas',                 labelKey: 'nav.ideas',      icon: Lightbulb,       color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
    { href: '/settings',              labelKey: 'nav.settings',   icon: Settings,        color: 'text-slate-400',  bg: 'bg-slate-500/10' },
  ];

  const adminMenuItems = [
    { href: '/admin', labelKey: 'nav.admin', icon: Shield, color: 'text-rose-400', bg: 'bg-rose-500/10' },
  ];

  async function handleLogout() {
    await apiFetch('/api/auth/logout', { method: 'POST' });
    // In scripts, use get(t) instead of $t subscription
    toast(get(t)('feedback.signedOut'), { variant: 'default' });
    await goto('/login');
    window.location.reload();
  }

  // Dark mode — reads preferences.themeOverride + system media query
  $effect(() => {
    if (typeof window === 'undefined') return;
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const isDark =
      preferences.themeOverride === 'dark' ||
      (preferences.themeOverride === 'system' && systemDark);
    document.documentElement.classList.toggle('dark', isDark);
  });

  // Locale sync
  $effect(() => {
    if ($locale) document.documentElement.lang = $locale;
  });
</script>

<div class="flex min-h-screen w-full flex-col bg-background text-foreground text-base">

  <!-- ─── Top App Bar ──────────────────────────────────────────────────── -->
  <header class="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background px-4 md:px-6">

    <!-- Mobile: hamburger opens Sheet drawer -->
    <Sheet.Root bind:open={sidebarOpen}>
      <Sheet.Trigger>
        {#snippet child({ props })}
          <Button variant="ghost" size="icon" class="md:hidden shrink-0" {...props}
            aria-label={$t('sidebar.expand', { default: 'Open menu' })}>
            <Menu class="h-5 w-5" />
          </Button>
        {/snippet}
      </Sheet.Trigger>
      <Sheet.Content side="left" class="w-64 sm:max-w-none p-0">
        <Sheet.Header class="px-6 pt-6 pb-2">
          <Sheet.Title class="text-base font-semibold">{$t('menu.title', { default: 'Navigation' })}</Sheet.Title>
          <Sheet.Description class="text-sm">{$t('menu.subtitle', { default: '' })}</Sheet.Description>
        </Sheet.Header>
        <nav class="flex flex-col gap-1 px-3 py-4">
          {#each menuItems as item}
            {@const Icon = item.icon}
            {@const active = $page.url.pathname === item.href}
            <a
              href={item.href}
              class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors
                     {active ? 'bg-primary text-primary-foreground' : 'text-foreground hover:bg-muted'}"
              onclick={() => { sidebarOpen = false; }}
            >
              <span class="p-1.5 rounded-lg {active ? 'bg-primary-foreground/20 text-primary-foreground' : `${item.bg} ${item.color}`} shrink-0 flex items-center justify-center">
                <Icon class="h-4 w-4" />
              </span>
              {$t(item.labelKey)}
            </a>
          {/each}

          {#if isAdmin}
            <div class="mt-4 mb-1 px-3">
              <span class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{$t('nav.admin')}</span>
            </div>
            {#each adminMenuItems as item}
              {@const Icon = item.icon}
              {@const active = $page.url.pathname.startsWith(item.href)}
              <a
                href={item.href}
                class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors
                       {active ? 'bg-primary text-primary-foreground' : 'text-foreground hover:bg-muted'}"
                onclick={() => { sidebarOpen = false; }}
              >
                <span class="p-1.5 rounded-lg {active ? 'bg-primary-foreground/20 text-primary-foreground' : `${item.bg} ${item.color}`} shrink-0 flex items-center justify-center">
                  <Icon class="h-4 w-4" />
                </span>
                {$t(item.labelKey, { default: 'Admin' })}
              </a>
            {/each}
          {/if}

        </nav>
      </Sheet.Content>
    </Sheet.Root>

    <!-- Desktop: sidebar collapse toggle -->
    <Button variant="ghost" size="icon" class="hidden md:flex shrink-0" onclick={toggleSidebar}
      aria-label={sidebarCollapsed
        ? $t('sidebar.expand', { default: 'Expand sidebar' })
        : $t('sidebar.collapse', { default: 'Collapse sidebar' })}>
      {#if sidebarCollapsed}
        <PanelLeftOpen class="h-5 w-5" />
      {:else}
        <PanelLeftClose class="h-5 w-5" />
      {/if}
    </Button>

    <!-- App title -->
    <span class="text-lg font-bold tracking-tight truncate">
      {$t('app.title', { default: 'SvelteKit Admin' })}
    </span>

    <!-- Right-side controls -->
    <div class="ml-auto flex items-center gap-1">
      <LanguageSwitcher />
      <ThemeSelector />

      {#if session}
        <!-- Authenticated: avatar dropdown -->
        <DropdownMenu.Root>
          <DropdownMenu.Trigger>
            {#snippet child({ props })}
              <button
                {...props}
                class="ml-2 rounded-full ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                aria-label={$t('a11y.userMenu')}
              >
                <Avatar.Root class="h-9 w-9 border-2 border-border">
                  <Avatar.Image src={session.user.image} alt={session.user.name} />
                  <Avatar.Fallback class="text-xs font-medium">
                    {session.user.name.slice(0, 2).toUpperCase()}
                  </Avatar.Fallback>
                </Avatar.Root>
              </button>
            {/snippet}
          </DropdownMenu.Trigger>
          <DropdownMenu.Content align="end" class="w-56">
            <div class="px-3 py-2 border-b">
              <p class="text-sm font-medium">{session.user.name}</p>
              <p class="text-xs text-muted-foreground truncate">{session.user.email}</p>
              <span class="mt-1 inline-flex items-center rounded-full px-1.5 py-0.5 text-xs font-medium
                {session.user.role === 'admin' ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'}">
                {session.user.role}
              </span>
            </div>
            <DropdownMenu.Item onclick={handleLogout} class="text-destructive focus:text-destructive cursor-pointer">
              <LogOut class="mr-2 h-4 w-4" />
              {$t('auth.signOut')}
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Root>
      {:else}
        <!-- Unauthenticated: sign in button -->
        <Button href="/login" variant="outline" size="sm" class="ml-2 gap-1.5">
          <LogIn class="h-4 w-4" />
          {$t('auth.signIn')}
        </Button>
      {/if}

    </div>
  </header>

  <div class="flex flex-1 overflow-hidden">
    <!-- ─── Desktop Sidebar ────────────────────────────────────────────── -->
    <aside
      class="hidden md:flex flex-col border-r bg-muted/30 transition-all duration-300 ease-in-out overflow-hidden
             {sidebarCollapsed ? 'w-16' : 'w-60'}"
    >
      <nav class="flex flex-col gap-1 px-2 py-4 flex-1">
        {#each menuItems as item}
          {@const Icon = item.icon}
          {@const active = $page.url.pathname === item.href}
          <a
            href={item.href}
            title={sidebarCollapsed ? $t(item.labelKey) : undefined}
            class="flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors group
                   {active ? 'bg-primary text-primary-foreground' : 'text-foreground/80 hover:bg-muted hover:text-foreground'}"
          >
            <span class="p-1.5 rounded-lg {active ? 'bg-primary-foreground/20 text-primary-foreground' : `${item.bg} ${item.color}`} shrink-0 flex items-center justify-center group-hover:scale-110 transition-transform">
              <Icon class="h-4 w-4" />
            </span>
            {#if !sidebarCollapsed}
              <span class="truncate">{$t(item.labelKey)}</span>
            {/if}
          </a>
        {/each}

        {#if isAdmin}
          <div class="mt-4 mb-1 {sidebarCollapsed ? 'px-1' : 'px-3'}">
            {#if !sidebarCollapsed}
              <span class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{$t('nav.admin')}</span>
            {:else}
              <div class="h-px bg-border my-1"></div>
            {/if}
          </div>
          {#each adminMenuItems as item}
            {@const Icon = item.icon}
            {@const active = $page.url.pathname.startsWith(item.href)}
            <a
              href={item.href}
              title={sidebarCollapsed ? $t(item.labelKey, { default: 'Admin' }) : undefined}
              class="flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors group
                     {active ? 'bg-primary text-primary-foreground' : 'text-foreground/80 hover:bg-muted hover:text-foreground'}"
            >
              <span class="p-1.5 rounded-lg {active ? 'bg-primary-foreground/20 text-primary-foreground' : `${item.bg} ${item.color}`} shrink-0 flex items-center justify-center group-hover:scale-110 transition-transform">
                <Icon class="h-4 w-4" />
              </span>
              {#if !sidebarCollapsed}
                <span class="truncate">{$t(item.labelKey, { default: 'Admin' })}</span>
              {/if}
            </a>
          {/each}
        {/if}

      </nav>
    </aside>

    <!-- ─── Main Content ───────────────────────────────────────────────── -->
    <main class="flex-1 overflow-auto">
      {@render children()}
    </main>
  </div>
</div>

<!-- Global toast portal — must be outside the main layout flow -->
<Toaster />
