import { json, type RequestHandler } from '@sveltejs/kit';
import { llmopsFetch } from '$lib/server/llmops-api';

const CANDIDATE_ID = /^CAND-\d{8}-\d{4}$/;

/** Candidate detail, proxied to GET /api/knowledge/candidates/{id}. */
export const GET: RequestHandler = async ({ params }) => {
	if (!CANDIDATE_ID.test(params.id ?? '')) {
		return json({ status: 'not_found', id: params.id }, { status: 404 });
	}
	try {
		const res = await llmopsFetch(`/api/knowledge/candidates/${params.id}`);
		return json(await res.json(), { status: res.status });
	} catch (err: any) {
		return json({ status: 'error', reason: `LLMOps API unreachable: ${err?.message || err}` }, { status: 502 });
	}
};

/**
 * Review (accept | amend | reject), proxied to PATCH /api/knowledge/candidates/{id} with the
 * server-side kb:review token. Restricted to admin sessions of this application.
 */
export const PATCH: RequestHandler = async ({ params, request, locals }) => {
	const session = (locals as any).session;
	if (!session || session.user?.role !== 'admin') {
		return json({ status: 'unauthorized', reason: 'Reviewer (admin) session required.' }, { status: 403 });
	}
	if (!CANDIDATE_ID.test(params.id ?? '')) {
		return json({ status: 'not_found', id: params.id }, { status: 404 });
	}
	if (!process.env.LLMOPS_REVIEW_TOKEN) {
		return json(
			{ status: 'unauthorized', reason: 'LLMOPS_REVIEW_TOKEN (kb:review scope) is not configured on this server.' },
			{ status: 403 }
		);
	}
	let body: any;
	try {
		body = await request.json();
	} catch {
		return json({ status: 'invalid_argument', argument: 'body', reason: 'JSON body expected.' }, { status: 400 });
	}
	const payload = {
		action: body?.action,
		reviewer: body?.reviewer,
		reason: body?.reason,
		amended_content: body?.amended_content
	};
	try {
		const res = await llmopsFetch(
			`/api/knowledge/candidates/${params.id}`,
			{ method: 'PATCH', body: JSON.stringify(payload) },
			{ review: true }
		);
		return json(await res.json(), { status: res.status });
	} catch (err: any) {
		return json({ status: 'error', reason: `LLMOps API unreachable: ${err?.message || err}` }, { status: 502 });
	}
};
