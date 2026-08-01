<script lang="ts">
	import { T } from '@threlte/core';
	import * as THREE from 'three';
	import type { Edge3D, Node3D } from '$lib/server/kb-adapter';

	let { edges, nodes }: { edges: Edge3D[]; nodes: Node3D[] } = $props();

	const nodeMap = $derived(new Map(nodes.map((n) => [n.id, n])));
</script>

{#each edges as edge (edge.id)}
	{@const sourceNode = nodeMap.get(edge.source)}
	{@const targetNode = nodeMap.get(edge.target)}

	{#if sourceNode && targetNode}
		{@const start = new THREE.Vector3(sourceNode.x, sourceNode.y + 0.8, sourceNode.z)}
		{@const end = new THREE.Vector3(targetNode.x, targetNode.y + 0.8, targetNode.z)}
		{@const curve = new THREE.LineCurve3(start, end)}

		<T.Line>
			<T.BufferGeometry
				attributes={{
					position: new THREE.Float32BufferAttribute([start.x, start.y, start.z, end.x, end.y, end.z], 3)
				}}
			/>
			<T.LineBasicMaterial
				color={edge.sourceDomain === edge.targetDomain ? '#38bdf8' : '#ec4899'}
				opacity={0.7}
				transparent={true}
				linewidth={2}
			/>
		</T.Line>
	{/if}
{/each}
