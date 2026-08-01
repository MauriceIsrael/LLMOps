<script lang="ts">
	import { useThrelte, useTask } from '@threlte/core';
	import { OrbitControls as ThreeOrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
	import { onDestroy } from 'svelte';

	let { target = [0, 12, 0] }: { target?: [number, number, number] } = $props();

	const { camera, renderer } = useThrelte();

	let controls: ThreeOrbitControls | undefined;

	$effect(() => {
		const dom = renderer?.domElement || document.querySelector('canvas');
		if (camera.current && dom) {
			controls = new ThreeOrbitControls(camera.current, dom);
			controls.enableDamping = true;
			controls.target.set(...target);
		}
	});

	useTask(() => {
		controls?.update();
	});

	onDestroy(() => {
		controls?.dispose();
	});
</script>
