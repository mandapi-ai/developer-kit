import { createCatalog } from './catalog.js';
import { fixtureModels } from './fixtures/models.js';
import type { FindModelsOptions } from './types.js';

export { createCatalog } from './catalog.js';
export { fixtureSources } from './fixtures/models.js';
export type {
  FindModelsOptions,
  MandapiModel,
  MandapiModelInput,
  ModelCapabilities,
  ModelCapability,
  ModelCatalog,
  ProtocolId,
  ProtocolSupport,
} from './types.js';

/** Static public metadata fixtures; not a production catalog API. */
export const catalog = createCatalog(fixtureModels);
export const getModel = (id: string) => catalog.getModel(id);
export const get = (id: string) => catalog.get(id);
export const listModels = () => catalog.listModels();
export const findModels = (options: FindModelsOptions = {}) => catalog.findModels(options);
export const resolvePreferredProtocol = (id: string) => catalog.resolvePreferredProtocol(id);
