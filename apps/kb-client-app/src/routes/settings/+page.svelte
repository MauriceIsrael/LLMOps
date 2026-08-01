<script lang="ts">
  import { Button } from '$lib/components/ui/button';
  import { Input } from '$lib/components/ui/input';
  import { Label } from '$lib/components/ui/label';
  import * as Card from '$lib/components/ui/card';
  import { t } from 'svelte-i18n';
</script>

<div class="flex-1 space-y-4 p-4 md:p-8 pt-6">
  <div class="flex items-center justify-between space-y-2">
    <h2 class="text-3xl font-bold tracking-tight">{$t('settings.title')}</h2>
  </div>

  <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
    <Card.Root class="col-span-2">
      <Card.Header>
        <Card.Title>{$t('settings.profile.title')}</Card.Title>
        <Card.Description>
          {$t('settings.profile.desc')}
        </Card.Description>
      </Card.Header>
      <Card.Content>
        <form class="space-y-8">
          <div class="space-y-2">
            <Label for="username">{$t('settings.profile.username')}</Label>
            <Input id="username" placeholder="shadcn" />
            <p class="text-[0.8rem] text-muted-foreground">
              {$t('settings.profile.usernameDesc')}
            </p>
          </div>
          
          <div class="space-y-2">
            <Label for="email">{$t('settings.profile.email')}</Label>
            <Input id="email" type="email" placeholder="m@example.com" />
            <p class="text-[0.8rem] text-muted-foreground">
              {$t('settings.profile.emailDesc')}
            </p>
          </div>
          
          <Button type="button">{$t('settings.profile.update')}</Button>
        </form>
      </Card.Content>
    </Card.Root>
  </div>
</div>
