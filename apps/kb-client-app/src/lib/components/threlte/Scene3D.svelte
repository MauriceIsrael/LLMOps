<script lang="ts">
	import { T } from '@threlte/core';
	import OrbitControls from './OrbitControls.svelte';
	import DomainPlanes3D from './DomainPlanes3D.svelte';
	import LayeredNodes3D from './LayeredNodes3D.svelte';
	import CrossDomainEdges3D from './CrossDomainEdges3D.svelte';
	import type { LayeredGraphPayload } from '$lib/server/kb-adapter';

	let { graphData }: { graphData: LayeredGraphPayload } = $props();
</script>

<!-- Camera setup with 3D perspective angled above the domain planes -->
<T.PerspectiveCamera
	makeDefault
	position={[35, 32, 45]}
	fov={50}
>
	<OrbitControls target={[0, 12, 0]} />
</T.PerspectiveCamera>

<!-- Lighting setup -->
<T.AmbientLight intensity={0.6} />
<T.DirectionalLight position={[40, 60, 30]} intensity={1.2} castShadow />
<T.PointLight position={[-20, 30, -20]} intensity={0.8} color="#3b82f6" />

<!-- 3D Layered Content -->
{#if graphData}
	<DomainPlanes3D domains={graphData.domains} />
	<LayeredNodes3D nodes={graphData.nodes} />
	<CrossDomainEdges3D edges={graphData.edges} nodes={graphData.nodes} />
{/if}
