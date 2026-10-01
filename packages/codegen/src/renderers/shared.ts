import type { WireRequest } from '../types.js';

export function quote(value: string): string {
  return JSON.stringify(value).replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
}

export function shellQuote(value: string): string {
  return "'" + value.replace(/'/g, "'\\''") + "'";
}

export function rubyQuote(value: string): string {
  return "'" + value.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'";
}

export function javaQuote(value: string): string {
  let result = '"';
  for (const char of value) {
    const code = char.charCodeAt(0);
    if (char === '"') result += '\\"';
    else if (char === '\\') result += '\\\\';
    else if (char === '\n') result += '\\n';
    else if (char === '\r') result += '\\r';
    else if (char === '\t') result += '\\t';
    else if (code < 32) result += '\\' + code.toString(8).padStart(3, '0');
    else result += char;
  }
  return result + '"';
}

export function staticHeaders(request: WireRequest): [string, string][] {
  return Object.entries(request.headers).filter(([name]) => name.toLowerCase() !== request.auth.header.toLowerCase());
}

export function bodyJson(request: WireRequest): string {
  return JSON.stringify(request.body);
}

export function validateEnv(request: WireRequest): void {
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(request.auth.env)) {
    throw new Error('API key environment variable must be a valid environment variable name.');
  }
}
