<script lang="ts">
	interface Concept {
		term: string;
		category: string;
		definition: string;
		domains: string[];
	}

	const concepts: Concept[] = [
		{
			term: 'Continuous Compliance Evaluation',
			category: 'Gouvernance & Audit',
			definition: 'Inspection continue et automatisée de la posture opérationnelle contre les baselines réglementaires pour prévenir le drift.',
			domains: ['security', 'compliance', 'observability']
		},
		{
			term: 'Source of Truth (Single Source)',
			category: 'Architecture GitOps',
			definition: 'Dépôt Git faisant foi pour l\'état souhaité de la configuration logicielle et d\'infrastructure.',
			domains: ['cloud-platform', 'network-automation']
		},
		{
			term: 'Supply Chain Security Baseline',
			category: 'Sécurité Tiers & SBOM',
			definition: 'Contrôles stricts sur la provenance logicielle, SBOM signé et isolation des accès éditeurs via API northbound.',
			domains: ['supply-chain', 'security']
		},
		{
			term: 'Early Warning (24h Alert)',
			category: 'Résilience NIS 2',
			definition: 'Alerte formelle ultra-rapide émise vers les autorités de cybersécurité (CSIRT) dans les 24 heures suivant un incident majeur.',
			domains: ['incident-handling', 'resilience']
		},
		{
			term: 'Break-glass Procedure',
			category: 'Continuité d\'Urgence',
			definition: 'Procédure d\'exception permettant des opérations de rétablissement directes quand la plateforme de management est indisponible.',
			domains: ['resilience', 'operations']
		},
		{
			term: 'Sovereignty Boundary',
			category: 'SecNumCloud & Données',
			definition: 'Périmètre garantissant l\'autonomie des clés de chiffrement (HSM ANSSI) et l\'immunité aux lois extraterritoriales étrangères.',
			domains: ['sovereignty', 'cryptography']
		}
	];
</script>

<div class="p-6 bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl shadow-lg mb-8">
	<div class="flex items-center justify-between pb-4 mb-5 border-b border-slate-800">
		<div>
			<h3 class="text-lg font-bold text-white flex items-center gap-2">
				<span class="p-1 bg-amber-500/20 text-amber-400 rounded">💡</span>
				Vocabulaire Contrôlé & Concepts Piliers de la KB
			</h3>
			<p class="text-xs text-slate-400 mt-0.5">
				Concepts unifiés reliant les réglementations externes (NIS 2, SecNumCloud) aux décisions et patterns d'architecture internes.
			</p>
		</div>
		<span class="px-2.5 py-1 bg-amber-500/10 text-amber-300 border border-amber-500/20 rounded-lg text-xs font-mono font-bold">
			Ontologie Active
		</span>
	</div>

	<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
		{#each concepts as c}
			<div class="p-4 bg-slate-950/60 border border-slate-800/80 rounded-xl flex flex-col justify-between space-y-3 hover:border-amber-500/30 transition-all">
				<div>
					<div class="flex items-center justify-between gap-2 mb-1.5">
						<span class="text-xs font-bold text-amber-300 font-mono tracking-wide truncate">
							{c.term}
						</span>
						<span class="text-[10px] uppercase font-semibold text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded shrink-0">
							{c.category}
						</span>
					</div>
					<p class="text-xs text-slate-300 leading-relaxed">
						{c.definition}
					</p>
				</div>

				<div class="flex flex-wrap gap-1.5 pt-2 border-t border-slate-800/60">
					{#each c.domains as dom}
						<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-800">
							#{dom}
						</span>
					{/each}
				</div>
			</div>
		{/each}
	</div>
</div>
