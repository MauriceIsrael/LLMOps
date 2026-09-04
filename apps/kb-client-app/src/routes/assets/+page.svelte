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

	function getAssetTypeIcon(type: string): string {
		switch (type?.toLowerCase()) {
			case 'control':
				return '🛡️';
			case 'decision':
			case 'adr':
				return '⚖️';
			case 'pattern':
				return '🧩';
			case 'principle':
				return '🧭';
			case 'template':
				return '📋';
			case 'skill':
				return '🎓';
			default:
				return '📄';
		}
	}

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
		<aside class="w-full lg:w-[420px] shrink-0 border-r border-slate-800/80 bg-slate-950/90 flex flex-col">
			<!-- Filters Section -->
			<div class="p-4 border-b border-slate-800/80 space-y-3">
				<input
					type="text"
					bind:value={searchQuery}
					placeholder="Rechercher par titre ou ID..."
					class="w-full bg-slate-900 border border-slate-800 text-white placeholder-slate-500 rounded-xl px-4 py-2.5 text-xs focus:outline-none focus:border-emerald-500 font-mono shadow-inner"
				/>

				<div class="grid grid-cols-2 gap-2.5">
					<div class="min-w-0">
						<label for="type-filter" class="block text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Type d'actif</label>
						<select
							id="type-filter"
							bind:value={selectedType}
							class="w-full bg-slate-900 border border-slate-800 text-slate-200 text-xs rounded-xl px-2.5 py-2 focus:outline-none focus:border-emerald-500 cursor-pointer truncate"
						>
							<option value="all">Tous types</option>
							<option value="decision">ADR (Décision)</option>
							<option value="principle">Principe</option>
							<option value="pattern">Pattern</option>
							<option value="template">Modèle</option>
							<option value="control">🛡️ Normes / Contrôles</option>
						</select>
					</div>

					<div class="min-w-0">
						<label for="domain-filter" class="block text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Domaine</label>
						<select
							id="domain-filter"
							bind:value={selectedDomainFilter}
							class="w-full bg-slate-900 border border-slate-800 text-slate-200 text-xs rounded-xl px-2.5 py-2 focus:outline-none focus:border-emerald-500 cursor-pointer truncate"
						>
							<option value="all">Tous domaines</option>
							{#each domains.filter((d) => d !== 'all') as dom}
								<option value={dom}>{dom}</option>
							{/each}
						</select>
					</div>
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
							type="button"
							onclick={() => loadAssetContent(item.id)}
							class="w-full text-left p-3.5 rounded-xl border transition-all space-y-1.5 cursor-pointer {selectedId === item.id ? 'bg-emerald-950/30 border-emerald-500/50 shadow-md text-white' : 'bg-slate-900/40 border-slate-800/80 hover:bg-slate-900 text-slate-300'}"
						>
							<div class="flex items-center justify-between gap-2">
								<span class="font-mono text-xs font-bold {item.type === 'control' ? 'text-amber-400' : 'text-emerald-400'} flex items-center gap-1.5 min-w-0">
									<span class="text-sm shrink-0" aria-hidden="true">{getAssetTypeIcon(item.type)}</span>
									<span class="truncate">{item.id}</span>
								</span>
								<span class="text-[10px] uppercase font-semibold tracking-wider px-1.5 py-0.5 rounded {item.type === 'control' ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-800 text-slate-400'} shrink-0">
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

						<!-- Implemented Regulatory Controls (When viewing Pattern / Decision / Principle) -->
						{#if activeAsset.implements_controls && activeAsset.implements_controls.length > 0}
							<div class="mt-5 pt-4 border-t border-slate-800/80">
								<div class="text-xs font-bold text-emerald-400 flex items-center gap-2 mb-2.5">
									<span class="p-1 bg-emerald-500/20 rounded">🛡️</span>
									<span>Exigences Réglementaires Couvertes ({activeAsset.implements_controls.length})</span>
								</div>
								<div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
									{#each activeAsset.implements_controls as ctrl}
										<button
											type="button"
											onclick={() => loadAssetContent(ctrl.id)}
											class="p-2.5 bg-emerald-950/30 hover:bg-emerald-900/50 border border-emerald-500/30 hover:border-emerald-400 rounded-xl text-left transition-all cursor-pointer group shadow-sm"
										>
											<div class="flex items-center justify-between gap-2 mb-1">
												<span class="font-mono text-xs font-bold text-emerald-300 group-hover:text-emerald-200">{ctrl.id}</span>
												<span class="px-1.5 py-0.2 bg-emerald-500/20 text-[10px] font-semibold text-emerald-300 rounded uppercase">{ctrl.framework}</span>
											</div>
											<div class="text-xs text-slate-300 line-clamp-2 leading-snug">{ctrl.title}</div>
										</button>
									{/each}
								</div>
							</div>
						{/if}

						<!-- Implementing Architecture Patterns (When viewing a Regulatory Control) -->
						{#if activeAsset.implemented_by && activeAsset.implemented_by.length > 0}
							<div class="mt-5 pt-4 border-t border-slate-800/80">
								<div class="text-xs font-bold text-indigo-400 flex items-center gap-2 mb-2.5">
									<span class="p-1 bg-indigo-500/20 rounded">🏛️</span>
									<span>Motifs d'Architecture Implémentant ce Contrôle ({activeAsset.implemented_by.length})</span>
								</div>
								<div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
									{#each activeAsset.implemented_by as impl}
										<button
											type="button"
											onclick={() => loadAssetContent(impl.id)}
											class="p-2.5 bg-indigo-950/30 hover:bg-indigo-900/50 border border-indigo-500/30 hover:border-indigo-400 rounded-xl text-left transition-all cursor-pointer group shadow-sm"
										>
											<div class="flex items-center justify-between gap-2 mb-1">
												<span class="font-mono text-xs font-bold text-indigo-300 group-hover:text-indigo-200">{impl.id}</span>
												<span class="px-1.5 py-0.2 bg-indigo-500/20 text-[10px] font-semibold text-indigo-300 rounded uppercase">{impl.type}</span>
											</div>
											<div class="text-xs text-slate-300 line-clamp-2 leading-snug">{impl.title}</div>
										</button>
									{/each}
								</div>
							</div>
						{/if}
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
