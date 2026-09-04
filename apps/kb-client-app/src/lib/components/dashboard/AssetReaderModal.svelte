<script lang="ts">
	import type { VolumeKpiData } from '$lib/server/kb-adapter';

	let { open = $bindable(false), initialId = 'ADR-0001' }: { open: boolean; initialId?: string } = $props();

	let searchId = $state(initialId);
	let loading = $state(false);
	let assetData = $state<any | null>(null);
	let error = $state<string | null>(null);

	const availableAssets = [
		'ADR-0001', 'ADR-0002', 'ADR-0003', 'ADR-0004', 'ADR-0005',
		'ADR-0006', 'ADR-0007', 'ADR-0008', 'ADR-0009', 'ADR-0010',
		'ADR-0011', 'ADR-0012', 'ADR-0013', 'TPL-getting-started', 'BLU-hla-mcx'
	];

	async function fetchAsset(id: string) {
		if (!id) return;
		loading = true;
		error = null;
		try {
			const res = await fetch(`/api/kb/asset?id=${encodeURIComponent(id)}`);
			if (res.ok) {
				const json = await res.json();
				if (json.status === 'ok') {
					assetData = json.data;
				} else {
					error = `Actif '${id}' non trouvé dans la base KB locale.`;
					assetData = null;
				}
			}
		} catch {
			error = 'Erreur de connexion au serveur KB.';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		if (open && searchId) {
			fetchAsset(searchId);
		}
	});

	function handleSubmit(e: Event) {
		e.preventDefault();
		fetchAsset(searchId);
	}
</script>

