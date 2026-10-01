import { getProtocol } from '../config/protocols.js';
import type { JsonObject, JsonValue, RequestOptions } from '../types.js';
import { buildMessages } from './messages.js';
function assertJson(value: unknown, seen = new Set<object>()): asserts value is JsonValue {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return;
  if (typeof value === 'number' && Number.isFinite(value)) return;
  if (typeof value !== 'object' || value === null) throw new Error('Body must contain only finite JSON values');
  if (seen.has(value)) throw new Error('Body must not contain cycles');
  if (!Array.isArray(value) && Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null) throw new Error('Body must contain plain JSON objects');
  seen.add(value);
  for (const item of Object.values(value)) assertJson(item, seen);
  seen.delete(value);
}
function validateBody(body: JsonObject, options: RequestOptions): void {
  if (body.stream === true) throw new Error('Streaming is not supported in P2; use non-streaming requests');
  if (options.protocol !== 'gemini' && body.model !== options.model) throw new Error('Body model must match the requested model');
  if (options.protocol === 'chat' || options.protocol === 'messages') {
    if (!Array.isArray(body.messages) || body.messages.length === 0) throw new Error('Body requires non-empty messages');
  }
  if (options.protocol === 'messages' && (!Number.isInteger(body.max_tokens) || Number(body.max_tokens) <= 0)) throw new Error('Messages requires positive integer max_tokens');
  if (options.protocol === 'responses' && body.input === undefined) throw new Error('Responses requires input');
  if (options.protocol === 'gemini' && (!Array.isArray(body.contents) || body.contents.length === 0)) throw new Error('Gemini requires non-empty contents');
}
/** Public, pure request-body builder shared with future real request callers. */
export function buildBody(options: RequestOptions): JsonObject {
  getProtocol(options.protocol);
  if (typeof options.model !== 'string' || !options.model.trim()) throw new Error('model is required');
  if (options.maxTokens !== undefined && (!Number.isInteger(options.maxTokens) || options.maxTokens <= 0)) throw new Error('maxTokens must be a positive integer');
  if (options.body && (options.parameters || options.messages || options.prompt !== undefined || options.system !== undefined || options.maxTokens !== undefined)) throw new Error('Use a native body or high-level input options, not both');
  let body: JsonObject;
  if (options.body) {
    if (Array.isArray(options.body) || typeof options.body !== 'object') throw new Error('Native body must be a JSON object');
    assertJson(options.body);
    body = JSON.parse(JSON.stringify(options.body)) as JsonObject;
    if (options.protocol !== 'gemini') body = { ...body, model: body.model ?? options.model };
  } else {
    const messages = buildMessages(options);
    switch (options.protocol) {
      case 'chat':
        body = { model: options.model, messages: messages.map(message => ({ ...message })) };
        if (options.maxTokens !== undefined) body.max_tokens = options.maxTokens;
        break;
      case 'responses':
        body = { model: options.model, input: messages.map(message => ({ ...message })) };
        if (options.maxTokens !== undefined) body.max_output_tokens = options.maxTokens;
        break;
      case 'messages': {
        const system = messages.filter(m => m.role === 'system' || m.role === 'developer').map(m => m.content).join('\n\n');
        body = { model: options.model, max_tokens: options.maxTokens ?? 1024, messages: messages.filter(m => m.role !== 'system' && m.role !== 'developer').map(m => ({ ...m })) };
        if (system) body.system = system;
        break;
      }
      case 'gemini': {
        const system = messages.filter(m => m.role === 'system' || m.role === 'developer').map(m => ({ text: m.content }));
        body = { contents: messages.filter(m => m.role !== 'system' && m.role !== 'developer').map(m => ({ role: m.role === 'assistant' ? 'model' : 'user', parts: [{ text: m.content }] })) };
        if (system.length) body.systemInstruction = { parts: system };
        if (options.maxTokens !== undefined) body.generationConfig = { maxOutputTokens: options.maxTokens };
        break;
      }
    }
    if (options.parameters) {
      assertJson(options.parameters);
      for (const [key, value] of Object.entries(options.parameters)) {
        if (Object.hasOwn(body, key)) throw new Error(`parameters cannot override ${key}; use native body for complete protocol control`);
        Object.defineProperty(body, key, { value, enumerable: true, writable: true, configurable: true });
      }
    }
  }
  assertJson(body);
  validateBody(body, options);
  return JSON.parse(JSON.stringify(body)) as JsonObject;
}
