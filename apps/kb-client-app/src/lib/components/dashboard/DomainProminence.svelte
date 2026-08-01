<script lang="ts">
	import type { DomainProminenceData } from '$lib/server/kb-adapter';

	let { data }: { data: DomainProminenceData | null } = $props();

	let maxVolume = $derived(
		Math.max(...(data?.domain_volumes?.map((d) => d.count) || [1]))
	);
</script>

<div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
	<!-- Domain Volume Breakdown -->
	<div class="p-6 bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl shadow-lg">
		<h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
			<span class="p-1 bg-indigo-500/20 text-indigo-400 rounded">📊</span>
			Masse Volumétrique par Domaine d'Expertise
		</h3>
		<div class="space-y-4">
			{#if data?.domain_volumes}
				{#each data.domain_volumes as d}
					<div>
						<div class="flex justify-between text-sm mb-1">
							<span class="font-medium text-slate-200">{d.domain}</span>
							<span class="text-slate-400 font-mono">{d.count} actifs ({Math.round((d.count / (data.domain_volumes.reduce((a, b) => a + b.count, 0) || 1)) * 100)}%)</span>
						</div>
						<div class="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
							<div
								class="bg-gradient-to-r from-indigo-500 to-purple-500 h-2.5 rounded-full transition-all duration-500"
								style="width: {(d.count / maxVolume) * 100}%"
							></div>
						</div>
					</div>
				{/each}
			{/if}
		</div>
	</div>

	<!-- Cross-Domain Dependency Matrix (Hub vs Consumers) -->
	<div class="p-6 bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl shadow-lg">
		<h3 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
			<span class="p-1 bg-emerald-500/20 text-emerald-400 rounded">🧲</span>
			Gravité & Matrice d'Ancrage Inter-Domaines
		</h3>
		<p class="text-xs text-slate-400 mb-4">
			Arêtes <code class="text-emerald-400">REQUIRES</code> franchissant les limites de domaines. Les domaines les plus ciblés agissent comme les **piliers d'ancrage**.
		</p>
		<div class="space-y-3">
			{#if data?.cross_domain_dependencies}
				{#each data.cross_domain_dependencies as dep}
					<div class="flex items-center justify-between p-3 bg-slate-950/60 border border-slate-800/80 rounded-lg">
						<div class="flex items-center gap-2 text-xs">
							<span class="px-2 py-1 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded font-medium">{dep.source_domain}</span>
							<span class="text-slate-500">➜ REQUIRES ➜</span>
							<span class="px-2 py-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded font-medium">{dep.target_domain}</span>
						</div>
						<div class="text-xs font-mono font-bold text-white bg-slate-800 px-2 py-0.5 rounded">
							{dep.weight} arêtes
						</div>
					</div>
				{/each}
			{/if}
		</div>
	</div>
</div>
