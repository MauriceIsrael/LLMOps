<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import { Button } from '$lib/components/ui/button';
  import Lightbulb from 'lucide-svelte/icons/lightbulb';
  import Trash from 'lucide-svelte/icons/trash';
  import MessageSquare from 'lucide-svelte/icons/message-square';
  import Calendar from 'lucide-svelte/icons/calendar';
  import User from 'lucide-svelte/icons/user';
  import { t } from 'svelte-i18n';
  import { toast } from '$lib/toast/index.svelte';
  
  let { data } = $props();

  let title = $state('');
  let content = $state('');
  let loading = $state(false);

  const session = $derived(data.session);

  function formatDate(dateStr: string | Date) {
    const d = new Date(dateStr);
    return d.toLocaleDateString('fr-FR', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }
</script>

<svelte:head>
  <title>Boîte à Idées — Template App</title>
</svelte:head>

<div class="flex-1 space-y-6 p-4 md:p-8 pt-6">
  
  <!-- Header -->
  <div class="flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Lightbulb class="h-5 w-5" />
      </div>
      <div>
        <h1 class="text-2xl font-bold tracking-tight">Boîte à Idées & Suggestions</h1>
        <p class="text-sm text-muted-foreground">Laissez vos propositions, votes ou commentaires pour faire évoluer l'application.</p>
      </div>
    </div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
    
    <!-- Submit Idea Form (4 Cols) -->
    <div class="lg:col-span-4 space-y-6">
      <Card.Root>
        <Card.Header>
          <Card.Title class="text-base flex items-center gap-2">
            <MessageSquare class="h-4 w-4 text-primary" />
            Proposer une idée
          </Card.Title>
          <Card.Description>Partagez vos suggestions d'améliorations ou de nouvelles fonctionnalités.</Card.Description>
        </Card.Header>
        <Card.Content>
          <form method="POST" action="?/createIdea" class="space-y-4">
            <div class="space-y-2">
              <label for="title" class="text-xs font-bold uppercase tracking-wider text-muted-foreground">Titre de l'idée</label>
              <input
                id="title"
                name="title"
                type="text"
                bind:value={title}
                placeholder="Ex: Ajouter un export PDF..."
                required
                class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>

            <div class="space-y-2">
              <label for="content" class="text-xs font-bold uppercase tracking-wider text-muted-foreground">Description détaillée</label>
              <textarea
                id="content"
                name="content"
                bind:value={content}
                placeholder="Décrivez votre proposition, son utilité et comment l'implémenter..."
                rows="4"
                required
                class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
              ></textarea>
            </div>

            <Button type="submit" class="w-full mt-2" disabled={loading}>
              Soumettre ma proposition
            </Button>
          </form>
        </Card.Content>
      </Card.Root>
    </div>

    <!-- Ideas List (8 Cols) -->
    <div class="lg:col-span-8 space-y-4">
      <h2 class="text-lg font-bold tracking-tight flex items-center gap-2">
        <Lightbulb class="h-4 w-4 text-violet-400" />
        Idées Partagées ({data.ideas?.length || 0})
      </h2>

      {#if !data.ideas || data.ideas.length === 0}
        <Card.Root class="border-dashed">
          <Card.Content class="flex flex-col items-center justify-center p-12 text-center text-muted-foreground">
            <Lightbulb class="h-10 w-10 text-muted-foreground/40 mb-3 animate-pulse" />
            <p class="font-medium text-sm">Aucune idée n'a encore été proposée.</p>
            <p class="text-xs mt-1">Soyez le premier à partager vos suggestions !</p>
          </Card.Content>
        </Card.Root>
      {:else}
        <div class="grid grid-cols-1 gap-4">
          {#each data.ideas as idea}
            <Card.Root>
              <Card.Header class="pb-3">
                <div class="flex items-start justify-between gap-4">
                  <div>
                    <Card.Title class="text-base font-bold text-foreground leading-snug">{idea.title}</Card.Title>
                    <div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1.5 text-xs text-muted-foreground">
                      <span class="flex items-center gap-1">
                        <User class="h-3 w-3" />
                        {idea.authorName || 'Utilisateur'}
                      </span>
                      <span class="flex items-center gap-1">
                        <Calendar class="h-3 w-3" />
                        {formatDate(idea.createdAt)}
                      </span>
                    </div>
                  </div>

                  <!-- Only show delete button if author or admin -->
                  {#if session && (session.user.role === 'admin' || session.user.id === idea.authorId)}
                    <form method="POST" action="?/deleteIdea">
                      <input type="hidden" name="id" value={idea.id} />
                      <Button variant="ghost" size="icon" type="submit" class="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10 shrink-0">
                        <Trash class="h-4 w-4" />
                      </Button>
                    </form>
                  {/if}
                </div>
              </Card.Header>
              <Card.Content>
                <p class="text-sm text-foreground/80 leading-relaxed whitespace-pre-wrap">{idea.content}</p>
              </Card.Content>
            </Card.Root>
          {/each}
        </div>
      {/if}
    </div>

  </div>
</div>
