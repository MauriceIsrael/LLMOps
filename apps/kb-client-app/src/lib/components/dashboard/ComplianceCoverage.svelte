<script lang="ts">
	import type { FrameworkCoverage } from '$lib/server/kb-adapter';

	let { coverage = [] }: { coverage?: FrameworkCoverage[] } = $props();

	const frameworkMeta: Record<string, { label: string; icon: string; desc: string; color: string; bg: string }> = {
		NIS2: {
			label: 'NIS 2 (Directive UE)',
			icon: '🛡️',
			desc: 'Directive (EU) 2022/2555 — Gestion des cyber-risques & continuité',
			color: 'text-emerald-400',
			bg: 'from-emerald-500 to-teal-500'
		},
		'3GPP': {
			label: '3GPP (5G & MCX)',
			icon: '📡',
			desc: 'Spécifications TS 33.501 & TS 33.179 — SBA & Chiffrement bout-en-bout',
			color: 'text-cyan-400',
			bg: 'from-cyan-500 to-blue-500'
		},
		SecNumCloud: {
			label: 'SecNumCloud 3.2',
			icon: '☁️',
			desc: 'Référentiel ANSSI — Souveraineté, immunité extraterritoriale & HSM',
			color: 'text-amber-400',
			bg: 'from-amber-500 to-orange-500'
		},
		ISO27001: {
			label: 'ISO/IEC 27001:2022',
			icon: '🌐',
			desc: 'Standard international — Annexe A : Gestion des configurations & SBOM',
			color: 'text-purple-400',
			bg: 'from-purple-500 to-indigo-500'
		}
	};

	let totalControls = $derived(
		coverage.reduce((acc, curr) => acc + curr.total_controls, 0)
	);
	let totalImplemented = $derived(
		coverage.reduce((acc, curr) => acc + curr.implemented_controls, 0)
	);
	let globalRate = $derived(
		totalControls > 0 ? Math.round((totalImplemented / totalControls) * 100) : 0
	);
</script>

<div class="p-6 bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl shadow-lg mb-8">
	<!-- Header -->
	<div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 mb-6 border-b border-slate-800">
		<div>
			<h3 class="text-lg font-bold text-white flex items-center gap-2">
				<span class="p-1 bg-emerald-500/20 text-emerald-400 rounded">🛡️</span>
				Couverture des Référentiels & Conformité Réglementaire
			</h3>
			<p class="text-xs text-slate-400 mt-0.5">
				Alignement automatique des exigences externes (NIS 2, 3GPP, SecNumCloud, ISO 27001) avec les motifs et décisions d'architecture internes.
			</p>
		</div>

		<div class="flex items-center gap-4 shrink-0">
			<div class="text-right">
				<div class="text-2xl font-black text-emerald-400">
					{globalRate}%
				</div>
				<div class="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">
					Couverture Globale ({totalImplemented}/{totalControls})
				</div>
			</div>
			<a
				href="/assets"
				class="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition-all border border-slate-700 flex items-center gap-1.5"
			>
				<span>Consulter les contrôles</span>
				<span>➜</span>
			</a>
		</div>
	</div>

	<!-- Frameworks Grid -->
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
		{#each coverage as item}
			{@const meta = frameworkMeta[item.framework] || {
				label: item.framework,
				icon: '📄',
				desc: 'Référentiel externe',
				color: 'text-slate-400',
				bg: 'from-slate-500 to-slate-600'
			}}
			<div class="p-4 bg-slate-950/60 border border-slate-800/80 rounded-xl space-y-3 hover:border-slate-700 transition-all">
				<div class="flex items-start justify-between gap-2">
					<div class="flex items-center gap-2.5">
						<span class="text-lg">{meta.icon}</span>
						<div>
							<div class="text-sm font-bold text-slate-200 flex items-center gap-2">
								{meta.label}
							</div>
							<div class="text-[11px] text-slate-400 leading-tight">
								{meta.desc}
							</div>
						</div>
					</div>

					<span class="px-2 py-0.5 rounded text-xs font-mono font-bold {item.coverage_pct > 0 ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-400'} shrink-0">
						{item.coverage_pct}%
					</span>
				</div>

				<!-- Progress bar -->
				<div>
					<div class="flex justify-between text-[11px] text-slate-400 mb-1 font-mono">
						<span>Exigences couvertes</span>
						<span>{item.implemented_controls} / {item.total_controls} contrôles</span>
					</div>
					<div class="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
						<div
							class="bg-gradient-to-r {meta.bg} h-2 rounded-full transition-all duration-500"
							style="width: {item.coverage_pct}%"
						></div>
					</div>
				</div>
			</div>
		{/each}
	</div>
</div>
