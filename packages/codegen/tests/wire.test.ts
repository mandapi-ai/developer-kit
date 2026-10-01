import { describe, expect, it } from 'vitest';
import { buildBody, buildRequest, generateCode, PROTOCOLS } from '../src/index.js';
import type { GenerateOptions } from '../src/index.js';
const options = { model: 'arbitrary-model', baseUrl: 'https://gateway.example/tenant/', prompt: 'hello', language: 'python' as const };
describe('shared wire contract', () => {
  it.each([
    ['chat', '/v1/chat/completions', { model: 'arbitrary-model', messages: [{ role: 'user', content: 'hello' }] }],
    ['responses', '/v1/responses', { model: 'arbitrary-model', input: [{ role: 'user', content: 'hello' }] }],
    ['messages', '/v1/messages', { model: 'arbitrary-model', max_tokens: 1024, messages: [{ role: 'user', content: 'hello' }] }],
    ['gemini', '/gemini/v1beta/models/arbitrary-model:generateContent', { contents: [{ role: 'user', parts: [{ text: 'hello' }] }] }],
  ] as const)('%s creates the exact protocol request', (protocol, path, body) => {
    const request = buildRequest({ ...options, protocol });
    expect(request.url).toBe(`https://gateway.example/tenant${path}`);
    expect(request.body).toEqual(body);
    expect(request.headers['Content-Type']).toBe('application/json');
    expect(request.auth).toEqual({ header: 'Authorization', prefix: 'Bearer ', env: 'MANDAPI_API_KEY' });
    expect(request.headers['anthropic-version']).toBe(protocol === 'messages' ? '2023-06-01' : undefined);
  });
  it('accepts an SDK /v1 base without a duplicate /v1', () => {
    expect(buildRequest({ ...options, protocol: 'chat', baseUrl: 'http://localhost:8080/v1/' }).url).toBe('http://localhost:8080/v1/chat/completions');
  });
  it('encodes a model only in a path and preserves the exact body model', () => {
    const model = 'id/with space?';
    expect(buildRequest({ ...options, model, protocol: 'gemini' }).path).toBe('/gemini/v1beta/models/id%2Fwith%20space%3F:generateContent');
    expect(buildBody({ ...options, model, protocol: 'chat' }).model).toBe(model);
  });
  it('allows an explicit route and auth without a renderer-specific decision', () => {
    const request = buildRequest({ ...options, protocol: 'gemini', endpointPath: '/v1beta/models/{model}:generateContent', auth: 'x-goog-api-key' });
    expect(request.url).toBe('https://gateway.example/tenant/v1beta/models/arbitrary-model:generateContent');
    expect(request.auth.header).toBe('x-goog-api-key');
  });
  it('preserves native extension fields and does not mutate caller data', () => {
    const body = { contents: [{ role: 'user', parts: [{ text: 'test' }] }], cachedContent: 'cached/123', generationConfig: { temperature: 0.2 } };
    const built = buildBody({ model: 'native', baseUrl: options.baseUrl, protocol: 'gemini', body });
    expect(built).toEqual(body);
    (built.generationConfig as { temperature: number }).temperature = 0.9;
    expect(body.generationConfig.temperature).toBe(0.2);
  });
  it('converts system/history for Messages and Gemini without changing history', () => {
    const messages = [{ role: 'user' as const, content: 'hello' }, { role: 'assistant' as const, content: 'hi' }];
    const input = { model: 'any', baseUrl: options.baseUrl, messages, system: 'rules', maxTokens: 200 };
    expect(buildBody({ ...input, protocol: 'messages' })).toEqual({ model: 'any', system: 'rules', max_tokens: 200, messages });
    expect(buildBody({ ...input, protocol: 'gemini' })).toEqual({ contents: [{ role: 'user', parts: [{ text: 'hello' }] }, { role: 'model', parts: [{ text: 'hi' }] }], systemInstruction: { parts: [{ text: 'rules' }] }, generationConfig: { maxOutputTokens: 200 } });
    expect(messages).toHaveLength(2);
  });
  it('preserves protocol-native Responses input, tools, and reasoning', () => {
    const body = { input: 'hello', tools: [{ type: 'function', name: 'lookup', parameters: { type: 'object' } }], reasoning: { effort: 'low' } };
    expect(buildBody({ model: 'any', baseUrl: options.baseUrl, protocol: 'responses', body })).toEqual({ ...body, model: 'any' });
  });
  it('rejects a contradictory native body model', () => {
    expect(() => buildBody({ model: 'a', protocol: 'chat', baseUrl: options.baseUrl, body: { model: 'b', messages: [] } })).toThrow('model must match');
  });
  it('rejects unsupported streaming instead of silently changing behavior', () => {
    expect(() => buildBody({ ...options, protocol: 'chat', parameters: { stream: true } })).toThrow('Streaming');
  });
  it('rejects lossy JSON and reserved field overrides', () => {
    expect(() => buildBody({ ...options, protocol: 'chat', parameters: { temperature: NaN } })).toThrow('finite JSON');
    expect(() => buildBody({ ...options, protocol: 'chat', parameters: { model: 'other' } })).toThrow('cannot override');
  });
  it.each(['', 'ftp://host', 'https://user:secret@host', 'https://host/?key=secret'])('rejects invalid or credential-bearing base URL %s', baseUrl => {
    expect(() => buildRequest({ ...options, protocol: 'chat', baseUrl })).toThrow('baseUrl');
  });
  it('rejects unknown protocol, language, and literal credentials', () => {
    expect(() => buildRequest({ ...options, protocol: 'invalid' as 'chat' })).toThrow('Unsupported protocol');
    expect(() => generateCode({ ...options, protocol: 'chat', language: 'invalid' } as unknown as GenerateOptions)).toThrow('Unsupported language');
    expect(() => buildRequest({ ...options, protocol: 'chat', headers: { Authorization: 'secret' } })).toThrow('environment variable');
  });
  it('keeps protocol configuration immutable', () => {
    expect(Object.isFrozen(PROTOCOLS)).toBe(true);
    expect(Object.isFrozen(PROTOCOLS.messages.headers)).toBe(true);
  });
});
