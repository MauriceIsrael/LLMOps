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

	let readerScrollContainer = $state<HTMLElement | null>(null);

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
		if (readerScrollContainer) {
			readerScrollContainer.scrollTop = 0;
		}
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

	function resetFilters() {
		searchQuery = '';
		selectedType = 'all';
		selectedDomainFilter = 'all';
	}
</script>

<div class="h-[calc(100vh-4rem)] bg-slate-950 text-slate-100 flex flex-col font-sans overflow-hidden">
	<!-- Top App Header (Pinned at top, shrink-0) -->
	<header class="shrink-0 px-6 py-3.5 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur flex items-center justify-between gap-4 z-20">
		<div class="flex items-center gap-3">
			<span class="p-1.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-xl text-base">📚</span>
			<div>
				<h1 class="text-lg font-black text-white leading-tight">
					Catalogue & Lecteur d'Actifs KB
				</h1>
				<p class="text-[11px] text-slate-400">
					ADRs, Principes, Patterns, Modèles & Normes réglementaires (NIS 2, SecNumCloud, ISO 27001, 3GPP)
				</p>
			</div>
		</div>

		<!-- Environment Badge -->
		<div class="px-3 py-1 bg-slate-900/80 border border-emerald-500/30 text-emerald-400 rounded-lg text-xs font-mono font-medium flex items-center gap-2 shadow-sm shrink-0">
			<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
			<span>{kbConfig.activeEnv.name}</span>
		</div>
	</header>

	<!-- Main Workspace Split View (Exact fill of remaining viewport height) -->
	<div class="flex-1 min-h-0 flex flex-col lg:flex-row overflow-hidden">

		<!-- Left Sidebar: Catalogue & Filters (Fixed width, independent scroll) -->
		<aside class="w-full lg:w-[420px] shrink-0 border-r border-slate-800/80 bg-slate-950 flex flex-col min-h-0 h-full">

			<!-- Sticky Filters Section (Never scrolls away) -->
			<div class="shrink-0 p-3.5 border-b border-slate-800/80 space-y-2.5 bg-slate-950/95 backdrop-blur z-10 shadow-sm">
				<div class="relative">
					<input
						type="text"
						bind:value={searchQuery}
						placeholder="Rechercher par titre ou ID..."
						class="w-full bg-slate-900 border border-slate-800 text-white placeholder-slate-500 rounded-xl pl-8 pr-4 py-2 text-xs focus:outline-none focus:border-emerald-500 font-mono shadow-inner transition-colors"
					/>
					<span class="absolute left-2.5 top-2.5 text-xs text-slate-500 pointer-events-none">🔍</span>
					{#if searchQuery}
						<button
							type="button"
							onclick={() => (searchQuery = '')}
							class="absolute right-2.5 top-2 text-xs text-slate-400 hover:text-white cursor-pointer"
							title="Effacer la recherche"
						>
							✕
						</button>
					{/if}
				</div>

				<div class="grid grid-cols-2 gap-2">
					<div class="min-w-0">
						<label for="type-filter" class="block text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Type</label>
						<select
							id="type-filter"
							bind:value={selectedType}
							class="w-full bg-slate-900 border border-slate-800 text-slate-200 text-xs rounded-xl px-2.5 py-1.5 focus:outline-none focus:border-emerald-500 cursor-pointer truncate"
						>
							<option value="all">Tous ({assets.length})</option>
							<option value="decision">ADR ({assets.filter((a) => a.type === 'decision').length})</option>
							<option value="pattern">Pattern ({assets.filter((a) => a.type === 'pattern').length})</option>
							<option value="principle">Principe ({assets.filter((a) => a.type === 'principle').length})</option>
							<option value="template">Modèle ({assets.filter((a) => a.type === 'template').length})</option>
							<option value="control">🛡️ Normes ({assets.filter((a) => a.type === 'control').length})</option>
						</select>
					</div>

					<div class="min-w-0">
						<label for="domain-filter" class="block text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Domaine</label>
						<select
							id="domain-filter"
							bind:value={selectedDomainFilter}
							class="w-full bg-slate-900 border border-slate-800 text-slate-200 text-xs rounded-xl px-2.5 py-1.5 focus:outline-none focus:border-emerald-500 cursor-pointer truncate"
						>
							<option value="all">Tous domaines</option>
							{#each domains.filter((d) => d !== 'all') as dom}
								<option value={dom}>{dom}</option>
							{/each}
						</select>
					</div>
				</div>

				<!-- Filter results count & reset link -->
				<div class="flex items-center justify-between text-[11px] text-slate-400 px-0.5">
					<span>
						<strong class="text-emerald-400 font-mono">{filteredAssets.length}</strong> actif{filteredAssets.length > 1 ? 's' : ''} listé{filteredAssets.length > 1 ? 's' : ''}
					</span>
					{#if searchQuery || selectedType !== 'all' || selectedDomainFilter !== 'all'}
						<button
							type="button"
							onclick={resetFilters}
							class="text-[10px] text-emerald-400 hover:underline cursor-pointer font-medium"
						>
							Réinitialiser les filtres
						</button>
					{/if}
				</div>
			</div>

			<!-- Independent Scrollable Assets List -->
			<div class="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-1.5 divide-y divide-transparent">
				{#if loadingList}
					<div class="p-8 text-center text-slate-500 text-xs flex flex-col items-center gap-2">
						<span class="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></span>
						<span>Chargement du catalogue...</span>
					</div>
				{:else if filteredAssets.length === 0}
					<div class="p-8 text-center text-slate-500 text-xs space-y-2">
						<div>Aucun actif ne correspond à ces critères.</div>
						<button
							type="button"
							onclick={resetFilters}
							class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs"
						>
							Effacer les filtres
						</button>
					</div>
				{:else}
					{#each filteredAssets as item (item.id)}
						<button
							type="button"
							onclick={() => loadAssetContent(item.id)}
							class="w-full text-left p-2.5 rounded-xl border transition-all space-y-1 cursor-pointer {selectedId === item.id ? 'bg-emerald-950/40 border-emerald-500 text-white shadow-md ring-1 ring-emerald-500/40' : 'bg-slate-900/40 border-slate-800/80 hover:bg-slate-900 text-slate-300'}"
						>
							<div class="flex items-center justify-between gap-2">
								<span class="font-mono text-xs font-bold {item.type === 'control' ? 'text-amber-400' : 'text-emerald-400'} flex items-center gap-1.5 min-w-0">
									<span class="text-sm shrink-0" aria-hidden="true">{getAssetTypeIcon(item.type)}</span>
									<span class="truncate">{item.id}</span>
								</span>
								<span class="text-[9px] uppercase font-semibold tracking-wider px-1.5 py-0.5 rounded {item.type === 'control' ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-800 text-slate-400'} shrink-0">
									{item.type}
								</span>
							</div>

							<div class="text-xs font-semibold leading-snug line-clamp-2">
								{item.title}
							</div>

							<div class="text-[10px] text-slate-500 font-mono truncate">
								#{item.domain}
							</div>
						</button>
					{/each}
				{/if}
			</div>
		</aside>

		<!-- Right Main Reader Canvas (Independent scroll, resets to top on asset change) -->
		<main bind:this={readerScrollContainer} class="flex-1 min-h-0 overflow-y-auto p-6 md:p-8 bg-slate-950">
			{#if loadingAsset}
				<div class="h-full min-h-[300px] flex flex-col items-center justify-center text-slate-400 text-xs gap-3">
					<span class="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></span>
					<span>Chargement du contenu de l'actif <strong class="font-mono text-emerald-400">{selectedId}</strong>...</span>
				</div>
			{:else if activeAsset}
				<div class="max-w-4xl mx-auto space-y-6 pb-12">
					<!-- Top Metadata Card -->
					<div class="p-6 bg-slate-900/90 border border-slate-800 rounded-2xl shadow-xl">
						<div class="flex flex-wrap items-center gap-2.5 mb-4">
							<span class="px-3 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-mono font-bold">
								{activeAsset.id}
							</span>
							<span class="px-2.5 py-1 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-lg text-xs font-semibold uppercase tracking-wider">
								{activeAsset.type}
							</span>
							<span class="px-2.5 py-1 bg-purple-500/10 text-purple-400 border border-purple-500/20 rounded-lg text-xs font-medium">
								Domaine: {activeAsset.domain}
							</span>
							<span class="px-2.5 py-1 bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded-lg text-xs font-medium">
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

						<!-- Cross-Navigation: Implemented Regulatory Controls (When viewing Pattern / Decision / Principle) -->
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

						<!-- Cross-Navigation: Implementing Architecture Patterns (When viewing a Regulatory Control) -->
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
