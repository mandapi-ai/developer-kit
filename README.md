**English** | [Português (Brasil)](README.pt-BR.md)

# MandAPI

**One API for multiple AI models — built with Brazilian developers in mind.**

GPT · Claude · Gemini · DeepSeek · Kimi · GLM · MiMo

> A multi-model AI gateway and developer platform with OpenAI-compatible APIs, pricing in Brazilian reais, Pix payment options, and access to premium and lower-cost models.

[Website](https://mandapi.com/) · [Documentation](https://mandapi.com/docs) · [Models](https://mandapi.com/#/models) · [Pricing in BRL](https://mandapi.com/pricing)

**Developer tools:** [Code Generator](packages/codegen/) · [Model Catalog](packages/catalog/) · [LLM Price Intelligence Skill](skills/llm-price-intelligence/) · SDK (planned).

## AI APIs without the usual complexity

Working across AI providers involves different API formats, authentication conventions and billing accounts. MandAPI brings multiple model families behind **one gateway and one API key**, with familiar OpenAI-compatible integration paths.

Choose from GPT, Claude, Gemini, DeepSeek, Kimi, GLM and MiMo models according to your task. The tools in this repository help you look up model metadata, choose a declared protocol and generate integration examples.

Check the [current model list](https://mandapi.com/docs/models) for availability to your key before making a request. Model families can support different protocols and capabilities.

## Built with Brazil in mind 🇧🇷

MandAPI focuses on making AI APIs practical for developers in Brazil:

- **Pricing in BRL:** compare input and output token prices in Brazilian reais.
- **Pix payment options:** add API credits using a local payment method.
- **Portuguese documentation:** get started with guides written for Brazilian developers.
- **Lower-cost model alternatives:** explore options for automation, extraction, classification and high-volume workloads.
- **Prepaid API credits:** access multiple model families from the same MandAPI account.
- **OpenAI-compatible endpoints:** connect through familiar request formats and SDK configuration.

See the [Brazil and Pix guide](https://docs.mandapi.com/api-de-ia-brasil/) for the current payment flow and the [quickstart](https://mandapi.com/docs/quickstart) for your first request.

## Low-cost AI API options in Brazil

Choose a model around the work it needs to do. Compare input and output prices, supported protocols, known capabilities and context limits alongside the quality your application needs.

For smaller tasks, try an economical model and measure the result. For complex coding, reasoning or agent workflows, evaluate a more capable model using the same workload. Your request mix matters: input and output tokens are priced separately, and the cost depends on actual usage.

**[Compare current prices in BRL](https://mandapi.com/pricing) · [Explore lower-cost AI models](https://mandapi.com/api-de-ia-barata-brasil/)**

The website publishes current prices. This repository's Catalog contains a dated metadata snapshot for development; consult the live catalog before choosing a model or estimating a production workload.

## Developer tools

The Developer Kit is MandAPI's open developer-tooling layer. Two JavaScript packages and a Python Skill are available from this repository; **npm packages have not been published yet**.

| Component | Status | What it provides |
| --- | --- | --- |
| [Code Generator](packages/codegen/) — `@mandapi/codegen` | Available from source | Request examples for four protocols and seven languages |
| [Model Catalog](packages/catalog/) — `@mandapi/catalog` | Available from source | Structured model metadata, filters and preferred-protocol lookup |
| Model Schema + AI SDK Provider | Planned — P3 | Shared model contracts and `@mandapi/ai-sdk-provider` integration |
| [LLM Price Intelligence](skills/llm-price-intelligence/) | Available from source | Collects and audits public LLM/API pricing, maps Brazil-focused gateways, preserves source provenance, and compares dated price snapshots |
| Other Agent Skills | Planned | Model discovery and integration support for coding assistants |

### Code Generator

Generate non-streaming examples for **Chat Completions, Responses API, Anthropic Messages and Gemini Native**, in **Python, TypeScript/JavaScript, cURL, Go, Java, C# and Ruby**.

Supply your gateway Base URL and request options. The shared `buildBody()` and `buildRequest()` functions keep generated code and future request clients on the same request contract. Routes and headers are configurable; see the [package guide](packages/codegen/README.md).

### Model Catalog

Look up models with `getModel()`, list or filter them with `listModels()` and `findModels()`, and resolve their declared preferred protocol with `resolvePreferredProtocol()`.

The initial Catalog contains nine representative models captured from public MandAPI metadata. It records protocols and confirmed capabilities, limits and pricing where known. Unknown fields are omitted. Protocol selection uses the explicit declarations in Catalog data.

The [Catalog guide](packages/catalog/README.md) documents the snapshot, its sources and how to create your own catalog.

## Start from the source

Use Node.js 22 (22.12+) or 24 LTS, and pnpm 11.24.0:

```sh
git clone https://github.com/mandapi-ai/developer-kit.git
cd developer-kit
pnpm install --frozen-lockfile
pnpm build
```

Set `MANDAPI_BASE_URL` locally to your gateway root, such as `https://api.mandapi.com`. Save this as `generate-example.mjs` in the repository root:

```js
import { writeFileSync } from 'node:fs';
import { generateForModel } from './packages/codegen/dist/index.js';
import { catalog } from './packages/catalog/dist/index.js';

const baseUrl = process.env.MANDAPI_BASE_URL;
if (!baseUrl) throw new Error('Set MANDAPI_BASE_URL');

writeFileSync('mandapi-example.py', generateForModel({
  catalog,
  model: 'gpt-6-sol',
  language: 'python',
  baseUrl,
  prompt: 'Reply with OK only.',
  headers: { 'User-Agent': 'MandAPI-Developer-Kit/0.1.0' },
}), 'utf8');
```

Generate the Python example:

```sh
node generate-example.mjs
```

To send the request, set `MANDAPI_API_KEY` in your local environment and run:

```sh
python mandapi-example.py
```

Code generation itself makes no API request. Running the generated Python uses your gateway and incurs its normal usage charge. Keep credentials outside source files and Git; confirm model availability for your key before running.

## For apps, agents and automation

| Workload | How MandAPI fits |
| --- | --- |
| AI applications | Integrate chat, assistants, extraction and generation through a shared gateway |
| Coding agents | Evaluate different models using their declared protocols |
| Automation | Compare economical options for repetitive or high-volume tasks |
| Model evaluation | Use a common prompt to assess response quality, latency and usage cost |
| Prototyping | Start with familiar API formats and explore different model families |

## Project status

P2 is complete and the first Python Agent Skill is available from source. The current structure is:

```text
packages/
├── codegen/
└── catalog/

skills/
└── llm-price-intelligence/
```

Generated Python for `gpt-6-sol` using Chat was live-tested on **2026-10-01** against `https://api.mandapi.com/v1/chat/completions`: HTTP 200 with assistant content. Only this Catalog model/protocol is marked `tested: true`; other combinations are not recorded as live-tested. Gemini's native route remains configurable.

See [P2 validation](docs/p2-validation.md) for the request configuration and verification record. The 86 tests, typechecks and builds passed. Model Schema, AI SDK Provider and other Agent Skills remain on the roadmap.

## Quick links

- [LLM Price Intelligence Skill](skills/llm-price-intelligence/README.md)
- [Kaggle Dataset](https://www.kaggle.com/datasets/mandapi/llm-api-pricing-dataset-2026)
- [Make your first API request](https://mandapi.com/docs/quickstart)
- [Create and protect an API key](https://mandapi.com/docs/api-keys)
- [Browse models](https://mandapi.com/#/models)
- [Compare prices in BRL](https://mandapi.com/pricing)
- [Read the Code Generator guide](packages/codegen/README.md)
- [Read the Model Catalog guide](packages/catalog/README.md)

## About MandAPI AI

MandAPI AI builds developer infrastructure for applications using multiple AI models, with an initial focus on accessibility and practical costs for developers in Brazil.

Our goal is to bring **model access, cost comparison, model metadata and reusable developer tools** into one ecosystem. These tools are open source so developers can inspect integrations, reuse examples and contribute improvements.

## License

MIT. See [LICENSE](LICENSE). Third-party reference projects and attribution requirements are documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
