<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { kbConfig } from '$lib/stores/kb-config.svelte';

	let assets = $state<any[]>([]);
	let selectedId = $state<string>('ADR-0001');
	let activeAsset = $state<any | null>(null);
	let loadingList = $state(true);
	let loadingAsset = $state(false);

	let searchQuery = $state('');
	let selectedType = $state<string>('all');
	let selectedDomainFilter = $state<string>('all');

	onMount(async () => {
		const urlId = $page.url.searchParams.get('id');
		if (urlId) {
			selectedId = urlId;
		}

		try {
			const res = await fetch(
				`/api/kb/graph?type=${kbConfig.activeEnv.type}&endpoint=${encodeURIComponent(kbConfig.activeEnv.endpoint)}`
			);
			if (res.ok) {
				const json = await res.json();
				assets = json.data.nodes || [];
			}
		} catch (e) {
			console.error('Failed to load assets list', e);
		} finally {
			loadingList = false;
		}

		if (selectedId) {
			loadAssetContent(selectedId);
		}
	});

	async function loadAssetContent(id: string) {
		selectedId = id;
		loadingAsset = true;
		try {
			const res = await fetch(`/api/kb/asset?id=${encodeURIComponent(id)}`);
			if (res.ok) {
				const json = await res.json();
				if (json.status === 'ok') {
					activeAsset = json.data;
				}
			}
		} catch (e) {
			console.error('Failed to load asset content', e);
		} finally {
			loadingAsset = false;
		}
	}

	let domains = $derived([
		'all',
		...Array.from(new Set(assets.map((a) => a.domain).filter(Boolean)))
	]);

	let filteredAssets = $derived(
		assets.filter((a) => {
			const matchesSearch =
				!searchQuery ||
				a.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
				a.title.toLowerCase().includes(searchQuery.toLowerCase());
			const matchesType = selectedType === 'all' || a.type === selectedType;
			const matchesDomain =
				selectedDomainFilter === 'all' || a.domain === selectedDomainFilter;
			return matchesSearch && matchesType && matchesDomain;
		})
	);
</script>

