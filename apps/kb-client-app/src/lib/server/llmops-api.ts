/**
 * Server-side client of the LLMOps REST API (KB candidate cycle).
 *
 * - LLMOPS_API_URL: base URL of the LLMOps server (default http://localhost:8000).
 * - LLMOPS_REVIEW_TOKEN: token carrying the `kb:review` scope (ENGAGEMENT_TOKENS on the
 *   server). Never sent to the browser. Required to review candidates and to read the
 *   content of candidates blocked by the anonymization check.
 * - SERVER_TOKEN: read-only fallback token.
 */
export function llmopsBaseUrl(): string {
	return (process.env.LLMOPS_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
}

export async function llmopsFetch(
	path: string,
	init: RequestInit = {},
	options: { review?: boolean } = {}
): Promise<Response> {
	const token = options.review
		? process.env.LLMOPS_REVIEW_TOKEN
		: process.env.LLMOPS_REVIEW_TOKEN || process.env.SERVER_TOKEN || process.env.LLMOPS_AUTH_TOKEN;
	const headers = new Headers(init.headers);
	headers.set('Accept', 'application/json');
	if (token) headers.set('Authorization', `Bearer ${token}`);
	if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
	return fetch(`${llmopsBaseUrl()}${path}`, { ...init, headers });
}
