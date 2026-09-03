<script lang="ts">
	import { onMount } from 'svelte';
	import Users from 'lucide-svelte/icons/users';
	import ShieldCheck from 'lucide-svelte/icons/shield-check';
	import AlertTriangle from 'lucide-svelte/icons/alert-triangle';
	import RefreshCw from 'lucide-svelte/icons/refresh-cw';
	import FileSearch from 'lucide-svelte/icons/file-search';
	import Check from 'lucide-svelte/icons/check';
	import Briefcase from 'lucide-svelte/icons/briefcase';
	import Award from 'lucide-svelte/icons/award';

	let loading = $state(true);
	let engagement = $state('nordwave-mcx-2027');
	let matrixData = $state<any>(null);
	let activeTab = $state<'matrix' | 'rfp_simulator'>('matrix');

	// RFP Simulator state
	let rfpText = $state('');
	let analyzingRfp = $state(false);
	let rfpResults = $state<any>(null);

	async function loadStaffingMatrix() {
		loading = true;
		try {
			const res = await fetch(`/api/kb/staffing-matrix?engagement=${encodeURIComponent(engagement)}`);
			if (res.ok) {
				const json = await res.json();
				matrixData = json.data || null;
			}
		} catch (e) {
			console.error('Erreur chargement staffing matrix:', e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadStaffingMatrix();
	});

	async function runRfpSimulation() {
		if (!rfpText.trim()) return;
		analyzingRfp = true;
		try {
			const res = await fetch('/api/kb/analyze-rfp', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ text: rfpText })
			});
			if (res.ok) {
				const json = await res.json();
				rfpResults = json.data;
			}
		} catch (e) {
			console.error('Erreur analyse RFP:', e);
		} finally {
			analyzingRfp = false;
		}
	}

	function loadSampleRfp() {
		rfpText = `Le programme vise le déploiement d'un réseau mobile critique MCX (Mission Critical Services) conforme aux spécifications 3GPP Rel-17/18.
L'infrastructure sous-jacente s'appuiera sur une architecture IP Transport BGP-EVPN et un cluster Kubernetes durci Rancher.
La solution doit satisfaire les exigences réglementaires NIS2 (Article 21) et la qualification SecNumCloud de l'ANSSI.
L'autorité de certification et le chiffrement de bout en bout nécessitent un HSM qualifié de niveau renforcé pour le stockage des clés racines.
Une flotte de 2000 terminaux durcis avec profils MDM/EMM sera enrôlée pour les forces de terrain.
Un PCA/PRA multi-datacenter et une intégration avec le SOC/CSIRT central pour la journalisation WORM sont strictement requis.`;
	}
</script>

