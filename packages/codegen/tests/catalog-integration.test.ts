import { describe, expect, it } from 'vitest';
import { catalog, createCatalog } from '../../catalog/src/index.js';
import { generateForModel } from '../src/index.js';
const options = { catalog, language: 'python' as const, baseUrl: 'https://gateway.example' };
describe('catalog-driven code generation', () => {
  it('selects Claude Messages from declared catalog data', () => {
    const code = generateForModel({ ...options, model: 'claude-opus-5' });
    expect(code).toContain('/v1/messages');
    expect(code).toContain('anthropic-version');
  });
  it('selects a confirmed native Gemini model', () => {
    const code = generateForModel({ ...options, model: 'gemini-3.1-pro-preview' });
    expect(code).toContain('/gemini/v1beta/models/gemini-3.1-pro-preview:generateContent');
    expect(code).toContain('contents');
  });
  it('lets an explicit supported override win', () => {
    expect(generateForModel({ ...options, model: 'claude-opus-5', protocol: 'chat' })).toContain('/v1/chat/completions');
  });
  it('rejects an undeclared protocol and an unknown model', () => {
    expect(() => generateForModel({ ...options, model: 'gpt-6-sol', protocol: 'responses' })).toThrow('not declared');
    expect(() => generateForModel({ ...options, model: 'unknown' })).toThrow('Unknown model');
  });
  it('uses caller-supplied fallback only when catalog data is missing', () => {
    expect(generateForModel({ ...options, model: 'unknown', fallbackProtocol: 'responses' })).toContain('/v1/responses');
  });
  it('ignores model-name prefixes when explicit data disagrees', () => {
    const custom = createCatalog([{ id: 'claude-looking-name', name: 'Test', protocols: [{ id: 'gemini', preferred: true }], capabilities: {} }]);
    expect(generateForModel({ ...options, catalog: custom, model: 'claude-looking-name' })).toContain(':generateContent');
  });
});
