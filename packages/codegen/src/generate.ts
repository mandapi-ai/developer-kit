import { validateLanguage } from './config/languages.js';
import { render } from './renderers/index.js';
import type { GenerateForModelOptions, GenerateOptions } from './types.js';
import { buildRequest } from './wire/request.js';
export function generateCode(options: GenerateOptions): string {
  validateLanguage(options.language);
  return render(buildRequest(options), options.language);
}
export function generateForModel(options: GenerateForModelOptions): string {
  const model = options.catalog.getModel(options.model);
  const protocol = options.protocol ?? options.catalog.resolvePreferredProtocol(options.model) ?? options.fallbackProtocol;
  if (!model && !options.protocol && !options.fallbackProtocol) throw new Error(`Unknown model: ${options.model}`);
  if (!protocol) throw new Error(`No protocol declared for model: ${options.model}`);
  if (model && !model.protocols.some(support => support.id === protocol)) throw new Error(`Protocol ${protocol} is not declared for model ${options.model}`);
  return generateCode({ ...options, protocol });
}
