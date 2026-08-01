<script lang="ts">
  import { Button } from '$lib/components/ui/button';
  import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
  import Globe from 'lucide-svelte/icons/globe';

  import { setLocale } from '$lib/stores/i18n.svelte';
  import { locale, t } from 'svelte-i18n';

  /**
   * Hardcoded list of UI-visible locales.
   * Do NOT drive this from $availableLocales — that store contains all
   * registered BCP47 aliases (en, en-US, fr, fr-FR …) which causes duplicates.
   *
   * @extension Add an entry here when adding a new language. The `code` must
   * match one of the codes registered in src/lib/i18n.ts.
   */
  const DISPLAY_LOCALES = [
    { code: 'en',    name: 'English' },
    { code: 'fr',    name: 'Français' },
    { code: 'es',    name: 'Español' },
    { code: 'en-UK', name: 'English (UK)' },
  ];
</script>

<DropdownMenu.Root>
  <DropdownMenu.Trigger>
    {#snippet child({ props })}
      <Button variant="ghost" size="icon" {...props} aria-label={$t('nav.language', { default: 'Language' })}>
        <Globe class="h-5 w-5" />
      </Button>
    {/snippet}
  </DropdownMenu.Trigger>
  <DropdownMenu.Content align="end">
    <DropdownMenu.Label>{$t('nav.language', { default: 'Language' })}</DropdownMenu.Label>
    <DropdownMenu.Separator />
    <DropdownMenu.RadioGroup value={$locale ?? 'en'} onValueChange={setLocale}>
      {#each DISPLAY_LOCALES as lang (lang.code)}
        <DropdownMenu.RadioItem value={lang.code}>
          {lang.name}
        </DropdownMenu.RadioItem>
      {/each}
    </DropdownMenu.RadioGroup>
  </DropdownMenu.Content>
</DropdownMenu.Root>
