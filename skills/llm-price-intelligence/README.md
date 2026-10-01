# MandAPI LLM Price Intelligence

**Public LLM/API price collection, normalization, provenance and snapshot diffing.**

MandAPI LLM Price Intelligence is an open research and developer tool for collecting, normalizing and auditing public AI API prices across official providers, multi-model gateways and Brazil-focused resellers.

It is designed to support the **MandAPI LLM Pricing Observatory / AI API Prices in Brazil** dataset without turning one-off browser research into an opaque spreadsheet.

## What it does

- loads public pricing sources from `sources.yaml`;
- fetches public pages and APIs with evidence hashes;
- parses structured OpenRouter, APIMart and OminiGate public catalog pricing;
- extracts candidate prices from simple public HTML tables;
- keeps profile-only competitors in the provider registry without fabricating prices;
- preserves the original published currency;
- normalizes model IDs conservatively;
- exports the current V2 flat price schema;
- validates suspicious or incomplete records;
- compares two snapshots and writes a Markdown change report.

## Research integrity

A generic HTML parser is not treated as ground truth. Generic extraction is emitted with:

```text
verification_status = needs_review
```

Structured public adapters can emit:

```text
verification_status = public_source
```

This distinction is deliberate. A larger dataset is not useful if the provenance is weak.

## Install

Python 3.11+ is required.

```bash
cd skills/llm-price-intelligence
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -e .[dev]
pytest
```

## Crawl Brazil-focused sources

```bash
mandapi-price-intel crawl --market brazil --out ./dist/2026-10-01-2200-brazil
```

Outputs:

```text
dist/2026-10-01-2200-brazil/
├── prices.csv
├── providers.csv
├── evidence.jsonl
└── crawl-summary.md
```

By default, `prices.csv` includes candidates from enabled sources and preserves their verification status. A publication pipeline should filter or manually review `needs_review` rows before they enter a research release.

## Crawl the global registry

```bash
mandapi-price-intel crawl --market global --out ./dist/2026-10-01-2200-global
```

## Validate a CSV

```bash
mandapi-price-intel validate --input ./dist/2026-10-01-2200-brazil/prices.csv
```

## Diff snapshots

```bash
mandapi-price-intel diff \
  --old ./examples/sample-prices.csv \
  --new ./dist/2026-10-01-2200-brazil/prices.csv \
  --out ./dist/2026-10-01-2200-brazil/price-changes.md
```

The diff uses an adjacent new-snapshot `evidence.jsonl` when present: unavailable sources produce unobserved offers instead of removal claims. Absence from a CSV is not proof that a seller discontinued a model.

## Initial source registry

The registry includes public sources for MandAPI, Roteia, TokenRecarga, OpenRouter, OpenAI, Anthropic, Google AI Studio, DeepSeek, Kunavo, APIMart, RunAPI, UnoRouter and OminiGate, plus profile/market sources such as Tokia, NAVI Router, CertiSecure, PixIA Cloud, Apitopus, Nexforce and SWEN.AI.

Provider-specific adapters cover Roteia's embedded public catalog and context tiers, RunAPI's protocol-specific token table, Kunavo's text/cache tables, and TokenRecarga's numeric pricing cards. HTML and embedded-page data remain `needs_review`; the structured OpenRouter, APIMart and OminiGate public APIs are `public_source`. APIMart exports explicit base rates as `listed_base`, excluding effective/group/member discounts. OminiGate exports `catalog_list` rates, excluding route discounts. TokenRecarga rows retain its tax-excluded caveat. Non-token charges are not mapped into token fields.

A source returning HTTP 200 with zero supported rows is **not evidence that it has no public prices**. Check `parser_status` in `evidence.jsonl`; `no_supported_prices` means the adapter found none. The summary counts unique seller model IDs separately from price records (context/protocol variants). Profile sources emit no price records. Brazil mode includes Brazil/localized-market sources; use global mode for OpenRouter and official global references.

Use a fresh dated output directory each time: existing snapshots are refused. Output, local page copies, virtual environments and caches are ignored by Git. This release does not upload to Hugging Face or schedule recurring crawls.

## Data model

The first release exports a flat schema compatible with the public V2 dataset:

```text
record_id
model_id
canonical_model_id
model_name
model_family
model_provider
platform
platform_type
source_type
currency
input_per_1m
output_per_1m
cache_read_per_1m
cache_write_per_1m
context_tier
context_limit_tokens
pricing_variant
price_scope
market_scope
brazil_relevance
openai_compatible
verification_status
last_checked
source_url
notes
```

The crawler preserves original currencies. Cross-currency normalization should be produced as a derived research layer, not written back over source prices.

## Adding a source

Add a source to `sources.yaml`.

Example:

```yaml
- id: example-gateway
  platform: Example Gateway
  enabled: true
  adapter: generic_html
  pricing_url: https://example.com/pricing
  platform_type: gateway
  source_type: competitor_public
  default_currency: BRL
  market_scope: Brazil
  brazil_relevance: direct_brl
  openai_compatible: true
  unit: per_1m_tokens
```

If the public page is dynamic or semantically complex, add a dedicated adapter under `src/mandapi_price_intelligence/adapters/`.

## Português (Brasil)

O **MandAPI LLM Price Intelligence** é uma ferramenta aberta para coletar, normalizar e auditar preços públicos de APIs de IA, incluindo provedores oficiais, gateways multimodelo e plataformas voltadas ao mercado brasileiro.

A ferramenta preserva a moeda original, a URL da fonte, a data da coleta e um hash da evidência. Extrações genéricas de HTML ficam como `needs_review` até revisão, em vez de serem publicadas como fatos automaticamente.

Casos de uso:

- comparar preços públicos de GPT, Claude, Gemini, DeepSeek e outros modelos;
- acompanhar gateways compatíveis com OpenAI;
- mapear preços em BRL e concorrentes no Brasil;
- detectar aumentos, reduções e novos modelos;
- preparar snapshots reproduzíveis para o dataset público da MandAPI.

A coleta brasileira não inclui automaticamente as referências globais, como OpenRouter. Use `--market global` para coletá-las. Um resultado vazio indica que o parser não encontrou preços compatíveis; não comprova a ausência de preços públicos. Use uma pasta com data e horário a cada coleta.

## Links

- MandAPI pricing: https://mandapi.com/pricing
- Public dataset: https://huggingface.co/datasets/fanpuch/ai-api-prices-brazil
- Postman: https://www.postman.com/fanpuchi-9985689/mandapi

## License

MIT, following the repository root license. Third-party pricing pages remain subject to their respective owners' terms.
