import type { WireRequest } from '../types.js';
import { bodyJson, quote, staticHeaders, validateEnv } from './shared.js';

export function renderTypeScript(request: WireRequest): string {
  validateEnv(request);
  const headers = [...staticHeaders(request).map(([name, value]) => `    ${quote(name)}: ${quote(value)},`),
    `    ${quote(request.auth.header)}: ${quote(request.auth.prefix)} + apiKey,`].join('\n');
  return `// Node.js 22+; also valid TypeScript.
const apiKey = process.env[${quote(request.auth.env)}];
if (!apiKey) throw new Error(${quote('Set ' + request.auth.env + ' before running this example.')});
const baseOverride = process.env.MANDAPI_BASE_URL;
const url = baseOverride ? baseOverride.replace(/\\/+$/, "").replace(/\\/v1$/, "") + ${quote(request.path)} : ${quote(request.url)};
const response = await fetch(url, {
  method: ${quote(request.method)},
  headers: {
${headers}
  },
  body: ${quote(bodyJson(request))},
});
const text = await response.text();
if (!response.ok) throw new Error("HTTP " + response.status + ": " + text);
console.log(text);
`;
}
