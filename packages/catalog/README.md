# @mandapi/catalog

A canonical, data driven model contract and an immutable static catalog. This package has no runtime dependencies and makes no network requests.

## Usage

```ts
import {
  catalog,
  findModels,
  getModel,
  resolvePreferredProtocol,
} from '@mandapi/catalog';

catalog.get('gpt-6-sol'); // alias for getModel
getModel('not-in-this-snapshot'); // undefined
resolvePreferredProtocol('claude-opus-5'); // 'messages'
resolvePreferredProtocol('gemini-3.1-pro-preview'); // 'gemini'
findModels({ capability: 'tools', protocol: 'messages' });
```

`listModels()` returns all models in the snapshot. `findModels()` combines its filters with AND; a capability must be explicitly `true`, so a missing field never counts as supported. Lookups use exact IDs, with no prefix or family heuristics.

## Custom catalogs

```ts
import { createCatalog } from '@mandapi/catalog';

const custom = createCatalog([{
  id: 'any-name-you-control',
  name: 'Custom model',
  protocols: [
    { id: 'chat' },
    { id: 'responses', preferred: true, tested: false },
  ],
  capabilities: {},
}]);

custom.resolvePreferredProtocol('any-name-you-control'); // 'responses'
```

A single `preferred: true` declaration wins. If none is marked, the first declared protocol is used as the documented data-order fallback. Unknown IDs and empty protocol lists resolve to `undefined`. Duplicate model IDs, duplicate protocol declarations, unsupported protocol IDs, and multiple preferred protocols are rejected.

`preferredProtocol` on returned models is derived from `protocols`, never a second routing input. An existing model can be passed to `createCatalog`; its derived field is recomputed. Models, their nested metadata, the catalog object, and returned collections are frozen. The catalog copies input metadata, so later changes to caller data cannot change its routing.

## Included snapshot and evidence

Nine representative models were captured from public MandAPI metadata on **2026-10-01**:

- [Public model prices](https://mandapi.com/api/prices), also available as [catalog.json](https://mandapi.com/catalog.json): exact IDs, display names, context values, operational status, and normalized BRL prices per million tokens.
- [Public endpoint support table](https://api.mandapi.com/api/pricing): exact `supported_endpoint_types`, provider IDs, and capability tags.
- The selected original fields and source response timestamps are preserved in [fixtures/source-snapshot.json](fixtures/source-snapshot.json). `fixtureSources` exposes the URLs, snapshot date, metadata version, and source generation time.

Mapping is explicit: `openai` maps to `chat`, `anthropic` to `messages`, and `gemini` to `gemini`. Reasoning, Tools, Vision, and Audio tags map to the matching boolean capability fields. Other capabilities, missing context values, maximum output, and runtime measurements are omitted. NewAPI pricing ratios are not converted into prices; this catalog uses the already normalized public BRL values.

Native Messages and Gemini are the maintained preferred choices when the source declares those protocols. This preference is a library policy. The public source does not publish a preferred flag or live test results. Independently, only `gpt-6-sol` / `chat` is marked `tested: true`, following a successful generated Python request on 2026-10-01; see the [Acceptance A record](../../docs/p2-validation.md#acceptance-status). Other fixture protocols remain untested. Source generation time is metadata provenance, not a measured runtime observation. `runtime.status` records the published status only.

The snapshot declares only `chat` for `gpt-6-sol`; its other capabilities are unknown. It does not add Responses support based on the model name. The Gemini Native representative is `gemini-3.1-pro-preview`, whose source declares both Gemini and Chat. `gemini-3.8-flash` is not substituted based on naming.

The public source lists the generic Gemini path `/v1beta/models/{model}:generateContent`. The P2 Codegen contract uses `/gemini/v1beta/models/{model}:generateContent`. Protocol metadata in this package does not verify deployment of either path. Production route and authentication verification remain separate from this static catalog.

Prices and availability can change. This package is a dated fixture, not a live production catalog API. Refresh the snapshot and validate the intended gateway before relying on it for production traffic or cost estimates.

## Development

From the repository root:

```sh
pnpm test packages/catalog/tests
pnpm --filter @mandapi/catalog typecheck
pnpm --filter @mandapi/catalog build
```