{#if open}
	<!-- Modal Backdrop -->
	<div class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
		<div class="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
			
			<!-- Modal Header & Search Form -->
			<div class="p-6 border-b border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 bg-slate-950/40">
				<div>
					<h2 class="text-xl font-bold text-white flex items-center gap-2">
						<span class="p-1 bg-emerald-500/20 text-emerald-400 rounded">📄</span>
						Lecteur d'Actif KB Architecture
					</h2>
					<p class="text-xs text-slate-400">Consulter le contenu complet et le frontmatter d'un document d'architecture</p>
				</div>

				<button
					onclick={() => (open = false)}
					class="text-slate-400 hover:text-white transition-colors text-xl font-bold px-2 py-1 rounded-lg hover:bg-slate-800"
				>
					✕
				</button>
			</div>

			<!-- Quick Selector & Input Form -->
			<div class="p-4 bg-slate-950/80 border-b border-slate-800/80 flex flex-col sm:flex-row items-center gap-3">
				<form onsubmit={handleSubmit} class="flex items-center gap-2 flex-1 w-full">
					<input
						type="text"
						bind:value={searchId}
						placeholder="Saisir l'identifiant (ex: ADR-0001, ADR-0005...)"
						class="flex-1 bg-slate-900 border border-slate-700 text-white rounded-xl px-4 py-2 text-sm focus:outline-none focus:border-emerald-500 font-mono"
					/>
					<button
						type="submit"
						class="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs rounded-xl transition-all shadow-md"
					>
						Rechercher
					</button>
				</form>

				<div class="flex items-center gap-2 w-full sm:w-auto">
					<span class="text-xs text-slate-400 whitespace-nowrap">Sélection rapide:</span>
					<select
						bind:value={searchId}
						onchange={() => fetchAsset(searchId)}
						class="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl px-3 py-2 focus:outline-none font-mono"
					>
						{#each availableAssets as id}
							<option value={id}>{id}</option>
						{/each}
					</select>
				</div>
			</div>

			<!-- Modal Body (Content Reader) -->
			<div class="p-6 overflow-y-auto flex-1 text-slate-200 text-sm">
				{#if loading}
					<div class="py-12 text-center text-slate-400">Chargement du document {searchId}...</div>
				{:else if error}
					<div class="p-4 bg-rose-500/10 border border-rose-500/30 text-rose-300 rounded-xl text-xs">{error}</div>
				{:else if assetData}
					<!-- Metadata Badges Bar -->
					<div class="flex flex-wrap items-center gap-2 mb-6 pb-4 border-b border-slate-800">
						<span class="px-3 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-xs font-mono font-bold">
							{assetData.id}
						</span>
						<span class="px-2.5 py-1 bg-blue-500/10 text-blue-400 rounded-lg text-xs font-medium uppercase tracking-wider">
							{assetData.type}
						</span>
						<span class="px-2.5 py-1 bg-purple-500/10 text-purple-400 rounded-lg text-xs font-medium">
							Domaine: {assetData.domain}
						</span>
						<span class="px-2.5 py-1 bg-amber-500/10 text-amber-400 rounded-lg text-xs font-medium">
							Confiance: {assetData.confidence}
						</span>
						<span class="ml-auto text-xs text-slate-500 font-mono">
							Dernière révision: {assetData.last_reviewed}
						</span>
					</div>

					<h1 class="text-2xl font-extrabold text-white mb-4 leading-tight">
						{assetData.title}
					</h1>

					<!-- Cross Navigation: Implemented Controls -->
					{#if assetData.implements_controls && assetData.implements_controls.length > 0}
						<div class="mb-6 p-4 bg-emerald-950/20 border border-emerald-500/30 rounded-xl">
							<div class="text-xs font-bold text-emerald-400 flex items-center gap-1.5 mb-2.5">
								<span>🛡️</span> Exigences Réglementaires Couvertes ({assetData.implements_controls.length})
							</div>
							<div class="flex flex-wrap gap-2">
								{#each assetData.implements_controls as ctrl}
									<button
										type="button"
										onclick={() => { searchId = ctrl.id; fetchAsset(ctrl.id); }}
										class="px-3 py-1.5 bg-emerald-900/40 hover:bg-emerald-800/60 border border-emerald-500/40 text-emerald-200 hover:text-white rounded-lg text-xs font-mono transition-all flex items-center gap-2 cursor-pointer"
									>
										<span class="font-bold">{ctrl.id}</span>
										<span class="text-slate-300 font-sans border-l border-emerald-500/30 pl-2 line-clamp-1">{ctrl.title}</span>
									</button>
								{/each}
							</div>
						</div>
					{/if}

					<!-- Cross Navigation: Implementing Architecture Patterns -->
					{#if assetData.implemented_by && assetData.implemented_by.length > 0}
						<div class="mb-6 p-4 bg-indigo-950/20 border border-indigo-500/30 rounded-xl">
							<div class="text-xs font-bold text-indigo-400 flex items-center gap-1.5 mb-2.5">
								<span>🏛️</span> Motifs d'Architecture Implémentant ce Contrôle ({assetData.implemented_by.length})
							</div>
							<div class="flex flex-wrap gap-2">
								{#each assetData.implemented_by as impl}
									<button
										type="button"
										onclick={() => { searchId = impl.id; fetchAsset(impl.id); }}
										class="px-3 py-1.5 bg-indigo-900/40 hover:bg-indigo-800/60 border border-indigo-500/40 text-indigo-200 hover:text-white rounded-lg text-xs font-mono transition-all flex items-center gap-2 cursor-pointer"
									>
										<span class="font-bold">{impl.id}</span>
										<span class="text-slate-300 font-sans border-l border-indigo-500/30 pl-2 line-clamp-1">{impl.title}</span>
										<span class="px-1 bg-indigo-500/20 text-[10px] uppercase rounded font-sans">{impl.type}</span>
									</button>
								{/each}
							</div>
						</div>
					{/if}

					<!-- Parsed Markdown Body -->
					<div class="prose prose-invert max-w-none space-y-4 text-slate-300 leading-relaxed font-sans text-sm whitespace-pre-wrap">
						{assetData.body}
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}
