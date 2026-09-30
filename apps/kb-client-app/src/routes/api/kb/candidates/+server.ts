import { json, type RequestHandler } from '@sveltejs/kit';
import { llmopsFetch } from '$lib/server/llmops-api';

/** Candidate queue, proxied to GET /api/knowledge/candidates (filters: status, source, domain, engagement). */
export const GET: RequestHandler = async ({ url }) => {
	const params = new URLSearchParams();
	for (const key of ['status', 'source', 'domain', 'engagement']) {
		const value = url.searchParams.get(key);
		if (value) params.set(key, value);
	}
	try {
		const res = await llmopsFetch(`/api/knowledge/candidates?${params.toString()}`);
		return json(await res.json(), { status: res.status });
	} catch (err: any) {
		return json({ status: 'error', reason: `LLMOps API unreachable: ${err?.message || err}` }, { status: 502 });
	}
};
