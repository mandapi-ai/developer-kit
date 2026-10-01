# P2 validation

## Scope

Two independent ESM libraries: `@mandapi/codegen` and `@mandapi/catalog`. Root README, LICENSE, THIRD_PARTY_NOTICES, Organization branding, and production systems are unchanged. No upstream implementation was copied or adapted. Codegen is non-streaming.

## Reproduce

```sh
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm build
```

The tests execute generated Python and TypeScript against a temporary local test receiver. They compare the emitted request path, headers, and JSON against `buildRequest()` for every protocol, and check failures and environment overrides. All 28 protocol/language combinations retain the exact serialized body.

## Verified on 2026-10-01

- 86 tests passed across 4 test files.
- Both library typechecks and builds passed.
- Each package was packed and installed offline in a separate temporary project; ESM imports and Catalog-to-Codegen integration succeeded.
- Python and TypeScript generated requests were executed; other languages were verified structurally for complete serialized requests.

## Acceptance status

- B: `claude-opus-5` resolves to Messages from Catalog declarations.
- C: `gemini-3.1-pro-preview` resolves to Gemini Native and generates the specified route; the direct production-advertised `/v1beta/...` can be explicitly injected.
- D: `pnpm test`, TypeScript checks, and both package builds pass.
- A: authenticated Python-to-MandAPI Chat execution is pending a locally configured test credential. Local test-receiver execution proves the generated Python request is executable but is not recorded as a live MandAPI response.

No fixture has `tested: true`. Do not change that until a successful authenticated test against the intended deployment is recorded with its date and route. The public source only declares Chat for `gpt-6-sol`; Responses is not invented for this fixture.

## Run acceptance A

Set `MANDAPI_BASE_URL` and `MANDAPI_API_KEY` locally; do not add credentials to the repository. The public quickstart advertises gateway root `https://api.mandapi.com`. Generate a minimal Python example using the built library:

```sh
node --input-type=module -e 'import { generateCode } from "./packages/codegen/dist/index.js"; console.log(generateCode({model:"gpt-6-sol",protocol:"chat",language:"python",baseUrl:process.env.MANDAPI_BASE_URL,prompt:"Reply with OK only."}));' > /tmp/mandapi-chat.py
python /tmp/mandapi-chat.py
```

On Windows, save the generated UTF-8 script in the system temporary directory instead of `/tmp`. The generated file contains only request configuration and an environment-variable name, not the credential. A live request incurs the gateway usage charge. Verify a successful content-bearing response before marking A complete.

## Public evidence

- [Gateway quickstart](https://mandapi.com/docs/quickstart)
- [Gateway key guide](https://mandapi.com/docs/api-keys)
- [Claude Messages guide](https://docs.mandapi.com/claude-code/cc-w1-001/)
- [Normalized public model catalog](https://mandapi.com/api/prices)
- [Declared protocol support](https://api.mandapi.com/api/pricing)

Catalog source snapshots and observation date ship under `packages/catalog/fixtures/`. Pricing and endpoint declarations are metadata observations; they do not prove availability for any individual credential.
