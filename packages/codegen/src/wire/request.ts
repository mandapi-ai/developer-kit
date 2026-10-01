import type { RequestOptions, WireRequest } from '../types.js';
import { buildAuth, buildHeaders } from './auth.js';
import { buildBody } from './body.js';
import { buildEndpoint } from './endpoint.js';
export function buildRequest(options: RequestOptions): WireRequest {
  const body = buildBody(options);
  return { method: 'POST', ...buildEndpoint(options), headers: buildHeaders(options), auth: buildAuth(options), body };
}
