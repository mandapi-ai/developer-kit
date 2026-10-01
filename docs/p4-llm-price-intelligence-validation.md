# P4 live validation — 2026-10-01

Tested from an independent checkout based on `b55c25abcdef31f3d82b49cfb1054de65ffca004` using Python 3.13 on Windows. The P3 checkout was preserved. Codegen, Catalog, pnpm configuration and JavaScript dependencies were not changed.

## Checks

- Editable install `pip install -e ".[dev]"`: passed.
- Offline `pytest -q`: **69 passed, 0 failed**.
- Skill frontmatter validator: passed.
- Wheel built and packaged default registry loaded: 20 sources.
- Real Brazil crawl: **910 records**, **788 platform/model pairs**, 15 sources attempted; CSV validation passed.
- Real global crawl: **1,368 records**, 20 sources attempted; CSV validation passed.
- Diff command produced Markdown; missing values remain missing. Adjacent source-failure evidence prevents removal claims for unavailable providers.
- Fetch evidence retains HTTP status, timestamp, response SHA-256, adapter, parser status and row count. HTTP 403 is preserved without bypass.
- Global fetch window (UTC): `2026-10-01T14:21:57.510566+00:00` through `2026-10-01T14:22:49.727450+00:00`.
- Output, evidence files, raw third-party pages and virtual environments remain local ignored artifacts. No Hugging Face publication or scheduled automation was performed.

## Brazil coverage

Model count means unique published seller IDs with numeric token prices. Price records additionally separate protocol and context tiers; catalog totals and non-token models are not equivalent to this count.

| Source | HTTP | Parser | Models with prices | Price records |
| --- | --- | --- | --- | --- |
| mandapi | 200 | parsed | 44 | 44 |
| roteia | 200 | parsed | 50 | 54 |
| tokenrecarga | 200 | parsed | 2 | 2 |
| kunavo | 200 | parsed | 16 | 16 |
| apimart | 200 | parsed | 211 | 224 |
| runapi | 200 | parsed | 70 | 123 |
| unorouter | 403 | not_attempted | 0 | 0 |
| ominigate | 200 | parsed | 395 | 447 |
| tokia | 200 | profile_only | 0 | 0 |
| navi-router | 200 | profile_only | 0 | 0 |
| certisecure | 200 | profile_only | 0 | 0 |
| pixia-cloud | 200 | profile_only | 0 | 0 |
| apitopus | 200 | profile_only | 0 | 0 |
| nexforce | 200 | profile_only | 0 | 0 |
| swen-ai | 200 | profile_only | 0 | 0 |

## Global coverage

| Source | HTTP | Parser | Models with prices | Price records |
| --- | --- | --- | --- | --- |
| mandapi | 200 | parsed | 44 | 44 |
| roteia | 200 | parsed | 50 | 54 |
| tokenrecarga | 200 | parsed | 2 | 2 |
| openrouter | 200 | parsed | 456 | 456 |
| openai | 200 | parse_error | 0 | 0 |
| anthropic | 200 | parsed | 2 | 2 |
| google-ai-studio | 200 | no_supported_prices | 0 | 0 |
| deepseek | 200 | no_supported_prices | 0 | 0 |
| kunavo | 200 | parsed | 16 | 16 |
| apimart | 200 | parsed | 211 | 224 |
| runapi | 200 | parsed | 70 | 123 |
| unorouter | 403 | not_attempted | 0 | 0 |
| ominigate | 200 | parsed | 395 | 447 |
| tokia | 200 | profile_only | 0 | 0 |
| navi-router | 200 | profile_only | 0 | 0 |
| certisecure | 200 | profile_only | 0 | 0 |
| pixia-cloud | 200 | profile_only | 0 | 0 |
| apitopus | 200 | profile_only | 0 | 0 |
| nexforce | 200 | profile_only | 0 | 0 |
| swen-ai | 200 | profile_only | 0 | 0 |

## Pricing meaning and remaining limitations

- APIMart: 211 IDs / 224 records from the public all-model pricing API. `listed_base` contains explicit base token rates; effective/group/member discounts are excluded rather than silently applied.
- OminiGate: 395 text-output IDs / 447 records from its public catalog API. `catalog_list` contains per-million USD rates, including declared context tiers; route discounts and non-token charges are excluded.
- Roteia: public marketing catalog is capped at 50 models. Four long-context tiers yield 54 rows; this is not a claim that its entire dashboard catalog has only 50 models. Embedded HTML data remains `needs_review`.
- RunAPI: 70 IDs / 123 explicit protocol/context records; range headings are replaced by declared tier detail, never reduced to the first price. HTML data remains `needs_review`.
- Kunavo: 16 text IDs. Main and cache tables are joined without counting the same model twice. Image/video/audio units are excluded from token schema.
- TokenRecarga: only 2 numeric public cards; the page states 124 additional models require a proposal. Account-contract prices may differ and the published numeric prices exclude taxes.
- UnoRouter returned HTTP 403 and was not bypassed. Profile-only competitors return zero price records deliberately.
- OpenAI generic parser rejects ambiguous duplicate/context offers. Google and DeepSeek public layouts are not supported by the initial generic parser; Anthropic generic extraction is partial. These empty/partial results are adapter coverage, not absence of public prices.
- `public_source` means deterministically extracted from a public API, not an independently audited or guaranteed future billing rate. All original BRL/USD values are retained; CNY parsing is covered offline and no FX conversion is performed.

## Reproduction

From `skills/llm-price-intelligence`, use Python 3.11+ and a new dated directory:

```sh
pip install -e ".[dev]"
pytest -q
mandapi-price-intel crawl --market brazil --out dist/YYYY-MM-DD-HHMM-brazil
mandapi-price-intel validate --input dist/YYYY-MM-DD-HHMM-brazil/prices.csv
mandapi-price-intel crawl --market global --out dist/YYYY-MM-DD-HHMM-global
```

Source registry URLs and adapter semantics are retained in `sources.yaml` and the source code. Full page copies were used only for local debugging and were not committed.
