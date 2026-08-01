<script lang="ts">
	import { onMount } from 'svelte';
	import VolumeKpis from '$lib/components/dashboard/VolumeKpis.svelte';
	import DomainProminence from '$lib/components/dashboard/DomainProminence.svelte';
	import AssetReaderModal from '$lib/components/dashboard/AssetReaderModal.svelte';
	import { kbConfig } from '$lib/stores/kb-config.svelte';
	import type { VolumeKpiData, DomainProminenceData } from '$lib/server/kb-adapter';

	let analytics = $state<VolumeKpiData | null>(null);
	let prominence = $state<DomainProminenceData | null>(null);
	let loading = $state(true);
	let readerOpen = $state(false);
	let selectedAssetId = $state('ADR-0001');

	async function loadDashboardData() {
		loading = true;
		try {
			const res = await fetch(
				`/api/kb/analytics?type=${kbConfig.activeEnv.type}&endpoint=${encodeURIComponent(kbConfig.activeEnv.endpoint)}`
			);
			if (res.ok) {
				const json = await res.json();
				analytics = json.data.analytics;
				prominence = json.data.prominence;
			}
		} catch (e) {
			console.error('Error fetching analytics:', e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadDashboardData();
	});

	function handleEnvChange(id: string) {
		kbConfig.setEnvironment(id);
		loadDashboardData();
	}

	function openReader(id: string = 'ADR-0001') {
		selectedAssetId = id;
		readerOpen = true;
	}
</script>

<div class="min-h-screen bg-slate-950 text-slate-100 p-8 font-sans">
	<!-- Top Navigation & Multi-KB Selector -->
	<header class="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-8 mb-8 border-b border-slate-800">
		<div>
			<div class="flex items-center gap-3 mb-1">
				<h1 class="text-2xl font-black tracking-tight text-white">
					LLMOps Knowledge Base Explorer
				</h1>
				<span class="px-2.5 py-0.5 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded-full text-xs font-mono font-semibold">
					FastMCP + Threlte 3D
				</span>
			</div>
			<p class="text-sm text-slate-400">
				Plateforme Introspective Multi-KB & Analyse de Centralité des Domaines d'Expertise
			</p>
		</div>

		<!-- Action Buttons & Multi-KB Instance Selector -->
		<div class="flex flex-wrap items-center gap-3">
			<button
				onclick={() => openReader('ADR-0001')}
				class="px-4 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-xl text-xs font-bold transition-all shadow-md flex items-center gap-2"
			>
				🔍 Consulter un Actif (Formulaire)
			</button>

			<div class="flex items-center gap-2 p-1.5 bg-slate-900 border border-slate-800 rounded-xl shadow-inner">
			{#each kbConfig.environments as env}
				<button
					onclick={() => handleEnvChange(env.id)}
					class="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 {kbConfig.activeEnvId === env.id
						? 'bg-gradient-to-r from-emerald-500 to-indigo-600 text-white shadow-md'
						: 'text-slate-400 hover:text-white hover:bg-slate-800'}"
				>
					<span class="w-2 h-2 rounded-full {env.type === 'local' ? 'bg-emerald-400' : 'bg-blue-400'}"></span>
					{env.name}
				</button>
			{/each}
			</div>
		</div>
	</header>

	<main class="max-w-7xl mx-auto">
		<!-- Banner to Launch 3D Visualizer -->
		<div class="p-6 mb-8 bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-indigo-500/30 rounded-2xl shadow-2xl flex flex-col md:flex-row items-center justify-between gap-6">
			<div>
				<div class="inline-flex items-center gap-2 text-xs font-bold text-indigo-400 uppercase tracking-wider mb-2">
					<span class="p-1 bg-indigo-500/20 rounded">✨</span> Visualisation 3D Threlte
				</div>
				<h2 class="text-xl font-extrabold text-white mb-1">
					Cartographie 3D par Planes de Domaines d'Expertise
				</h2>
				<p class="text-xs text-slate-400 max-w-2xl">
					Explorez le graphe Kùzu DB sous forme de plans 3D empilés par domaine (Security, Cloud, Data, LLMOps). Visualisez les connexions inter-domaines et l'antériorité des ADRs en temps réel.
				</p>
			</div>
			<a
				href="/explorer"
				class="px-6 py-3 bg-gradient-to-r from-emerald-500 to-indigo-500 hover:from-emerald-400 hover:to-indigo-400 text-white font-bold text-sm rounded-xl transition-all shadow-lg hover:shadow-emerald-500/20 whitespace-nowrap"
			>
				Ouvrir l'App 3D Threlte ➜
			</a>
		</div>

		<!-- Dashboard Content -->
		{#if loading}
			<div class="py-20 text-center text-slate-400 text-sm">
				Chargement des métriques de la base de connaissance...
			</div>
		{:else}
			<!-- Volume KPIs -->
			<VolumeKpis data={analytics} />

			<!-- Domain Prominence Breakdown -->
			<DomainProminence data={prominence} />
		{/if}
	</main>
</div>

<AssetReaderModal bind:open={readerOpen} initialId={selectedAssetId} />
