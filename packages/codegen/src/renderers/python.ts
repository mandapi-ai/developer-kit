import type { WireRequest } from '../types.js';
import { bodyJson, quote, staticHeaders, validateEnv } from './shared.js';

export function renderPython(request: WireRequest): string {
  validateEnv(request);
  const headers = Object.fromEntries(staticHeaders(request));
  return `import json
import os
import urllib.error
import urllib.request

api_key = os.environ.get(${quote(request.auth.env)})
if not api_key:
    raise RuntimeError(${quote('Set ' + request.auth.env + ' before running this example.')})
base_override = os.environ.get("MANDAPI_BASE_URL")
if base_override:
    base_override = base_override.rstrip("/")
    if base_override.endswith("/v1"):
        base_override = base_override[:-3]
url = base_override.rstrip("/") + ${quote(request.path)} if base_override else ${quote(request.url)}
headers = json.loads(${quote(JSON.stringify(headers))})
headers[${quote(request.auth.header)}] = ${quote(request.auth.prefix)} + api_key
payload = ${quote(bodyJson(request))}.encode("utf-8")
request = urllib.request.Request(url, data=payload, headers=headers, method=${quote(request.method)})

try:
    with urllib.request.urlopen(request, timeout=300) as response:
        print(response.read().decode("utf-8"))
except urllib.error.HTTPError as error:
    detail = error.read().decode("utf-8", errors="replace")
    raise RuntimeError(f"HTTP {error.code}: {detail}") from error
`;
}