<div class="min-h-screen bg-slate-950 text-slate-100 p-6 flex flex-col gap-6 font-sans">
	<!-- Header -->
	<div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
		<div>
			<div class="flex items-center gap-3">
				<div class="p-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
					<Users class="w-6 h-6" />
				</div>
				<h1 class="text-2xl font-bold tracking-tight text-white">Staffing, Compétences & Simulateur RFP</h1>
			</div>
			<p class="text-sm text-slate-400 mt-1">
				Audit d'adéquation de l'équipe face aux Blueprints techniques et dimensionnement automatique d'équipes d'avant-vente.
			</p>
		</div>

		<div class="flex items-center gap-3">
			<button 
				onclick={loadStaffingMatrix} 
				class="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
				disabled={loading}
			>
				<RefreshCw class="w-3.5 h-3.5 {loading ? 'animate-spin' : ''}" />
				Actualiser
			</button>
		</div>
	</div>

	<!-- Tabs -->
	<div class="flex items-center gap-2 border-b border-slate-800 pb-2 text-sm">
		<button 
			onclick={() => activeTab = 'matrix'} 
			class="px-4 py-2 rounded-lg font-medium transition flex items-center gap-2 {activeTab === 'matrix' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-200'}"
		>
			<ShieldCheck class="w-4 h-4" />
			Matrice Projet en Direct ({engagement})
		</button>
		<button 
			onclick={() => activeTab = 'rfp_simulator'} 
			class="px-4 py-2 rounded-lg font-medium transition flex items-center gap-2 {activeTab === 'rfp_simulator' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'}"
		>
			<FileSearch class="w-4 h-4" />
			Simulateur RFP / CCTP (Dream Team Matrix)
		</button>
	</div>

	{#if activeTab === 'matrix'}
		<!-- KPI Summary Cards -->
		{#if matrixData}
			<div class="grid grid-cols-1 md:grid-cols-4 gap-4">
				<div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col">
					<span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Taux de Couverture</span>
					<div class="flex items-baseline gap-2 mt-1">
						<span class="text-3xl font-bold {matrixData.coverage_percentage === 100 ? 'text-emerald-400' : 'text-amber-400'}">
							{matrixData.coverage_percentage}%
						</span>
						<span class="text-xs text-slate-400">({matrixData.covered_skills_count}/{matrixData.total_required_skills})</span>
					</div>
				</div>

				<div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col">
					<span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Index de Risque Staffing</span>
					<span class="text-2xl font-bold mt-1 {matrixData.risk_level === 'low' ? 'text-emerald-400' : 'text-amber-400'}">
						{matrixData.risk_level === 'low' ? 'FAIBLE' : 'MODÉRÉ'}
					</span>
				</div>

				<div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col">
					<span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Assistance Technique / Prestataires</span>
					<span class="text-2xl font-bold text-white mt-1">
						{matrixData.external_contractors?.length || 0}
					</span>
				</div>

				<div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col">
					<span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Statut Gap G5</span>
					<span class="text-2xl font-bold mt-1 {matrixData.missing_skills?.length === 0 ? 'text-emerald-400' : 'text-red-400'}">
						{matrixData.missing_skills?.length === 0 ? 'RÉSOLU' : `${matrixData.missing_skills.length} MANQUANTS`}
					</span>
				</div>
			</div>

			<!-- Sections Table -->
			<div class="bg-slate-900/60 rounded-xl border border-slate-800 overflow-hidden">
				<div class="p-4 border-b border-slate-800 flex items-center justify-between">
					<h3 class="text-sm font-semibold text-white">Couverture Détaillée par Section du Blueprint (BLU-hla-mcx)</h3>
					<span class="text-xs text-slate-400">Engagement actif : <strong class="text-slate-200">{engagement}</strong></span>
				</div>

				<table class="w-full text-left text-xs">
					<thead class="bg-slate-950/80 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
						<tr>
							<th class="p-3.5">Section</th>
							<th class="p-3.5">Intitulé</th>
							<th class="p-3.5">Compétences Requises</th>
							<th class="p-3.5">Statut</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-800/60">
						{#each Object.entries(matrixData.sections || {}) as [secId, sectionItem]}
							{@const s = sectionItem as any}
							<tr class="hover:bg-slate-800/30 transition">
								<td class="p-3.5 font-mono text-emerald-400 font-semibold">{secId}</td>
								<td class="p-3.5 text-white font-medium">{s.title}</td>
								<td class="p-3.5">
									<div class="flex flex-wrap gap-1.5">
										{#each s.required_skills as sk}
											<span class="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[11px] border border-slate-700">
												{sk}
											</span>
										{/each}
									</div>
								</td>
								<td class="p-3.5">
									{#if s.covered}
										<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
											<Check class="w-3 h-3" /> Couvert
										</span>
									{:else}
										<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-red-500/10 text-red-400 border border-red-500/20">
											<AlertTriangle class="w-3 h-3" /> Manquant ({s.missing_skills?.join(', ')})
										</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{:else if loading}
			<div class="p-12 text-center text-slate-500 text-sm">Chargement de la matrice de compétences...</div>
		{/if}

	{:else}
		<!-- Tab 2: RFP Simulator -->
		<div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
			<!-- Left: Input (5 cols) -->
			<div class="lg:col-span-5 bg-slate-900/60 rounded-xl border border-slate-800 p-6 flex flex-col gap-4">
				<div class="flex items-center justify-between">
					<h3 class="text-sm font-semibold text-white">Cahier des Charges / CCTP Entrant</h3>
					<button 
						onclick={loadSampleRfp} 
						class="text-xs text-blue-400 hover:underline"
					>
						Charger un exemple
					</button>
				</div>
				<p class="text-xs text-slate-400">
					Collez le texte d'un appel d'offres ou d'une spécification client pour extraire les compétences indispensables et dimensionner l'équipe cible.
				</p>

				<textarea 
					bind:value={rfpText} 
					rows="12" 
					placeholder="Collez ici le texte du CCTP / RFP..."
					class="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 font-mono focus:outline-none focus:border-blue-500 leading-relaxed"
				></textarea>

				<button 
					onclick={runRfpSimulation}
					class="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition flex items-center justify-center gap-2 shadow-lg shadow-blue-950/40"
					disabled={analyzingRfp || !rfpText.trim()}
				>
					<FileSearch class="w-4 h-4 {analyzingRfp ? 'animate-spin' : ''}" />
					{analyzingRfp ? 'Analyse & Dimensionnement en cours...' : 'Analyser & Générer la Dream Team Matrix'}
				</button>
			</div>

			<!-- Right: Output (7 cols) -->
			<div class="lg:col-span-7 bg-slate-900/60 rounded-xl border border-slate-800 p-6 flex flex-col gap-6">
				{#if rfpResults}
					<!-- Detected Regulations -->
					<div class="flex flex-col gap-2">
						<span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Référentiels Réglementaires Détectés</span>
						<div class="flex flex-wrap gap-2">
							{#each rfpResults.regulatory_targets || [] as reg}
								<span class="px-3 py-1 rounded-lg bg-emerald-500/10 text-emerald-300 font-semibold text-xs border border-emerald-500/30">
									🏛️ {reg}
								</span>
							{/each}
						</div>
					</div>

					<!-- Dream Team Staffing Matrix -->
					<div class="flex flex-col gap-2">
						<span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Profil d'Équipe Cible Recommandé (Dream Team)</span>
						<div class="space-y-3">
							{#each rfpResults.dream_team || [] as role}
								<div class="p-4 rounded-xl bg-slate-950 border border-slate-800 flex flex-col gap-2">
									<div class="flex items-center justify-between">
										<h4 class="text-sm font-bold text-white flex items-center gap-2">
											<Briefcase class="w-4 h-4 text-blue-400" />
											{role.role}
										</h4>
										<span class="px-2.5 py-0.5 rounded text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
											{role.fte}
										</span>
									</div>
									<p class="text-xs text-slate-400">{role.mission}</p>
									<div class="flex items-center justify-between text-[11px] pt-2 border-t border-slate-900">
										<span class="text-slate-500">Compétences : <strong class="text-slate-300">{role.skills?.join(', ')}</strong></span>
										<span class="text-slate-500">Séniorité : <strong class="text-amber-400">{role.min_level}</strong></span>
									</div>
								</div>
							{/each}
						</div>
					</div>

					<!-- Ranked Skills -->
					<div class="flex flex-col gap-2">
						<span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Compétences Détectées par Intensité</span>
						<div class="grid grid-cols-1 md:grid-cols-2 gap-2">
							{#each rfpResults.ranked_skills || [] as sk}
								<div class="p-3 rounded-lg bg-slate-950/70 border border-slate-800 text-xs flex flex-col gap-1">
									<div class="flex items-center justify-between">
										<span class="font-mono text-emerald-400 font-semibold">{sk.id}</span>
										<span class="text-[10px] font-bold text-amber-400">{sk.intensity}</span>
									</div>
									<span class="text-white font-medium">{sk.title}</span>
									<span class="text-[11px] text-slate-500">Occurrences : {sk.key_occurrences?.join(', ')}</span>
								</div>
							{/each}
						</div>
					</div>
				{:else}
					<div class="p-16 text-center text-slate-500 text-sm flex flex-col items-center gap-3">
						<FileSearch class="w-8 h-8 text-slate-600" />
						Collez un document RFP ou cliquez sur "Charger un exemple" pour visualiser la Dream Team Staffing Matrix.
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>
