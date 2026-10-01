---
name: llm-price-intelligence
description: Collect and audit public LLM/API prices, map Brazil-focused gateways, preserve price provenance, and compare dated snapshots for MandAPI Research. Use for public pricing research and price-change reports.
---

# MandAPI LLM Price Intelligence

Use this Skill when the task involves public LLM/API pricing, competitor price research, Brazil/BRL AI API market mapping, price-change detection, OpenRouter alternatives, or updating the MandAPI LLM Pricing Observatory.

## Triggers

Examples:

- "Update today's Brazil AI API prices."
- "Compare MandAPI with public competitor prices."
- "Find new Brazilian LLM API gateways."
- "Check whether GPT / Claude / Gemini prices changed."
- "Build a public source-linked price table."
- "Update the AI API Prices in Brazil dataset."

## Run the tool

From this Skill directory, install with Python 3.11+ using `pip install -e ".[dev]"`. See [README.md](README.md) for commands and schema. Run `mandapi-price-intel crawl --market brazil --out dist/YYYY-MM-DD-HHMM-brazil`, then validate the CSV. Choose a new output path for every run.

## Workflow

1. Read `sources.yaml`.
2. Select enabled sources for the requested market.
3. Fetch public pages/APIs with a descriptive User-Agent and reasonable timeout.
4. Preserve source URL, fetch time, status code and content SHA-256.
5. Use a deterministic adapter when available.
6. Treat generic HTML extraction as `needs_review`.
7. Preserve original published currency.
8. Keep seller model ID and conservative canonical model ID separately.
9. Validate records before comparing or publishing them.
10. Append or create a dated snapshot; never destroy prior history.
11. Generate a Markdown change report when an older snapshot exists.
12. Never invent a numeric price for quote-only products.

## Data integrity rules

- Missing is not zero.
- Promotion is not permanent standard pricing.
- Peak/off-peak is not context tier.
- Seller is not automatically the model creator.
- BRL conversion is derived data unless the seller itself publishes BRL.
- The public source URL belongs on every price observation.
- Unknown model aliases stay unknown rather than being guessed.

## Output

Primary export: `prices.csv`, compatible with the MandAPI LLM Pricing Observatory V2 flat schema.

Supporting exports:

- `providers.csv`
- `evidence.jsonl`
- `crawl-summary.md`
- optional `price-changes.md`

## Brand / research context

This Skill is maintained as part of **MandAPI Research / MandAPI Developer Kit**. It supports open work on LLM pricing, inference economics, gateway markets and AI API prices in Brazil.

Public research dataset:

https://huggingface.co/datasets/fanpuch/ai-api-prices-brazil

MandAPI pricing:

https://mandapi.com/pricing

Postman workspace:

https://www.postman.com/fanpuchi-9985689/mandapi

## Prohibited behavior

Do not:

- bypass authentication or anti-bot controls;
- scrape private account pages;
- expose API keys, cookies or browser credentials;
- infer hidden wholesale costs and publish them as facts;
- mark generic parser output verified without review;
- claim a competitor has a numeric public price when it only says "contact sales" / "sob consulta".
