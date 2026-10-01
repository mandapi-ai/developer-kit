import { getProtocol } from '../config/protocols.js';
import type { RequestOptions } from '../types.js';
export function buildEndpoint(options: RequestOptions): { baseUrl: string; path: string; url: string } {
  if (typeof options.baseUrl !== 'string' || !options.baseUrl.trim()) throw new Error('baseUrl is required');
  let base: URL;
  try { base = new URL(options.baseUrl); } catch { throw new Error('baseUrl must be an absolute HTTP(S) URL'); }
  if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password || base.search || base.hash) {
    throw new Error('baseUrl must be HTTP(S), without credentials, query, or fragment');
  }
  // Accept an OpenAI SDK /v1 base as well as a gateway root, without duplicate /v1.
  base.pathname = base.pathname.replace(/\/+$/, '').replace(/\/v1$/, '');
  const baseUrl = base.toString().replace(/\/+$/, '');
  const template = options.endpointPath ?? getProtocol(options.protocol).path;
  if (!template.startsWith('/') || template.startsWith('//') || /[?#\r\n]/.test(template)) throw new Error('endpointPath must be an absolute path without query or fragment');
  const path = template.replaceAll('{model}', encodeURIComponent(options.model));
  if (/[{}]/.test(path)) throw new Error('Unknown endpointPath placeholder');
  return { baseUrl, path, url: `${baseUrl}${path}` };
}
