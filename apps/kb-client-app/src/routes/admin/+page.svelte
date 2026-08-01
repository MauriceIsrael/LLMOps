<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import * as Tabs from '$lib/components/ui/tabs';
  import { Button } from '$lib/components/ui/button';
  import { t } from 'svelte-i18n';
  
  import Shield from 'lucide-svelte/icons/shield';
  import UserPlus from 'lucide-svelte/icons/user-plus';
  import UserIcon from 'lucide-svelte/icons/user';
  import Mail from 'lucide-svelte/icons/mail';
  import Hash from 'lucide-svelte/icons/hash';
  import Settings from 'lucide-svelte/icons/settings';

  import AdminUserDialog from '$lib/components/admin/AdminUserDialog.svelte';
  import AdminPolicyTable from '$lib/components/admin/AdminPolicyTable.svelte';

  let { data } = $props();

  let userDialogOpen = $state(false);
  let selectedUser = $state(null);

  function openEdit(user: any) {
    selectedUser = user;
    userDialogOpen = true;
  }

  function openAdd() {
    selectedUser = null;
    userDialogOpen = true;
  }

  const roleColors = {
    admin: 'bg-primary/10 text-primary border-primary/20',
    user: 'bg-muted text-muted-foreground border-border',
  } as const;
</script>

<svelte:head>
  <title>{$t('nav.admin')} — Template App</title>
</svelte:head>

<div class="flex-1 space-y-6 p-4 md:p-8 pt-6">

  <!-- Page header -->
  <div class="flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Shield class="h-5 w-5" />
      </div>
      <div>
        <h1 class="text-2xl font-bold tracking-tight">{$t('admin.title')}</h1>
        <p class="text-sm text-muted-foreground">{$t('admin.desc')}</p>
      </div>
    </div>
  </div>

  <Tabs.Root value="users" class="space-y-6">
    <Tabs.List>
      <Tabs.Trigger value="users">{$t('admin.tabs.users')}</Tabs.Trigger>
      <Tabs.Trigger value="permissions">{$t('admin.tabs.permissions')}</Tabs.Trigger>
    </Tabs.List>

    <!-- USERS TAB -->
    <Tabs.Content value="users" class="space-y-4">
      <div class="flex justify-end">
        <Button onclick={openAdd} size="sm" class="gap-1.5">
          <UserPlus class="h-4 w-4" /> {$t('admin.users.addUser')}
        </Button>
      </div>

      <Card.Root>
        <Card.Header>
          <Card.Title>{$t('admin.users.title')}</Card.Title>
          <Card.Description>{$t('admin.users.desc', { values: { count: data.users?.length ?? 0 } })}</Card.Description>
        </Card.Header>
        <Card.Content>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b text-left text-muted-foreground">
                  <th class="pb-3 pr-6 font-medium"><span class="flex items-center gap-1.5"><Hash class="h-3.5 w-3.5" /> ID</span></th>
                  <th class="pb-3 pr-6 font-medium"><span class="flex items-center gap-1.5"><UserIcon class="h-3.5 w-3.5" /> Name</span></th>
                  <th class="pb-3 pr-6 font-medium"><span class="flex items-center gap-1.5"><Mail class="h-3.5 w-3.5" /> Email</span></th>
                  <th class="pb-3 pr-6 font-medium">Role</th>
                  <th class="pb-3 w-10"></th>
                </tr>
              </thead>
              <tbody class="divide-y">
                {#each (data.users ?? []) as user}
                  <tr class="hover:bg-muted/30 transition-colors">
                    <td class="py-3 pr-6"><code class="text-xs text-muted-foreground">{user.id.slice(0, 8)}</code></td>
                    <td class="py-3 pr-6 font-medium">{user.name}</td>
                    <td class="py-3 pr-6 text-muted-foreground">{user.email}</td>
                    <td class="py-3 pr-6">
                      <span class="inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium
                        {roleColors[user.role as keyof typeof roleColors] ?? roleColors.user}">
                        {user.role}
                      </span>
                    </td>
                    <td class="py-3">
                      <Button variant="ghost" size="icon-sm" onclick={() => openEdit(user)}>
                        <Settings class="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </Card.Content>
      </Card.Root>
    </Tabs.Content>

    <!-- PERMISSIONS TAB -->
    <Tabs.Content value="permissions">
      <AdminPolicyTable policies={data.policies} groups={data.groups} users={data.users} />
    </Tabs.Content>
  </Tabs.Root>

</div>

{#if userDialogOpen}
  <AdminUserDialog bind:open={userDialogOpen} user={selectedUser} />
{/if}
