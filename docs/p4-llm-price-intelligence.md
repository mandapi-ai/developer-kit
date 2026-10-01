# P4 — LLM Price Intelligence Skill

MandAPI's first Agent Skill is focused on public LLM/API pricing research.

It crawls configured public sources, keeps original currencies, normalizes conservative model identities, hashes source evidence, exports a V2-compatible price table and compares dated snapshots.

The design separates deterministic structured adapters from generic HTML extraction. Generic extraction is intentionally marked `needs_review` so parser guesses do not silently enter the public research dataset.

## Why this exists

The public MandAPI LLM Pricing Observatory / AI API Prices in Brazil dataset needs repeatable collection instead of one-off manual research. The Skill turns that workflow into reusable infrastructure while preserving source provenance.

## Safety boundary

The Skill only targets public pages and public APIs. It does not bypass authentication, bot protection or access controls, and it does not use customer requests or private transaction data.

## Status

Initial release includes:

- source registry;
- public HTTP fetcher;
- OpenRouter, APIMart and OminiGate structured public API adapters;
- Roteia, RunAPI, Kunavo and TokenRecarga provider-specific HTML/embedded-data adapters;
- generic HTML table candidate parser;
- profile-only source representation;
- model canonicalization helpers;
- V2-compatible CSV export;
- evidence hashes;
- validator;
- snapshot diff reports.

Adapters preserve pricing variants: APIMart base/list rates exclude membership and group discounts; OminiGate catalog rates exclude route discounts. RunAPI protocols and explicit context tiers are separate offers. Candidate HTML extractions remain `needs_review`.

The dated live validation and per-source coverage are recorded in [P4 validation](p4-llm-price-intelligence-validation.md). Zero supported rows indicates parser coverage, not proven absence of public pricing. Remaining dynamic/complex global official-provider parsers can be extended incrementally.
