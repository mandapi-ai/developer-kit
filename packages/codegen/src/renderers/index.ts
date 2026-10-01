import type { WireRequest } from '../types.js';
import { renderPython } from './python.js';
import { renderTypeScript } from './typescript.js';
import { renderCurl } from './curl.js';
import { renderGo } from './go.js';
import { renderJava } from './java.js';
import { renderCSharp } from './csharp.js';
import { renderRuby } from './ruby.js';

export { renderPython, renderTypeScript, renderCurl, renderGo, renderJava, renderCSharp, renderRuby };

const RENDERERS = {
  python: renderPython,
  typescript: renderTypeScript,
  curl: renderCurl,
  go: renderGo,
  java: renderJava,
  csharp: renderCSharp,
  ruby: renderRuby,
} as const;

export function render(request: WireRequest, language: keyof typeof RENDERERS): string {
  const renderer = RENDERERS[language];
  if (!renderer) throw new Error(`Unsupported language: ${String(language)}`);
  return renderer(request);
}
