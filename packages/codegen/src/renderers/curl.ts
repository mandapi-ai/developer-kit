import type { WireRequest } from '../types.js';
import { bodyJson, shellQuote, staticHeaders, validateEnv } from './shared.js';

export function renderCurl(request: WireRequest): string {
  validateEnv(request);
  const headers = staticHeaders(request).map(([name, value]) => `  --header ${shellQuote(name + ': ' + value)} \\`).join('\n');
  return `#!/bin/sh
set -eu
# Requires curl 7.76+ for --fail-with-body.
api_key="\${${request.auth.env}:?Set ${request.auth.env} before running this example.}"
url=${shellQuote(request.url)}
if [ -n "\${MANDAPI_BASE_URL:-}" ]; then
  base_url="$MANDAPI_BASE_URL"
  while [ "\${base_url%/}" != "$base_url" ]; do base_url="\${base_url%/}"; done
  case "$base_url" in */v1) base_url="\${base_url%/v1}" ;; esac
  path=${shellQuote(request.path)}
  url="$base_url$path"
fi
auth_header=${shellQuote(request.auth.header + ': ' + request.auth.prefix)}"$api_key"
curl --fail-with-body --silent --show-error \\
  --request ${shellQuote(request.method)} \\
  --url "$url" \\
${headers}
  --header "$auth_header" \\
  --data-binary ${shellQuote(bodyJson(request))}
`;
}
