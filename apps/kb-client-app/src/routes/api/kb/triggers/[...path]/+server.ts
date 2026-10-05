import { json, type RequestHandler } from '@sveltejs/kit';

/**
 * Proxy to the review API of trigger rules and facts-vocabulary keys (Hub contract 1.25).
 *
 * Only the routes of the review screen are forwarded, to the Hub named by the server environment (never by the browser):
 *   GET   triggers                            rules by carrying element, vocabulary, queue
 *   POST  triggers/validate | triggers/preview
 *   PATCH candidates/{id}                     accept | amend | reject   (needs the kb:review scope)
 *   POST  candidates/{id}/merge-key           merge a proposed key into an existing one
 * The token comes from LLMOPS_REVIEW_TOKEN (the kb:review scope), else SERVER_TOKEN.
 */
const ALLOWED: Array<{ method: string; pattern: RegExp }> = [
	{ method: 'GET', pattern: /^triggers$/ },
	{ method: 'POST', pattern: /^triggers\/(validate|preview)$/ },
	{ method: 'PATCH', pattern: /^candidates\/CAND-[0-9A-Za-z-]+$/ },
	{ method: 'POST', pattern: /^candidates\/CAND-[0-9A-Za-z-]+\/merge-key$/ }
];

const handle: RequestHandler = async ({ params, request }) => {
	const path = params.path ?? '';
	if (!ALLOWED.some((a) => a.method === request.method && a.pattern.test(path))) {
		return json({ status: 'error', message: 'Route non autorisée' }, { status: 404 });
	}
	const endpoint = (process.env.LLMOPS_ENDPOINT || 'http://localhost:8000').replace(/\/+$/, '');
	const token = process.env.LLMOPS_REVIEW_TOKEN || process.env.SERVER_TOKEN;
	const headers: Record<string, string> = { Accept: 'application/json' };
	if (token) headers['Authorization'] = `Bearer ${token}`;
	const init: RequestInit = { method: request.method, headers };
	if (request.method !== 'GET') {
		headers['Content-Type'] = 'application/json';
		init.body = await request.text();
	}
	try {
		const res = await fetch(`${endpoint}/api/knowledge/${path}`, init);
		return json(await res.json(), { status: res.status });
	} catch (err: any) {
		return json({ status: 'error', message: `Hub injoignable : ${err?.message ?? err}` }, { status: 502 });
	}
};

export const GET = handle;
export const POST = handle;
export const PATCH = handle;
