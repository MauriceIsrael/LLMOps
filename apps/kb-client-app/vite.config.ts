import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		watch: {
			ignored: ['**/dev.db*', '**/.git/**', '**/tmp/**', '**/data/engagements/**']
		}
	},
	optimizeDeps: {
		// ── Dépendances lourdes (poids brut) ─────────────────────────────────────
		// echarts (59 Mo source) et gridstack (2.1 Mo) sont pré-bundlés au
		// démarrage du serveur dev pour éviter les lenteurs à la première navigation.
		//
		// ── Dépendances transitives découvertes au runtime ──────────────────
		// Les entrées ci-dessous correspondent aux modules que Vite découvrait
		// trop tard (à la première requête), ce qui causait :
		//   "✨ optimized dependencies changed. reloading"
		// = rechargement complet de la page visible par l'utilisateur.
		//
		// Sources :
		//   svelte-i18n  → intl-messageformat, deepmerge
		//   bits-ui      → @floating-ui/dom, tabbable, style-to-object
		//   @internationalized/date → via bits-ui DatePicker, Calendar...
		include: [
			// Lourdes
			'echarts/core',
			'echarts/charts',
			'echarts/components',
			'echarts/renderers',
			'gridstack',
			'casbin',
			'casbin-prisma-adapter',
			// Packages SSR découverts trop tard (prisma, jose)
			'@prisma/client',
			'jose',
			// Transitives svelte-i18n
			'intl-messageformat',
			'deepmerge',
			// Transitives bits-ui
			'@floating-ui/dom',
			'tabbable',
			'style-to-object',
			// Transitives @internationalized
			'@internationalized/date',
		]
	}
});
