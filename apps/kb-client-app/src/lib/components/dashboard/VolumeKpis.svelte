<script lang="ts">
	import type { VolumeKpiData } from '$lib/server/kb-adapter';

	let { data }: { data: VolumeKpiData | null } = $props();

	let totalAssets = $derived(
		data?.volume_by_type?.reduce((acc, curr) => acc + curr.count, 0) ?? 0
	);
	let activeAssets = $derived(
		data?.status_breakdown?.find((s) => s.status === 'active')?.count ?? 0
	);
	let supersededAssets = $derived(
		data?.status_breakdown?.find((s) => s.status === 'superseded')?.count ?? 0
	);
	let highConfidenceCount = $derived(
		data?.confidence_breakdown?.find((c) => c.confidence === 'high')?.count ?? 0
	);
</script>

<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
	<!-- Total Assets -->
	<div class="p-5 bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl shadow-lg hover:border-emerald-500/50 transition-all">
		<div class="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
			<span>Actifs d'Architecture</span>
			<span class="p-1.5 bg-emerald-500/10 text-emerald-400 rounded-lg">📚</span>
		</div>
		<div class="text-3xl font-extrabold text-white mb-1">{totalAssets}</div>
		<div class="text-xs text-slate-400">
			<span class="text-emerald-400 font-medium">100%</span> cartographiés en LadybugDB
		</div>
	</div>

	<!-- Active / Superseded Ratio -->
	<div class="p-5 bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl shadow-lg hover:border-blue-500/50 transition-all">
		<div class="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
			<span>Statut & Antériorité</span>
			<span class="p-1.5 bg-blue-500/10 text-blue-400 rounded-lg">🔄</span>
		</div>
		<div class="text-3xl font-extrabold text-white mb-1">{activeAssets} <span class="text-sm font-normal text-slate-400">/ {supersededAssets} obs.</span></div>
		<div class="text-xs text-slate-400">
			Ratio d'actifs actifs vs remplacés
		</div>
	</div>

	<!-- High Confidence Ratio -->
	<div class="p-5 bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl shadow-lg hover:border-purple-500/50 transition-all">
		<div class="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
			<span>Haute Confiance</span>
			<span class="p-1.5 bg-purple-500/10 text-purple-400 rounded-lg">🛡️</span>
		</div>
		<div class="text-3xl font-extrabold text-white mb-1">{highConfidenceCount}</div>
		<div class="text-xs text-slate-400">
			<span class="text-purple-400 font-medium">{Math.round((highConfidenceCount / (totalAssets || 1)) * 100)}%</span> certifiés par architecte
		</div>
	</div>

	<!-- Glossary & Relations -->
	<div class="p-5 bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl shadow-lg hover:border-amber-500/50 transition-all">
		<div class="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
			<span>Termes Glossaire & Graphe</span>
			<span class="p-1.5 bg-amber-500/10 text-amber-400 rounded-lg">🔗</span>
		</div>
		<div class="text-3xl font-extrabold text-white mb-1">{data?.glossary_count ?? 0} <span class="text-sm font-normal text-slate-400">termes</span></div>
		<div class="text-xs text-slate-400">
			<span class="text-amber-400 font-medium">{data?.relations?.REQUIRES ?? 0}</span> relations REQUIRES actives
		</div>
	</div>
</div>
