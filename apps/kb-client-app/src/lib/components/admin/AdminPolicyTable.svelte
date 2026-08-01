<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import { Button } from '$lib/components/ui/button';
  import { Input } from '$lib/components/ui/input';
  import * as Select from '$lib/components/ui/select';
  import { toastSuccess, toastError } from '$lib/toast/index.svelte';
  import { invalidateAll } from '$app/navigation';
  import Trash from 'lucide-svelte/icons/trash';
  import Plus from 'lucide-svelte/icons/plus';
  import Users from 'lucide-svelte/icons/users';
  import Shield from 'lucide-svelte/icons/shield';
  import ChevronRight from 'lucide-svelte/icons/chevron-right';

  interface User {
    id: string;
    name: string;
    email: string;
  }

  let { policies = [], groups = [], users = [] }: { policies: string[][], groups: string[][], users: User[] } = $props();

  // Extract unique groups from both 'policies' (index 0) and 'groups' (index 1)
  // Also include base roles to always be visible
  const baseRoles = ['admin', 'user'];
  
  // Local state for newly created groups before they have policies/members
  let localGroups = $state<string[]>([]);
  let newGroupName = $state('');

  const uniqueGroups = $derived.by(() => {
    const set = new Set<string>([...baseRoles, ...localGroups]);
    policies.forEach((p: string[]) => set.add(p[0]));
    groups.forEach((g: string[]) => set.add(g[1]));
    return Array.from(set).sort();
  });

  let selectedGroup = $state<string | null>(null);

  // Group specific data
  const groupPolicies = $derived(policies.filter((p: string[]) => p[0] === selectedGroup));
  const groupMembers = $derived(
    groups
      .filter((g: string[]) => g[1] === selectedGroup)
      .map((g: string[]) => {
        const user = users.find((u: User) => u.id === g[0]);
        return {
          id: g[0],
          name: user ? user.name : 'Unknown User',
          email: user ? user.email : 'N/A'
        };
      })
  );

  // Available users not in the selected group
  const availableUsers = $derived(
    users.filter((u: User) => !groupMembers.some((m: { id: string }) => m.id === u.id))
  );

  let newP = $state(['', '']); // obj, act
  let selectedNewUserId = $state<string>('');
  let loading = $state(false);

  // Set initial selected group
  $effect(() => {
    if (!selectedGroup && uniqueGroups.length > 0) {
      selectedGroup = uniqueGroups[0];
    }
  });

  function handleCreateGroup() {
    const name = newGroupName.trim().toLowerCase();
    if (!name) return;
    if (uniqueGroups.includes(name)) {
      toastError('Group already exists');
      return;
    }
    localGroups = [...localGroups, name];
    selectedGroup = name;
    newGroupName = '';
    toastSuccess('Group created (Local only until permissions/members are added)');
  }

  async function addPolicy() {
    if (!selectedGroup || newP.some(v => !v.trim())) return;
    loading = true;
    const res = await fetch('/api/admin/policies', {
      method: 'POST',
      body: JSON.stringify({ type: 'p', params: [selectedGroup, ...newP] })
    });
    loading = false;
    if (res.ok) {
      toastSuccess('Permission added');
      newP = ['', ''];
      invalidateAll();
    } else {
      toastError('Failed to add permission');
    }
  }

  async function addMember() {
    if (!selectedGroup || !selectedNewUserId) return;
    loading = true;
    const res = await fetch('/api/admin/policies', {
      method: 'POST',
      body: JSON.stringify({ type: 'g', params: [selectedNewUserId, selectedGroup] })
    });
    loading = false;
    if (res.ok) {
      toastSuccess('Member added');
      selectedNewUserId = '';
      invalidateAll();
    } else {
      toastError('Failed to add member. Ensure user exists.');
    }
  }

  async function removeRule(type: 'p' | 'g', params: string[]) {
    const res = await fetch(`/api/admin/policies?type=${type}&params=${JSON.stringify(params)}`, {
      method: 'DELETE'
    });
    if (res.ok) {
      toastSuccess(type === 'p' ? 'Permission removed' : 'Member removed');
      invalidateAll();
    } else {
      toastError('Failed to remove rule');
    }
  }
</script>

