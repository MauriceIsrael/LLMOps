<script lang="ts">
	import { T } from '@threlte/core';
	import * as THREE from 'three';

	let { domains }: { domains: string[] } = $props();

	// Level heights along Y axis for each domain
	const colors = ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#6366f1'];
</script>

{#each domains as domain, idx}
	{@const y = idx * 6}
	{@const color = colors[idx % colors.length]}

	<T.Group position={[0, y, 0]}>
		<!-- Semi-transparent 3D plane surface -->
		<T.Mesh rotation={[-Math.PI / 2, 0, 0]}>
			<T.PlaneGeometry args={[30, 20]} />
			<T.MeshStandardMaterial
				color={color}
				transparent={true}
				opacity={0.12}
				side={THREE.DoubleSide}
				roughness={0.2}
				metalness={0.8}
			/>
		</T.Mesh>

		<!-- Plane Grid Helper for visual 3D grid structure -->
		<T.GridHelper args={[30, 15, color, color]} position={[0, 0.01, 0]} />

		<!-- Border wireframe box -->
		<T.LineSegments>
			<T.EdgesGeometry args={[new THREE.PlaneGeometry(30, 20)]} />
			<T.LineBasicMaterial color={color} opacity={0.4} transparent={true} />
		</T.LineSegments>
	</T.Group>
{/each}
