<script lang="ts">
	import { onMount } from 'svelte';
	import { Canvas } from '@threlte/core';
	import Scene3D from '$lib/components/threlte/Scene3D.svelte';
	import NodeInspector from '$lib/components/threlte/NodeInspector.svelte';
	import AssetReaderModal from '$lib/components/dashboard/AssetReaderModal.svelte';
	import { kbConfig } from '$lib/stores/kb-config.svelte';
	import type { LayeredGraphPayload } from '$lib/server/kb-adapter';

	let graphData = $state<LayeredGraphPayload | null>(null);
	let loading = $state(true);
	let readerOpen = $state(false);
	let selectedAssetId = $state('ADR-0001');

	onMount(async () => {
		try {
			const res = await fetch(
				`/api/kb/graph?type=${kbConfig.activeEnv.type}&endpoint=${encodeURIComponent(kbConfig.activeEnv.endpoint)}`
			);
			if (res.ok) {
				const json = await res.json();
				graphData = json.data;
			}
		} catch (e) {
			console.error('Failed to load 3D graph data', e);
		} finally {
			loading = false;
		}
	});

	function handleOpenReader(id: string) {
		selectedAssetId = id;
		readerOpen = true;
	}
</script>

<div class="relative w-full h-screen bg-slate-950 overflow-hidden select-none">
	<!-- Top Navigation Overlay -->
	<header class="absolute top-0 left-0 right-0 p-6 z-30 flex items-center justify-between pointer-events-none">
		<div class="pointer-events-auto flex items-center gap-4">
			<div>
				<h1 class="text-xl font-black text-white tracking-tight flex items-center gap-2">
					Visualiseur 3D <span class="px-2 py-0.5 bg-gradient-to-r from-emerald-500 to-indigo-500 text-white rounded-md text-xs font-bold uppercase tracking-wider">Threlte Planes</span>
				</h1>
				<p class="text-xs text-slate-400">Cartographie Neuro-Symbolique par Niveaux Y de Domaines d'Expertise</p>
			</div>
		</div>

		<!-- Environment Badge -->
		<div class="pointer-events-auto px-3 py-1.5 bg-slate-900/90 backdrop-blur border border-emerald-500/30 text-emerald-400 rounded-xl text-xs font-mono font-medium shadow-lg flex items-center gap-2">
			<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
			{kbConfig.activeEnv.name}
		</div>
	</header>

	<!-- Threlte 3D Canvas -->
	{#if loading}
		<div class="w-full h-full flex items-center justify-center text-slate-400 text-sm font-medium">
			Chargement du Graphe 3D...
		</div>
	{:else if graphData}
		<Canvas>
			<Scene3D {graphData} />
		</Canvas>

		<NodeInspector nodes={graphData.nodes} edges={graphData.edges} onOpenReader={handleOpenReader} />
	{/if}

	<!-- Floating Legend Bottom Left -->
	{#if graphData?.domains}
		{@const colors = ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#6366f1']}
		<div class="absolute bottom-6 left-6 p-4 bg-slate-900/90 backdrop-blur border border-slate-800 rounded-xl text-xs z-30 shadow-xl space-y-1.5 max-h-64 overflow-y-auto">
			<div class="font-bold text-white mb-1">Niveaux 3D par Domaine</div>
			{#each graphData.domains as dom, idx}
				<div class="flex items-center gap-2">
					<span class="w-3 h-3 rounded" style="background-color: {colors[idx % colors.length]}"></span>
					<span class="text-slate-300 font-medium">{dom} <span class="text-slate-500 font-mono text-[10px]">(Y: {idx * 6})</span></span>
				</div>
			{/each}
		</div>
	{/if}
</div>

<AssetReaderModal bind:open={readerOpen} initialId={selectedAssetId} />
