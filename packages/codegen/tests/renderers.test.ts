import { spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, join, resolve, sep } from 'node:path';
import { describe, expect, it } from 'vitest';
import { LANGUAGES } from '../src/config/languages.js';
import { generateCode } from '../src/generate.js';
import { render } from '../src/renderers/index.js';
import { buildBody } from '../src/wire/body.js';
import { buildRequest } from '../src/wire/request.js';
import type { Language, ProtocolId, RequestOptions } from '../src/types.js';

const protocols: ProtocolId[] = ['chat', 'responses', 'messages', 'gemini'];
const complexPrompt = 'Quotes " and apostrophe \' and slash \\ and\nnew line; true false null; 中文 😀; #{system("id")}; `tick` $(id) ${value};\u2028end';
const options = (protocol: ProtocolId, baseUrl = 'https://gateway.example/proxy'): RequestOptions => ({
  model: 'test-model/with space',
  protocol,
  baseUrl,
  prompt: complexPrompt,
  system: 'Return valid JSON, preserving true/false strings.',
  maxTokens: 512,
  headers: { 'X-Custom-Header': 'custom-value' },
  parameters: { metadata: { nested: [true, false, null, 3.5, { text: complexPrompt }] } },
});

// Decode the payload expression in each emitted language. This checks the whole
// transmitted JSON, including extension fields, rather than a handful of tokens.
function payloadText(source: string, language: Language): string {
  let literal: string;
  switch (language) {
    case 'python': literal = source.match(/^payload = (.+)\.encode\("utf-8"\)$/m)![1]!; break;
    case 'typescript': literal = source.match(/^  body: (.+),$/m)![1]!; break;
    case 'go': literal = source.match(/^    payload := (.+)$/m)![1]!; break;
    case 'java': literal = source.match(/    String payload = ([\s\S]*?);\n/)![1]!; break;
    case 'csharp': literal = source.match(/^var payload = (.+);$/m)![1]!; break;
    case 'ruby': {
      const start = source.indexOf('request.body = ') + 'request.body = '.length;
      literal = source.slice(start, source.indexOf('\nresponse = ', start));
      return literal.slice(1, -1).replace(/\\(['\\])/g, '$1');
    }
    case 'curl': {
      literal = source.slice(source.lastIndexOf('  --data-binary ') + '  --data-binary '.length).trimEnd();
      return literal.slice(1, -1).replace(/'\\''/g, "'");
    }
  }
  return JSON.parse(literal) as string;
}

describe('seven-language wire preservation', () => {
  for (const protocol of protocols) {
    it.each(LANGUAGES)(`${protocol}: %s carries exactly buildBody() JSON`, language => {
      const input = options(protocol);
      const source = generateCode({ ...input, language });
      expect(JSON.parse(payloadText(source, language))).toEqual(buildBody(input));
      expect(payloadText(source, language)).toBe(JSON.stringify(buildBody(input)));
      expect(source).toContain('MANDAPI_API_KEY');
      expect(source).toContain('MANDAPI_BASE_URL');
      expect(source).not.toContain('AIHUBMIX_API_KEY');
    });
  }

  it('uses the requested key environment without embedding key material', () => {
    for (const language of LANGUAGES) {
      const source = generateCode({ ...options('chat'), apiKeyEnv: 'LOCAL_GATEWAY_KEY', language });
      expect(source).toContain('LOCAL_GATEWAY_KEY');
      expect(source).not.toContain('MANDAPI_API_KEY');
    }
  });

  it('rejects invalid key environment and language names without silent fallback', () => {
    const request = buildRequest(options('chat'));
    expect(() => render({ ...request, auth: { ...request.auth, env: 'KEY;echo injected' } }, 'curl')).toThrow(/environment variable/);
    expect(() => render(request, 'invalid' as Language)).toThrow(/Unsupported language/);
  });
});

interface CapturedRequest { url: string | undefined; method: string | undefined; headers: Record<string, string | string[] | undefined>; rawBody: string }
async function withMock<T>(status: number, run: (baseUrl: string, captured: CapturedRequest[]) => Promise<T>): Promise<T> {
  const captured: CapturedRequest[] = [];
  const server = createServer(async (request, response) => {
    const chunks: Buffer[] = [];
    for await (const chunk of request) chunks.push(Buffer.from(chunk));
    captured.push({ url: request.url, method: request.method, headers: request.headers, rawBody: Buffer.concat(chunks).toString('utf8') });
    response.writeHead(status, { 'Content-Type': 'application/json' });
    response.end(JSON.stringify({ message: status === 200 ? 'local-mock-ok' : 'local-mock-error' }));
  });
  await new Promise<void>(resolveListen => server.listen(0, '127.0.0.1', resolveListen));
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Mock server did not open a TCP address');
  try { return await run(`http://127.0.0.1:${address.port}`, captured); }
  finally { await new Promise<void>((resolveClose, reject) => server.close(error => error ? reject(error) : resolveClose())); }
}

async function execute(source: string, language: 'python' | 'typescript', baseOverride?: string) {
  const directory = await mkdtemp(join(tmpdir(), 'mandapi-renderer-'));
  const filename = join(directory, language === 'python' ? 'example.py' : 'example.mjs');
  try {
    await writeFile(filename, source, 'utf8');
    const env: NodeJS.ProcessEnv = { ...process.env, MANDAPI_API_KEY: 'local-mock-key' };
    delete env.MANDAPI_BASE_URL;
    if (baseOverride !== undefined) env.MANDAPI_BASE_URL = baseOverride;
    const command = language === 'python' ? (process.platform === 'win32' ? 'python' : 'python3') : process.execPath;
    return await new Promise<{ code: number | null; stdout: string; stderr: string }>((resolveChild, reject) => {
      const child = spawn(command, [filename], { env, windowsHide: true, timeout: 15000 });
      let stdout = '';
      let stderr = '';
      child.stdout.on('data', chunk => { stdout += String(chunk); });
      child.stderr.on('data', chunk => { stderr += String(chunk); });
      child.on('error', reject);
      child.on('close', code => resolveChild({ code, stdout, stderr }));
    });
  } finally {
    const absolute = resolve(directory);
    if (!absolute.startsWith(resolve(tmpdir()) + sep) || !basename(absolute).startsWith('mandapi-renderer-')) throw new Error('Unsafe temporary cleanup path');
    await rm(absolute, { recursive: true, force: true });
  }
}

const pythonCommand = process.platform === 'win32' ? 'python' : 'python3';
const hasPython = spawnSync(pythonCommand, ['--version'], { windowsHide: true }).status === 0;
for (const language of ['typescript', 'python'] as const) {
  describe.skipIf(language === 'python' && !hasPython)(`${language} generated request execution`, () => {
    it.each(protocols)('%s sends exactly the public request contract to a local mock', async protocol => {
      await withMock(200, async (baseUrl, captured) => {
        const input = options(protocol, 'https://unused.example');
        const request = buildRequest(input);
        const result = await execute(generateCode({ ...input, language }), language, baseUrl + '/proxy///');
        expect(result.code, result.stderr).toBe(0);
        expect(result.stdout).toContain('local-mock-ok');
        expect(captured).toHaveLength(1);
        expect(captured[0]!.url).toBe('/proxy' + request.path);
        expect(captured[0]!.method).toBe(request.method);
        expect(captured[0]!.headers[request.auth.header.toLowerCase()]).toBe(request.auth.prefix + 'local-mock-key');
        for (const [name, value] of Object.entries(request.headers)) {
          if (name.toLowerCase() !== request.auth.header.toLowerCase()) expect(captured[0]!.headers[name.toLowerCase()]).toBe(value);
        }
        expect(captured[0]!.rawBody).toBe(JSON.stringify(buildBody(input)));
      });
    }, 20000);

    it.each(protocols)('%s normalizes SDK /v1 runtime bases without duplicate paths', async protocol => {
      await withMock(200, async (baseUrl, captured) => {
        const input = options(protocol, 'https://unused.example');
        const request = buildRequest(input);
        const result = await execute(generateCode({ ...input, language }), language, baseUrl + '/prefix/v1///');
        expect(result.code, result.stderr).toBe(0);
        expect(captured).toHaveLength(1);
        expect(captured[0]!.url).toBe('/prefix' + request.path);
        expect(captured[0]!.rawBody).toBe(JSON.stringify(buildBody(input)));
      });
    }, 20000);

    it('uses the injected URL when no runtime base override exists', async () => {
      await withMock(200, async (baseUrl, captured) => {
        const input = options('chat', baseUrl);
        const result = await execute(generateCode({ ...input, language }), language);
        expect(result.code, result.stderr).toBe(0);
        expect(captured[0]!.url).toBe(buildRequest(input).path);
      });
    }, 20000);

    it('reports HTTP failures instead of printing a successful result', async () => {
      await withMock(400, async baseUrl => {
        const input = options('chat', baseUrl);
        const result = await execute(generateCode({ ...input, language }), language);
        expect(result.code).not.toBe(0);
        expect(result.stderr).toContain('HTTP 400');
        expect(result.stderr).toContain('local-mock-error');
      });
    }, 20000);
  });
}
