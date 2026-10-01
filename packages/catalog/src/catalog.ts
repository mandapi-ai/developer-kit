import type {
  FindModelsOptions,
  MandapiModel,
  MandapiModelInput,
  ModelCatalog,
  ProtocolId,
} from './types.js';

const protocolIds: readonly ProtocolId[] = ['chat', 'responses', 'messages', 'gemini'];

function snapshotModel(input: MandapiModelInput): MandapiModel {
  if (typeof input.id !== 'string' || input.id.trim().length === 0) {
    throw new Error('Model ID must be a non-empty string');
  }
  if (typeof input.name !== 'string' || input.name.trim().length === 0) {
    throw new Error(`Model ${input.id} must have a non-empty name`);
  }
  if (!Array.isArray(input.protocols)) {
    throw new Error(`Model ${input.id} must declare a protocols array`);
  }
  const seen = new Set<ProtocolId>();
  let preferredCount = 0;
  for (const protocol of input.protocols) {
    if (!protocolIds.includes(protocol.id)) {
      throw new Error(`Unsupported protocol ${protocol.id} for model ${input.id}`);
    }
    if (seen.has(protocol.id)) {
      throw new Error(`Duplicate protocol ${protocol.id} for model ${input.id}`);
    }
    seen.add(protocol.id);
    if (protocol.preferred === true) preferredCount += 1;
  }
  if (preferredCount > 1) {
    throw new Error(`Model ${input.id} declares multiple preferred protocols`);
  }
  const protocols = Object.freeze(input.protocols.map((protocol) => Object.freeze({ ...protocol })));
  const preferredProtocol = protocols.find((protocol) => protocol.preferred === true)?.id ?? protocols[0]?.id;
  // Ignore a derived value on an existing catalog model passed back as input.
  // Only the declarations above determine routing in the resulting catalog.
  const { preferredProtocol: _derived, ...source } = input as MandapiModel;
  return Object.freeze({
    ...source,
    protocols,
    capabilities: Object.freeze({ ...input.capabilities }),
    ...(input.limits === undefined ? {} : { limits: Object.freeze({ ...input.limits }) }),
    ...(input.pricing === undefined ? {} : { pricing: Object.freeze({ ...input.pricing }) }),
    ...(input.runtime === undefined ? {} : { runtime: Object.freeze({ ...input.runtime }) }),
    ...(preferredProtocol === undefined ? {} : { preferredProtocol }),
  });
}

/**
 * Create an immutable, independent catalog snapshot.
 * No model-name heuristics or network requests are performed.
 */
export function createCatalog(inputs: readonly MandapiModelInput[]): ModelCatalog {
  const byId = new Map<string, MandapiModel>();
  for (const input of inputs) {
    if (byId.has(input.id)) throw new Error(`Duplicate model ID: ${input.id}`);
    const model = snapshotModel(input);
    byId.set(model.id, model);
  }
  const models = Object.freeze([...byId.values()]);
  const getModel = (id: string): MandapiModel | undefined => byId.get(id);
  const findModels = (options: FindModelsOptions = {}): readonly MandapiModel[] => Object.freeze(
    models.filter((model) =>
      (options.capability === undefined || model.capabilities[options.capability] === true)
      && (options.protocol === undefined || model.protocols.some((protocol) => protocol.id === options.protocol)),
    ),
  );
  return Object.freeze({
    getModel,
    get: getModel,
    listModels: () => models,
    findModels,
    resolvePreferredProtocol: (id: string) => getModel(id)?.preferredProtocol,
  });
}
