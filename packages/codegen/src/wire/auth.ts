import { API_KEY_ENV } from '../config/placeholders.js';
import { getProtocol } from '../config/protocols.js';
import type { AuthType, RequestOptions, WireRequest } from '../types.js';
const AUTH: Readonly<Record<AuthType, { header: string; prefix: string }>> = {
  bearer: { header: 'Authorization', prefix: 'Bearer ' },
  'x-api-key': { header: 'x-api-key', prefix: '' },
  'x-goog-api-key': { header: 'x-goog-api-key', prefix: '' },
};
export function buildAuth(options: RequestOptions): WireRequest['auth'] {
  const type = options.auth ?? getProtocol(options.protocol).auth;
  if (!Object.hasOwn(AUTH, type)) throw new Error(`Unsupported auth type: ${type}`);
  const env = options.apiKeyEnv ?? API_KEY_ENV;
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(env)) throw new Error('apiKeyEnv must be an environment variable name');
  return { ...AUTH[type], env };
}
export function buildHeaders(options: RequestOptions): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...getProtocol(options.protocol).headers };
  const authHeader = buildAuth(options).header.toLowerCase();
  for (const [key, value] of Object.entries(options.headers ?? {})) {
    if (!/^[!#$%&'*+.^_`|~\w-]+$/.test(key) || /[\r\n]/.test(value)) throw new Error('Invalid HTTP header');
    if (key.toLowerCase() === authHeader) throw new Error('Pass credentials through the API key environment variable');
    if (key.toLowerCase() === 'content-type' && value.toLowerCase() !== 'application/json') throw new Error('Only application/json bodies are supported');
    const oldKey = Object.keys(headers).find(old => old.toLowerCase() === key.toLowerCase());
    if (oldKey) delete headers[oldKey];
    headers[key] = value;
  }
  return headers;
}
