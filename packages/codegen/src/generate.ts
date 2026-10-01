import { validateLanguage } from './config/languages.js';
import { render } from './renderers/index.js';
import type { GenerateOptions } from './types.js';
import { buildRequest } from './wire/request.js';
export function generateCode(options: GenerateOptions): string {
  validateLanguage(options.language);
  return render(buildRequest(options), options.language);
}
