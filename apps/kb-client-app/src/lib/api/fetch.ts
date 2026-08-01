/**
 * apiFetch — Typed fetch wrapper for SvelteKit API routes.
 *
 * Features:
 * - Auto JSON serialisation / deserialisation
 * - Normalised error shape: { data, error }
 * - Automatic Content-Type header
 * - Preserves full TypeScript inference on response body
 *
 * @usage
 *   import { apiFetch } from '$lib/api/fetch';
 *
 *   const { data, error } = await apiFetch<Item>('/api/demo', {
 *     method: 'POST',
 *     body: { name: 'My item' },
 *   });
 *   if (error) { toast(error.message, { variant: 'error' }); return; }
 *   console.log(data); // typed as Item
 */

export type ApiError = {
  status: number;
  message: string;
  details?: unknown;
};

export type ApiResult<T> =
  | { data: T; error: null }
  | { data: null; error: ApiError };

type ApiFetchOptions = Omit<RequestInit, 'body'> & {
  body?: unknown;
};

export async function apiFetch<T = unknown>(
  url: string,
  options: ApiFetchOptions = {}
): Promise<ApiResult<T>> {
  const { body, headers, ...rest } = options;

  const init: RequestInit = {
    ...rest,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  };

  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(url, init);

    if (!response.ok) {
      let details: unknown;
      try { details = await response.json(); } catch { /* ignore */ }
      return {
        data: null,
        error: {
          status: response.status,
          message: (details as { message?: string })?.message ?? response.statusText,
          details,
        },
      };
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return { data: undefined as T, error: null };
    }

    const data = (await response.json()) as T;
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error: {
        status: 0,
        message: err instanceof Error ? err.message : 'Network error',
      },
    };
  }
}
