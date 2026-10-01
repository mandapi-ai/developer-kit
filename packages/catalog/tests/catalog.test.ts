import { describe, expect, it } from 'vitest';
import {
  catalog,
  createCatalog,
  findModels,
  getModel,
  listModels,
  resolvePreferredProtocol,
  type MandapiModelInput,
} from '../src/index.js';

const custom: MandapiModelInput[] = [
  {
    id: 'claude-looking-but-chat',
    name: 'Unrelated custom model',
    protocols: [{ id: 'chat' }],
    capabilities: { tools: true, text: false },
  },
  {
    id: 'gpt-looking-but-gemini',
    name: 'Another custom model',
    protocols: [{ id: 'chat' }, { id: 'gemini', preferred: true }],
    capabilities: { tools: false, vision: true },
  },
  { id: 'no-protocol', name: 'Unspecified', protocols: [], capabilities: {} },
];

describe('catalog lookup and fixtures', () => {
  it('returns an exact model ID and provides the get alias', () => {
    const model = getModel('gpt-6-sol');
    expect(model?.id).toBe('gpt-6-sol');
    expect(model?.protocols).toEqual([{ id: 'chat', preferred: true }]);
    expect(model?.preferredProtocol).toBe('chat');
    expect(catalog.get('gpt-6-sol')).toBe(model);
    expect(model?.capabilities).toEqual({});
  });

  it('returns undefined for unknown models, including case differences', () => {
    expect(getModel('not-present')).toBeUndefined();
    expect(catalog.get('GPT-6-SOL')).toBeUndefined();
    expect(resolvePreferredProtocol('not-present')).toBeUndefined();
  });

  it('includes nine representative official IDs without claiming live tests', () => {
    expect(listModels()).toHaveLength(9);
    expect(listModels().flatMap((model) => model.protocols).some((protocol) => protocol.tested === true)).toBe(false);
    expect(getModel('claude-opus-5')?.pricing).toEqual({ currency: 'BRL', input: 2, output: 10, unit: 'per_million_tokens' });
    expect(getModel('gemini-3.1-pro-preview')?.limits?.context).toBe(1_000_000);
    expect(getModel('gpt-6-sol')?.limits).toBeUndefined();
  });
});

describe('data driven filtering and protocol choice', () => {
  const local = createCatalog(custom);

  it('filters by capabilities explicitly equal to true, never false or missing', () => {
    expect(local.findModels({ capability: 'tools' }).map((model) => model.id)).toEqual(['claude-looking-but-chat']);
    expect(local.findModels({ capability: 'text' })).toEqual([]);
    expect(local.findModels({ capability: 'reasoning' })).toEqual([]);
  });

  it('combines capability and protocol filters', () => {
    expect(local.findModels({ capability: 'vision', protocol: 'gemini' }).map((model) => model.id)).toEqual(['gpt-looking-but-gemini']);
    expect(local.findModels({ capability: 'tools', protocol: 'gemini' })).toEqual([]);
    expect(findModels({ protocol: 'messages' }).map((model) => model.id)).toEqual(['claude-opus-5', 'claude-sonnet-5']);
  });

  it('uses preferred flags, then declared data order, without name heuristics', () => {
    expect(local.resolvePreferredProtocol('claude-looking-but-chat')).toBe('chat');
    expect(local.resolvePreferredProtocol('gpt-looking-but-gemini')).toBe('gemini');
    expect(local.resolvePreferredProtocol('no-protocol')).toBeUndefined();
    const ordered = createCatalog([{ id: 'gpt-arbitrary', name: 'Ordered declarations', protocols: [{ id: 'gemini' }, { id: 'chat' }], capabilities: {} }]);
    expect(ordered.resolvePreferredProtocol('gpt-arbitrary')).toBe('gemini');
    expect(resolvePreferredProtocol('claude-opus-5')).toBe('messages');
    expect(resolvePreferredProtocol('gemini-3.1-pro-preview')).toBe('gemini');
  });

  it('uses only protocol declarations to derive preferredProtocol', () => {
    const model = { ...custom[0]!, preferredProtocol: 'responses' as const };
    expect(createCatalog([model]).get(model.id)?.preferredProtocol).toBe('chat');
  });
});

describe('catalog invariants', () => {
  it('rejects duplicate model IDs and multiple preferred protocols', () => {
    expect(() => createCatalog([custom[0]!, custom[0]!])).toThrow(/Duplicate model ID/);
    expect(() => createCatalog([{
      id: 'ambiguous', name: 'Ambiguous', capabilities: {},
      protocols: [{ id: 'chat', preferred: true }, { id: 'responses', preferred: true }],
    }])).toThrow(/multiple preferred protocols/);
  });

  it('rejects duplicate or unsupported protocol declarations', () => {
    expect(() => createCatalog([{
      id: 'duplicate-protocol', name: 'Duplicate', capabilities: {},
      protocols: [{ id: 'chat' }, { id: 'chat' }],
    }])).toThrow(/Duplicate protocol/);
    expect(() => createCatalog([{
      id: 'unsupported-protocol', name: 'Unsupported', capabilities: {},
      protocols: [{ id: 'unknown' as 'chat' }],
    }])).toThrow(/Unsupported protocol/);
  });

  it('isolates the catalog from mutations of source data', () => {
    const input: MandapiModelInput = {
      id: 'mutable-source', name: 'Source',
      protocols: [{ id: 'messages', preferred: true }],
      capabilities: { tools: true }, limits: { context: 200 },
      pricing: { input: 1 }, runtime: { status: 'documented' },
    };
    const local = createCatalog([input]);
    (input.protocols[0] as { id: string }).id = 'chat';
    (input.capabilities as { tools: boolean }).tools = false;
    (input.limits as { context: number }).context = 1;
    expect(local.resolvePreferredProtocol(input.id)).toBe('messages');
    expect(local.get(input.id)?.capabilities.tools).toBe(true);
    expect(local.get(input.id)?.limits?.context).toBe(200);
  });

  it('freezes models, nested metadata, list and filtered collections', () => {
    const model = getModel('claude-opus-5')!;
    for (const value of [catalog, model, model.protocols, model.protocols[0], model.capabilities, model.limits, model.pricing, model.runtime, listModels(), findModels({ protocol: 'chat' })]) {
      expect(Object.isFrozen(value)).toBe(true);
    }
    expect(() => { (model.protocols as unknown[]).push({ id: 'gemini' }); }).toThrow();
  });
});