<div class="grid grid-cols-1 md:grid-cols-[250px_1fr] gap-6 items-start">
  <!-- Sidebar: Group List -->
  <Card.Root class="sticky top-20">
    <Card.Header class="pb-3">
      <Card.Title class="text-lg">Roles & Groups</Card.Title>
      <Card.Description>Select a group to manage.</Card.Description>
    </Card.Header>
    <Card.Content class="p-0">
      <div class="flex flex-col">
        {#each uniqueGroups as group}
          <button
            class="flex items-center justify-between px-4 py-3 text-sm font-medium transition-colors border-l-2
                   {selectedGroup === group ? 'border-primary bg-primary/5 text-primary' : 'border-transparent hover:bg-muted text-foreground/80'}"
            onclick={() => { selectedGroup = group; }}
          >
            <span class="flex items-center gap-2">
              <Shield class="h-4 w-4" />
              {group}
            </span>
            {#if selectedGroup === group}
              <ChevronRight class="h-4 w-4" />
            {/if}
          </button>
        {/each}
      </div>
      <div class="p-4 border-t mt-2">
        <p class="text-xs font-semibold text-muted-foreground uppercase mb-2">Create New Group</p>
        <div class="flex gap-2">
          <Input bind:value={newGroupName} placeholder="group_name" class="h-8 text-sm" />
          <Button size="icon-sm" onclick={handleCreateGroup} variant="secondary" class="shrink-0"><Plus class="h-4 w-4" /></Button>
        </div>
      </div>
    </Card.Content>
  </Card.Root>

  <!-- Main Content: Selected Group Details -->
  <div class="space-y-6">
    {#if selectedGroup}
      <div>
        <h2 class="text-2xl font-bold tracking-tight mb-1">{selectedGroup}</h2>
        <p class="text-sm text-muted-foreground">Manage permissions and members for this group.</p>
      </div>

      <!-- Members Section -->
      <Card.Root>
        <Card.Header>
          <Card.Title class="flex items-center gap-2"><Users class="h-5 w-5" /> Members</Card.Title>
          <Card.Description>Users assigned to this group.</Card.Description>
        </Card.Header>
        <Card.Content>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b text-left text-muted-foreground">
                  <th class="pb-2 font-medium">Name</th>
                  <th class="pb-2 font-medium">Email</th>
                  <th class="pb-2 font-medium w-10"></th>
                </tr>
              </thead>
              <tbody class="divide-y">
                {#each groupMembers as member}
                  <tr class="hover:bg-muted/30 transition-colors">
                    <td class="py-2.5 font-medium">{member.name}</td>
                    <td class="py-2.5 text-muted-foreground">{member.email}</td>
                    <td class="py-2.5 text-right">
                      <Button variant="ghost" size="icon-sm" onclick={() => removeRule('g', [member.id, selectedGroup!])}>
                        <Trash class="h-4 w-4 text-destructive" />
                      </Button>
                    </td>
                  </tr>
                {:else}
                  <tr>
                    <td colspan="3" class="py-4 text-center text-muted-foreground text-xs italic">No members assigned.</td>
                  </tr>
                {/each}
                <tr class="bg-muted/30">
                  <td colspan="2" class="py-2 pr-2">
                    <Select.Root type="single" bind:value={selectedNewUserId}>
                      <Select.Trigger class="h-8 w-full">
                        {availableUsers.find(u => u.id === selectedNewUserId)?.name ?? "Select user to add..."}
                      </Select.Trigger>
                      <Select.Content>
                        {#each availableUsers as user}
                          <Select.Item value={user.id}>{user.name} ({user.email})</Select.Item>
                        {/each}
                      </Select.Content>
                    </Select.Root>
                  </td>
                  <td class="py-2 text-right">
                    <Button size="icon-sm" onclick={addMember} disabled={loading || !selectedNewUserId}><Plus class="h-4 w-4" /></Button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </Card.Content>
      </Card.Root>

      <!-- Permissions Section -->
      <Card.Root>
        <Card.Header>
          <Card.Title class="flex items-center gap-2"><Shield class="h-5 w-5" /> Permissions</Card.Title>
          <Card.Description>API and Data access rules for this group.</Card.Description>
        </Card.Header>
        <Card.Content>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b text-left text-muted-foreground">
                  <th class="pb-2 font-medium">Resource (Object)</th>
                  <th class="pb-2 font-medium">Action</th>
                  <th class="pb-2 font-medium w-10"></th>
                </tr>
              </thead>
              <tbody class="divide-y">
                {#each groupPolicies as p}
                  <tr class="hover:bg-muted/30 transition-colors">
                    <td class="py-2.5"><code class="px-1.5 py-0.5 rounded bg-muted font-mono text-xs">{p[1]}</code></td>
                    <td class="py-2.5"><span class="px-1.5 py-0.5 rounded border border-primary/20 text-primary font-mono text-xs bg-primary/5">{p[2]}</span></td>
                    <td class="py-2.5 text-right">
                      <Button variant="ghost" size="icon-sm" onclick={() => removeRule('p', p)}>
                        <Trash class="h-4 w-4 text-destructive" />
                      </Button>
                    </td>
                  </tr>
                {:else}
                  <tr>
                    <td colspan="3" class="py-4 text-center text-muted-foreground text-xs italic">No permissions assigned.</td>
                  </tr>
                {/each}
                <tr class="bg-muted/30">
                  <td class="py-2 pr-2"><Input bind:value={newP[0]} placeholder="e.g. /api/users or resource_type" class="h-8" /></td>
                  <td class="py-2 pr-2"><Input bind:value={newP[1]} placeholder="e.g. read, write" class="h-8" /></td>
                  <td class="py-2 text-right">
                    <Button size="icon-sm" onclick={addPolicy} disabled={loading || !newP[0] || !newP[1]}><Plus class="h-4 w-4" /></Button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </Card.Content>
      </Card.Root>
    {:else}
      <div class="flex flex-col items-center justify-center h-64 border rounded-xl border-dashed text-muted-foreground">
        <Shield class="h-10 w-10 mb-4 opacity-20" />
        <p>Select or create a group to manage.</p>
      </div>
    {/if}
  </div>
</div>
