<script lang="ts">
	import { onMount } from 'svelte';
	import VolumeKpis from '$lib/components/dashboard/VolumeKpis.svelte';
	import DomainProminence from '$lib/components/dashboard/DomainProminence.svelte';
	import ComplianceCoverage from '$lib/components/dashboard/ComplianceCoverage.svelte';
	import GlossaryConceptsWidget from '$lib/components/dashboard/GlossaryConceptsWidget.svelte';
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

	const featuredAssets = [
		{
			id: 'ADR-0001',
			title: 'Git as the source of truth for network and platform configuration',
			type: 'decision',
			icon: '⚖️',
			badge: 'GitOps Core',
			domain: 'network-automation'
		},
		{
			id: 'ADR-0002',
			title: 'Network source of truth and compliance engine',
			type: 'decision',
			icon: '⚖️',
			badge: 'Compliance',
			domain: 'network-automation'
		},
		{
			id: 'PAT-001',
			title: 'Dual-Plane Network and Infrastructure Telemetry',
			type: 'pattern',
			icon: '🧩',
			badge: 'Observability',
			domain: 'observability'
		},
		{
			id: 'NIS2-ART21-2A',
			title: 'Risk Analysis and Information System Security Policies',
			type: 'control',
			icon: '🛡️',
			badge: 'NIS 2 Mandatory',
			domain: 'security-governance'
		}
	];
</script>

<div class="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-8 font-sans">
	<!-- Top Navigation & Multi-KB Selector -->
	<header class="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-6 mb-8 border-b border-slate-800">
		<div>
			<div class="flex items-center gap-3 mb-1">
				<h1 class="text-2xl font-black tracking-tight text-white">
					Knowledge Base Overview
				</h1>
				<span class="px-2.5 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full text-xs font-mono font-semibold">
					Graphe Neuro-Symbolique Kùzu
				</span>
			</div>
			<p class="text-xs text-slate-400">
				Vue consolidée de l'architecture, conformité réglementaire multi-référentiels et santé de la base de connaissances.
			</p>
		</div>

		<!-- Action Buttons & Multi-KB Instance Selector -->
		<div class="flex flex-wrap items-center gap-3">
			<button
				onclick={() => openReader('ADR-0001')}
				class="px-4 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-xl text-xs font-bold transition-all shadow-md flex items-center gap-2 cursor-pointer"
			>
				<span>🔍</span>
				<span>Consulter un Actif</span>
			</button>

			<div class="flex items-center gap-2 p-1 bg-slate-900 border border-slate-800 rounded-xl shadow-inner">
				{#each kbConfig.environments as env}
					<button
						onclick={() => handleEnvChange(env.id)}
						class="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 cursor-pointer {kbConfig.activeEnvId === env.id
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

	<main class="max-w-7xl mx-auto space-y-8">
		<!-- Dashboard Content -->
		{#if loading}
			<div class="py-24 text-center text-slate-400 text-sm">
				Chargement de la synthèse de la base de connaissances...
			</div>
		{:else}
			<!-- 1. Volume & Health KPIs -->
			<VolumeKpis data={analytics} />

			<!-- 2. Compliance & External Referentials Coverage -->
			<ComplianceCoverage coverage={analytics?.compliance_coverage} />

			<!-- 3. Domain Knowledge Mapping & Inter-Domain Synergies -->
			<DomainProminence data={prominence} />

			<!-- 4. Controlled Vocabulary & Core Architecture Concepts -->
			<GlossaryConceptsWidget />

			<!-- 5. Featured Architecture Assets Quick Access -->
			<div class="p-6 bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl shadow-lg">
				<div class="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
					<div>
						<h3 class="text-lg font-bold text-white flex items-center gap-2">
							<span class="p-1 bg-indigo-500/20 text-indigo-400 rounded">⭐</span>
							Actifs d'Architecture Structurants
						</h3>
						<p class="text-xs text-slate-400 mt-0.5">
							Accès rapide aux décisions, patterns et exigences pivots régissant la plateforme.
						</p>
					</div>
					<a
						href="/assets"
						class="text-xs text-emerald-400 hover:text-emerald-300 font-semibold flex items-center gap-1"
					>
						<span>Voir tout le catalogue</span>
						<span>➜</span>
					</a>
				</div>

				<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
					{#each featuredAssets as asset}
						<button
							type="button"
							onclick={() => openReader(asset.id)}
							class="text-left p-4 bg-slate-950/60 hover:bg-slate-900/90 border border-slate-800 hover:border-emerald-500/40 rounded-xl transition-all space-y-2 cursor-pointer group shadow-sm"
						>
							<div class="flex items-center justify-between">
								<span class="font-mono text-xs font-bold text-emerald-400 flex items-center gap-1.5">
									<span>{asset.icon}</span>
									<span>{asset.id}</span>
								</span>
								<span class="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
									{asset.badge}
								</span>
							</div>

							<div class="text-xs font-semibold text-slate-200 group-hover:text-white line-clamp-2 leading-snug">
								{asset.title}
							</div>

							<div class="text-[11px] text-slate-500 font-mono">
								#{asset.domain}
							</div>
						</button>
					{/each}
				</div>
			</div>
		{/if}
	</main>
</div>

<AssetReaderModal bind:open={readerOpen} initialId={selectedAssetId} />
