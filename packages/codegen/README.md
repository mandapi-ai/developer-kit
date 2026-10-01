# @mandapi/codegen

A pure code generation library for four protocols and seven languages. No API key, production URL, SDK, database, or server is bundled. Node.js 22.12+ is required to use the ESM package.

```ts
import { generateCode, buildRequest, generateForModel } from '@mandapi/codegen';
import { catalog } from '@mandapi/catalog';

const baseUrl = process.env.MANDAPI_BASE_URL;
if (!baseUrl) throw new Error('Set MANDAPI_BASE_URL to your gateway root');

const python = generateCode({
  model: 'gpt-6-sol', protocol: 'chat', language: 'python', baseUrl,
  prompt: 'Reply with a short greeting.',
});

const claude = generateForModel({ catalog, model: 'claude-opus-5', language: 'python', baseUrl });
const gemini = generateForModel({ catalog, model: 'gemini-3.1-pro-preview', language: 'typescript', baseUrl });
```

Run the generated code with `MANDAPI_API_KEY` set locally. Generated examples also accept `MANDAPI_BASE_URL` as a runtime override. Use a gateway root; an OpenAI SDK `/v1` suffix is normalized to avoid duplicate `/v1`. Other deployment path prefixes are retained.

| Protocol | Default route | Default auth |
| --- | --- | --- |
| `chat` | `/v1/chat/completions` | Bearer |
| `responses` | `/v1/responses` | Bearer |
| `messages` | `/v1/messages` | Bearer + `anthropic-version: 2023-06-01` |
| `gemini` | `/gemini/v1beta/models/{model}:generateContent` | Bearer |

Languages: `python`, `typescript`, `curl`, `go`, `java`, `csharp`, `ruby`. Python, Go, Java (11+), C# (.NET 6+), Ruby use standard HTTP libraries; TypeScript requires a runtime with Fetch. cURL examples use a POSIX shell.

## One request builder

`buildBody()` is the only body builder. `buildRequest()` combines its output with the route, static headers, and an environment-based auth descriptor. Every renderer serializes that request body exactly. A future playground can call `buildRequest()` directly and supply its own secure credential at execution time.

Use `prompt` or string `messages` with optional `system` and `maxTokens`. Use `parameters` for extra JSON fields that do not replace generated fields. Use `body` for a complete protocol-native JSON payload (including tools or multimodal content). Native unknown fields are preserved; a contradictory model, invalid required field, non-JSON value, or `stream: true` is rejected. P2 supports non-streaming requests.

```ts
const request = buildRequest({
  model: 'gpt-6-sol', protocol: 'chat', baseUrl,
  body: { messages: [{ role: 'user', content: 'Hello' }], temperature: 0.2 },
});
// request.body is also the exact JSON serialized by generateCode().
```

## Gateway differences

Routes and headers are configured centrally, never in renderers. Supply `endpointPath`, `auth` (`bearer`, `x-api-key`, `x-goog-api-key`), `headers`, or `apiKeyEnv` when your gateway differs.

The [public MandAPI endpoint table](https://api.mandapi.com/api/pricing) currently declares `/v1beta/models/{model}:generateContent` for Gemini. The P2 default retains the specified `/gemini/v1beta/...` contract; for the advertised direct native route, explicitly pass:

```ts
generateForModel({
  catalog, model: 'gemini-3.1-pro-preview', language: 'python', baseUrl,
  endpointPath: '/v1beta/models/{model}:generateContent',
});
```

The [MandAPI Claude guide](https://docs.mandapi.com/claude-code/cc-w1-001/) uses Bearer for Messages, unlike the upstream Anthropic API. The [API key guide](https://mandapi.com/docs/api-keys) describes gateway Bearer auth. No generated protocol is marked as live-tested without a successful authenticated test.

## Protocol selection

`generateForModel()` uses an explicit supported override, then Catalog preferred protocol, then caller-supplied `fallbackProtocol`. Unknown model IDs fail unless an explicit protocol/fallback is supplied. Known models reject protocols absent from their catalog entries. No model-name heuristic is applied.

The `gpt-6-sol` fixture currently declares only Chat, as reported by the public catalog. The Responses renderer is available through `generateCode()` for a caller-confirmed deployment/model; the fixture does not invent Responses support.

## Development

From the repository root: `pnpm install`, `pnpm test`, `pnpm typecheck`, `pnpm build`. Root P1 documentation and license are preserved. All implementation in this package is independently written; no AIHubMix source code is copied or adapted.
