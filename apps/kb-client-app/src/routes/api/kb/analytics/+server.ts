import { json, type RequestHandler } from '@sveltejs/kit';
import { KBAdapter } from '$lib/server/kb-adapter';

export const GET: RequestHandler = async ({ url }) => {
	const type = (url.searchParams.get('type') || 'local') as 'local' | 'gcp';
	const endpoint = url.searchParams.get('endpoint') || 'http://localhost:8000';
	const apiKey = url.searchParams.get('apiKey') || undefined;

	const adapter = new KBAdapter({ type, endpoint, apiKey });
	const [analytics, prominence] = await Promise.all([
		adapter.fetchAnalytics(),
		adapter.fetchDomainProminence()
	]);

	return json({
		status: 'ok',
		data: {
			analytics,
			prominence
		}
	});
};
