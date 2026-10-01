import type { AuthType, ProtocolId } from '../types.js';
export interface ProtocolDefinition { path: string; auth: AuthType; headers: Readonly<Record<string, string>> }
/** Single source of truth for gateway routes, auth, and protocol headers. */
export const PROTOCOLS: Readonly<Record<ProtocolId, ProtocolDefinition>> = Object.freeze({
  chat: Object.freeze({ path: '/v1/chat/completions', auth: 'bearer', headers: Object.freeze({}) }),
  responses: Object.freeze({ path: '/v1/responses', auth: 'bearer', headers: Object.freeze({}) }),
  messages: Object.freeze({ path: '/v1/messages', auth: 'bearer', headers: Object.freeze({ 'anthropic-version': '2023-06-01' }) }),
  gemini: Object.freeze({ path: '/gemini/v1beta/models/{model}:generateContent', auth: 'bearer', headers: Object.freeze({}) }),
});
export function getProtocol(id: ProtocolId): ProtocolDefinition {
  if (!Object.hasOwn(PROTOCOLS, id)) throw new Error(`Unsupported protocol: ${id}`);
  return PROTOCOLS[id];
}
