<script lang="ts">
	import { kbConfig } from '$lib/stores/kb-config.svelte';
	import type { Node3D, Edge3D } from '$lib/server/kb-adapter';

	let { nodes, edges, onOpenReader }: { nodes: Node3D[]; edges: Edge3D[]; onOpenReader?: (id: string) => void } = $props();

	let selectedNode = $derived(
		nodes.find((n) => n.id === kbConfig.selectedNodeId) || null
	);

	let connectedEdges = $derived(
		edges.filter((e) => e.source === selectedNode?.id || e.target === selectedNode?.id)
	);
</script>

{#if selectedNode}
	<div class="fixed right-6 top-24 bottom-6 w-96 bg-slate-900/90 backdrop-blur-md border border-slate-800 rounded-2xl p-6 shadow-2xl z-40 overflow-y-auto">
		<div class="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
			<div class="flex items-center gap-2">
				<span class="px-2.5 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded text-xs font-mono font-bold">
					{selectedNode.id}
				</span>
				<span class="text-xs text-slate-400 font-medium">{selectedNode.type}</span>
			</div>
			<button
				onclick={() => kbConfig.setSelectedNodeId(null)}
				class="text-slate-400 hover:text-white transition-colors text-lg"
			>
				✕
			</button>
		</div>

		<h3 class="text-lg font-bold text-white mb-2 leading-snug">
			{selectedNode.title}
		</h3>

		<button
			onclick={() => onOpenReader?.(selectedNode.id)}
			class="w-full mb-4 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/40 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2"
		>
			📖 Lire le Document Markdown Complet
		</button>

		<div class="space-y-3 mb-6 text-xs text-slate-300">
			<div class="flex justify-between py-1 border-b border-slate-800/60">
				<span class="text-slate-500">Domaine d'expertise:</span>
				<span class="font-semibold text-emerald-400">{selectedNode.domain}</span>
			</div>
			<div class="flex justify-between py-1 border-b border-slate-800/60">
				<span class="text-slate-500">Niveau d'élévation (Y):</span>
				<span class="font-mono text-slate-300">Level {selectedNode.y}</span>
			</div>
			<div class="flex justify-between py-1 border-b border-slate-800/60">
				<span class="text-slate-500">Statut du document:</span>
				<span class="px-2 py-0.5 bg-blue-500/10 text-blue-400 rounded font-medium">{selectedNode.status}</span>
			</div>
			<div class="flex justify-between py-1 border-b border-slate-800/60">
				<span class="text-slate-500">Centralité (Degré):</span>
				<span class="font-mono text-amber-400 font-bold">{selectedNode.degree} connexions</span>
			</div>
		</div>

		<h4 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
			Dépendances d'Architecture ({connectedEdges.length})
		</h4>

		<div class="space-y-2">
			{#each connectedEdges as edge}
				<div class="p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg text-xs">
					<div class="flex items-center justify-between text-slate-400 font-mono mb-1">
						<span>{edge.type}</span>
						<span class="text-slate-600">{edge.sourceDomain} ➜ {edge.targetDomain}</span>
					</div>
					<div class="text-white font-medium">
						{edge.source === selectedNode.id ? `➜ Requières: ${edge.target}` : `⬅ Requis par: ${edge.source}`}
					</div>
				</div>
			{/each}
		</div>
	</div>
{/if}
