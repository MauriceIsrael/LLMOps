<script lang="ts">
  import * as Dialog from '$lib/components/ui/dialog';
  import { Button } from '$lib/components/ui/button';
  import { Input } from '$lib/components/ui/input';
  import { Label } from '$lib/components/ui/label';
  import * as Select from '$lib/components/ui/select';
  import { t } from 'svelte-i18n';
  import { toastSuccess, toastError } from '$lib/toast/index.svelte';
  import { apiFetch } from '$lib/api/fetch';
  import { invalidateAll } from '$app/navigation';

  let { open = $bindable(), user = null } = $props();

  let name = $state(user?.name ?? '');
  let email = $state(user?.email ?? '');
  let password = $state('');
  let role = $state(user?.role ?? 'user');
  let attributes = $state(user?.attributes ?? {});
  let loading = $state(false);

  async function handleSubmit() {
    // Basic validation
    if (!name || name.length < 2) {
      toastError('Name must be at least 2 characters');
      return;
    }
    if (!email || !email.includes('@')) {
      toastError('Please enter a valid email address');
      return;
    }
    if (!user && (!password || password.length < 6)) {
      toastError('Password must be at least 6 characters');
      return;
    }

    loading = true;
    const method = user ? 'PATCH' : 'POST';
    const body = user 
      ? { id: user.id, name, role, attributes }
      : { name, email, password: password || undefined, role, attributes };

    const { data, error } = await apiFetch('/api/admin/users', {
      method,
      body
    });

    loading = true; // Still loading while processing response
    if (!error) {
      toastSuccess(user ? 'User updated' : 'User created');
      open = false;
      invalidateAll();
    } else {
      toastError(error.message || 'Failed to save user');
    }
    loading = false;
  }

  const roleOptions = [
    { value: 'user', label: 'User' },
    { value: 'admin', label: 'Admin' }
  ];
</script>

<Dialog.Root bind:open>
  <Dialog.Content class="sm:max-w-[425px]">
    <Dialog.Header>
      <Dialog.Title>{user ? 'Edit User' : 'Add User'}</Dialog.Title>
      <Dialog.Description>
        Fill in the details for the user account.
      </Dialog.Description>
    </Dialog.Header>
    <div class="grid gap-4 py-4">
      <div class="grid grid-cols-4 items-center gap-4">
        <Label for="name" class="text-right">Name</Label>
        <Input id="name" bind:value={name} class="col-span-3" />
      </div>
      <div class="grid grid-cols-4 items-center gap-4">
        <Label for="email" class="text-right">Email</Label>
        <Input id="email" type="email" bind:value={email} disabled={!!user} class="col-span-3" />
      </div>
      {#if !user}
        <div class="grid grid-cols-4 items-center gap-4">
          <Label for="password" class="text-right">Password</Label>
          <div class="col-span-3 space-y-1">
            <Input id="password" type="password" bind:value={password} placeholder="••••••••" />
            <p class="text-[0.8rem] text-muted-foreground">
              Minimum 6 characters required.
            </p>
          </div>
        </div>
      {/if}
      <div class="grid grid-cols-4 items-center gap-4">
        <Label class="text-right">Role</Label>
        <div class="col-span-3">
          <Select.Root type="single" bind:value={role}>
            <Select.Trigger class="w-full">
              {roleOptions.find(o => o.value === role)?.label ?? 'Select role'}
            </Select.Trigger>
            <Select.Content>
              {#each roleOptions as option}
                <Select.Item value={option.value}>{option.label}</Select.Item>
              {/each}
            </Select.Content>
          </Select.Root>
        </div>
      </div>
    </div>
    <Dialog.Footer>
      <Button type="submit" onclick={handleSubmit} disabled={loading}>
        {loading ? 'Saving...' : 'Save changes'}
      </Button>
    </Dialog.Footer>
  </Dialog.Content>
</Dialog.Root>
