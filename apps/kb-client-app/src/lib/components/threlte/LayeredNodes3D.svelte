<script lang="ts">
	import { T } from '@threlte/core';
	import type { Node3D } from '$lib/server/kb-adapter';
	import { kbConfig } from '$lib/stores/kb-config.svelte';

	let { nodes }: { nodes: Node3D[] } = $props();

	let hoveredId = $state<string | null>(null);

	const domainColors: Record<string, string> = {
		'Security & IAM': '#10b981',
		'Cloud & Infrastructure': '#3b82f6',
		'Data & Analytics': '#8b5cf6',
		'Integration & API': '#f59e0b',
		'LLMOps & AI': '#ec4899'
	};
</script>

{#each nodes as node (node.id)}
	{@const isSelected = kbConfig.selectedNodeId === node.id}
	{@const isHovered = hoveredId === node.id}
	{@const color = domainColors[node.domain] || '#64748b'}
	{@const radius = 0.6 + (node.degree / 12) * 0.5}

	<T.Group
		position={[node.x, node.y + radius, node.z]}
		onclick={(e: MouseEvent) => {
			e.stopPropagation();
			kbConfig.setSelectedNodeId(node.id);
		}}
		onpointerenter={() => (hoveredId = node.id)}
		onpointerleave={() => (hoveredId = null)}
	>
		<!-- Core Node Sphere -->
		<T.Mesh>
			<T.SphereGeometry args={[radius, 16, 16]} />
			<T.MeshStandardMaterial
				color={isSelected ? '#ffffff' : color}
				emissive={color}
				emissiveIntensity={isSelected ? 0.8 : isHovered ? 0.5 : 0.2}
				roughness={0.3}
				metalness={0.7}
			/>
		</T.Mesh>

		<!-- Glowing Outer Ring when selected/hovered -->
		{#if isSelected || isHovered}
			<T.Mesh>
				<T.SphereGeometry args={[radius * 1.3, 16, 16]} />
				<T.MeshBasicMaterial color={color} transparent={true} opacity={0.25} wireframe={true} />
			</T.Mesh>
		{/if}
	</T.Group>
{/each}
