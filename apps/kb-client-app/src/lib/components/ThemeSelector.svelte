<script lang="ts">
  import { Button } from '$lib/components/ui/button';
  import Sun from 'lucide-svelte/icons/sun';
  import Moon from 'lucide-svelte/icons/moon';
  import Laptop from 'lucide-svelte/icons/laptop';
  import { preferences } from '$lib/stores/preferences.svelte';
  import { t } from 'svelte-i18n';
  import * as DropdownMenu from '$lib/components/ui/dropdown-menu';

  // Labels for the themes
  const labels = {
    light: 'themeSelector.light',
    dark: 'themeSelector.dark',
    system: 'themeSelector.system'
  };

  function setTheme(theme: 'light' | 'dark' | 'system') {
    preferences.themeOverride = theme;
  }
</script>

<DropdownMenu.Root>
  <DropdownMenu.Trigger>
    {#snippet child({ props })}
      <Button
        variant="ghost"
        size="icon"
        {...props}
        aria-label={$t('themeSelector.title', { default: 'Toggle theme' })}
      >
        {#if preferences.themeOverride === 'light'}
          <Sun class="h-5 w-5" />
        {:else}
          <Moon class="h-5 w-5" />
        {/if}
      </Button>
    {/snippet}
  </DropdownMenu.Trigger>
  <DropdownMenu.Content align="end">
    <DropdownMenu.Item onclick={() => setTheme('light')}>
      <Sun class="mr-2 h-4 w-4" />
      <span>{$t('themeSelector.light', { default: 'Light' })}</span>
    </DropdownMenu.Item>
    <DropdownMenu.Item onclick={() => setTheme('dark')}>
      <Moon class="mr-2 h-4 w-4" />
      <span>{$t('themeSelector.dark', { default: 'Dark' })}</span>
    </DropdownMenu.Item>
    <DropdownMenu.Item onclick={() => setTheme('system')}>
      <Laptop class="mr-2 h-4 w-4" />
      <span>{$t('themeSelector.system', { default: 'System' })}</span>
    </DropdownMenu.Item>
  </DropdownMenu.Content>
</DropdownMenu.Root>
