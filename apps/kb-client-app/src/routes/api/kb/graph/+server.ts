import { json, type RequestHandler } from '@sveltejs/kit';
import { KBAdapter } from '$lib/server/kb-adapter';

export const GET: RequestHandler = async ({ url }) => {
	const type = (url.searchParams.get('type') || 'local') as 'local' | 'gcp';
	const endpoint = url.searchParams.get('endpoint') || 'http://localhost:8000';

	const adapter = new KBAdapter({ type, endpoint });
	const payload = await adapter.fetchLayeredGraph3D();

	return json({
		status: 'ok',
		data: payload
	});
};
