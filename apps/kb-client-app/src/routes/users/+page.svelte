<script lang="ts">
  import * as Table from '$lib/components/ui/table';
  import { Button } from '$lib/components/ui/button';
  import * as Card from '$lib/components/ui/card';
  import { t } from 'svelte-i18n';

  // Real users data for the /users page
  const users = [
    { id: '1', name: 'Alice Johnson', email: 'alice@example.com', role: 'Admin', status: 'Active' },
    { id: '2', name: 'Bob Smith', email: 'bob@example.com', role: 'User', status: 'Active' },
    { id: '3', name: 'Charlie Brown', email: 'charlie@example.com', role: 'User', status: 'Inactive' },
    { id: '4', name: 'Diana Prince', email: 'diana@example.com', role: 'Admin', status: 'Active' },
    { id: '5', name: 'Edward Norton', email: 'edward@example.com', role: 'User', status: 'Pending' },
  ];

  import { dashboardStore } from '$lib/dashboard/widgetStore.svelte';
  import StatWidget from '$lib/dashboard/widgets/StatWidget.svelte';
  import { Users } from 'lucide-svelte';

  function addDashboardWidget() {
    dashboardStore.addWidget({
      id: 'stat-total-users',
      type: 'stat',
      title: 'Total Users',
      defaultSize: 'sm',
      component: StatWidget,
      props: { value: users.length.toString(), trend: 'neutral', icon: Users }
    });
    alert('Widget Added to Dashboard!');
  }
</script>

<div class="flex-1 space-y-4 p-4 md:p-8 pt-6">
  <div class="flex items-center justify-between space-y-2">
    <h2 class="text-3xl font-bold tracking-tight">{$t('users.title')}</h2>
    <div class="flex items-center space-x-2">
      <Button variant="outline" onclick={addDashboardWidget}>
        Add to Dashboard
      </Button>
      <Button>{$t('actions.download')}</Button>
    </div>
  </div>

  <Card.Root>
    <Card.Header>
      <Card.Title>{$t('users.title')}</Card.Title>
      <Card.Description>{$t('admin.users.desc', { values: { count: users.length } })}</Card.Description>
    </Card.Header>
    <Card.Content>
      <Table.Root>
        <Table.Header>
          <Table.Row>
            <Table.Head class="w-[100px]">ID</Table.Head>
            <Table.Head>{$t('settings.profile.username')}</Table.Head>
            <Table.Head>{$t('settings.profile.email')}</Table.Head>
            <Table.Head>Role</Table.Head>
            <Table.Head class="text-right">Status</Table.Head>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {#each users as user (user.id)}
            <Table.Row>
              <Table.Cell class="font-medium">{user.id}</Table.Cell>
              <Table.Cell>{user.name}</Table.Cell>
              <Table.Cell>{user.email}</Table.Cell>
              <Table.Cell>{user.role}</Table.Cell>
              <Table.Cell class="text-right">
                <span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium
                  {user.status === 'Active' ? 'bg-green-100 text-green-700' : 'bg-muted text-muted-foreground'}">
                  {user.status}
                </span>
              </Table.Cell>
            </Table.Row>
          {/each}
        </Table.Body>
      </Table.Root>
    </Card.Content>
  </Card.Root>
</div>