<div class="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
	<!-- Top App Header -->
	<header class="p-6 border-b border-slate-800 bg-slate-900/60 backdrop-blur flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
		<div>
			<h1 class="text-2xl font-black text-white flex items-center gap-3">
				<span class="p-1.5 bg-emerald-500/20 text-emerald-400 rounded-xl">📚</span>
				Catalogue & Lecteur d'Actifs KB
			</h1>
			<p class="text-xs text-slate-400">Consultation des documents d'architecture (ADRs, Principes, Patterns, Modèles)</p>
		</div>

		<!-- Environment Switcher Badge -->
		<div class="px-3 py-1.5 bg-slate-900 border border-emerald-500/30 text-emerald-400 rounded-xl text-xs font-mono font-medium flex items-center gap-2">
			<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
			{kbConfig.activeEnv.name}
		</div>
	</header>

	<!-- Main Workspace Split View -->
	<div class="flex-1 flex flex-col lg:flex-row overflow-hidden">
		<!-- Left Sidebar Catalogue & Filters -->
		<aside class="w-full lg:w-96 border-r border-slate-800/80 bg-slate-950/90 flex flex-col">
			<!-- Filters Section -->
			<div class="p-4 border-b border-slate-800/80 space-y-3">
				<input
					type="text"
					bind:value={searchQuery}
					placeholder="Rechercher par titre ou ID..."
					class="w-full bg-slate-900 border border-slate-800 text-white placeholder-slate-500 rounded-xl px-4 py-2 text-xs focus:outline-none focus:border-emerald-500 font-mono"
				/>

				<div class="flex items-center gap-2">
					<select
						bind:value={selectedDomainFilter}
						class="flex-1 bg-slate-900 border border-slate-800 text-slate-300 text-xs rounded-xl px-3 py-2 focus:outline-none"
					>
						<option value="all">Tous les domaines</option>
						{#each domains.filter((d) => d !== 'all') as dom}
							<option value={dom}>{dom}</option>
						{/each}
					</select>

					<select
						bind:value={selectedType}
						class="bg-slate-900 border border-slate-800 text-slate-300 text-xs rounded-xl px-3 py-2 focus:outline-none"
					>
						<option value="all">Tous types</option>
						<option value="decision">ADR (Décision)</option>
						<option value="principle">Principe</option>
						<option value="pattern">Pattern</option>
						<option value="template">Modèle</option>
					</select>
				</div>
			</div>

			<!-- Assets List -->
			<div class="flex-1 overflow-y-auto p-3 space-y-2">
				{#if loadingList}
					<div class="p-8 text-center text-slate-500 text-xs">Chargement du catalogue...</div>
				{:else if filteredAssets.length === 0}
					<div class="p-8 text-center text-slate-500 text-xs">Aucun actif ne correspond aux filtres.</div>
				{:else}
					{#each filteredAssets as item (item.id)}
						<button
							onclick={() => loadAssetContent(item.id)}
							class="w-full text-left p-3.5 rounded-xl border transition-all flex flex-col gap-1.5 {selectedId === item.id
								? 'bg-emerald-500/10 border-emerald-500/40 text-white shadow-lg'
								: 'bg-slate-900/40 border-slate-800/80 text-slate-300 hover:bg-slate-900 hover:border-slate-700'}"
						>
							<div class="flex items-center justify-between gap-2">
								<span class="px-2 py-0.5 bg-slate-800 text-emerald-400 font-mono text-[11px] font-bold rounded">
									{item.id}
								</span>
								<span class="text-[10px] uppercase font-semibold tracking-wider text-slate-400">
									{item.type}
								</span>
							</div>

							<div class="text-xs font-semibold leading-snug line-clamp-2">
								{item.title}
							</div>

							<div class="text-[11px] text-slate-400 font-medium truncate">
								{item.domain}
							</div>
						</button>
					{/each}
				{/if}
			</div>
		</aside>

		<!-- Right Main Reader Canvas -->
		<main class="flex-1 overflow-y-auto p-6 md:p-10 bg-slate-950">
			{#if loadingAsset}
				<div class="h-full flex items-center justify-center text-slate-400 text-sm font-medium">
					Chargement du contenu de l'actif {selectedId}...
				</div>
			{:else if activeAsset}
				<div class="max-w-4xl mx-auto space-y-6">
					<!-- Top Metadata Card -->
					<div class="p-6 bg-slate-900/90 border border-slate-800 rounded-2xl shadow-xl">
						<div class="flex flex-wrap items-center gap-3 mb-4">
							<span class="px-3 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-mono font-bold">
								{activeAsset.id}
							</span>
							<span class="px-2.5 py-1 bg-blue-500/10 text-blue-400 rounded-lg text-xs font-semibold uppercase tracking-wider">
								{activeAsset.type}
							</span>
							<span class="px-2.5 py-1 bg-purple-500/10 text-purple-400 rounded-lg text-xs font-medium">
								Domaine: {activeAsset.domain}
							</span>
							<span class="px-2.5 py-1 bg-amber-500/10 text-amber-400 rounded-lg text-xs font-medium">
								Confiance: {activeAsset.confidence}
							</span>
						</div>

						<h2 class="text-2xl font-black text-white mb-4 leading-tight">
							{activeAsset.title}
						</h2>

						<div class="grid grid-cols-2 sm:grid-cols-3 gap-4 pt-4 border-t border-slate-800 text-xs text-slate-400">
							<div>
								<span class="block text-slate-500">Statut</span>
								<span class="font-medium text-slate-200 uppercase">{activeAsset.status}</span>
							</div>
							<div>
								<span class="block text-slate-500">Responsable</span>
								<span class="font-medium text-slate-200">{activeAsset.owner}</span>
							</div>
							<div>
								<span class="block text-slate-500">Dernière révision</span>
								<span class="font-mono text-slate-200">{activeAsset.last_reviewed}</span>
							</div>
						</div>
					</div>

					<!-- Markdown Document Reader Card -->
					<div class="p-8 bg-slate-900/40 border border-slate-800/80 rounded-2xl shadow-xl">
						<div class="prose prose-invert max-w-none space-y-4 text-slate-300 leading-relaxed font-sans text-sm whitespace-pre-wrap">
							{activeAsset.body}
						</div>
					</div>
				</div>
			{/if}
		</main>
	</div>
</div>
