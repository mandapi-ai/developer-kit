[English](README.md) | **Português (Brasil)**

# MandAPI

**Uma API para vários modelos de IA, com preços em reais, recarga via Pix e opções de baixo custo.**

GPT · Claude · Gemini · DeepSeek · Kimi · GLM · MiMo

Um gateway multimodelo para aplicações, agentes e automações, com modelos de ponta, alternativas econômicas e ferramentas abertas para integração.

[Site](https://mandapi.com/) · [Documentação](https://mandapi.com/docs) · [Modelos](https://mandapi.com/#/models) · [Preços](https://mandapi.com/pricing)

**Ferramentas para desenvolvedores:** [Gerador de código](packages/codegen/) · [Catálogo de modelos](packages/catalog/) · SDK (planejado) · Agent Skills (planejado).

## APIs de IA sem complicação

A MandAPI reúne o acesso a vários provedores em **um gateway, uma chave de API e várias famílias de modelos**.

O catálogo inclui GPT, Claude, Gemini, DeepSeek, Kimi, GLM e MiMo. Endpoints compatíveis com OpenAI oferecem um ponto de partida conhecido. Protocolos nativos dependem do suporte declarado para cada modelo e gateway.

Este repositório oferece geração de código e um contrato de catálogo para consultar metadados e selecionar protocolos a partir de dados.

## Feita com o Brasil em mente 🇧🇷

A MandAPI busca tornar APIs de IA mais acessíveis para desenvolvedores brasileiros, com:

- **Preços em reais (BRL)**, com entrada e saída apresentadas separadamente.
- **Recarga via Pix**, para adicionar créditos de uso da API.
- **Produto, documentação e guias em português**.
- **Integração compatível com OpenAI**, conforme o contrato documentado.
- **Um saldo MandAPI para acessar diferentes modelos do gateway**.
- **Alternativas de baixo custo** para cargas que dispensam modelos premium.

O [guia de APIs de IA no Brasil](https://docs.mandapi.com/api-de-ia-brasil/) explica cadastro, créditos e primeira chamada. Confirme o ID e a disponibilidade antes de integrar.

## API de IA barata no Brasil

Ao escolher uma **API de IA barata no Brasil**, compare entrada e saída, publicadas separadamente em **BRL por 1 milhão de tokens**. O total depende do consumo em cada categoria.

Classificação e agentes de programação têm necessidades diferentes. Avalie preço, protocolo, contexto e capacidades confirmadas para escolher entre opções econômicas e modelos de ponta.

Os preços são dinâmicos. Consulte os [preços atuais](https://mandapi.com/pricing) e a página sobre [API de IA barata no Brasil](https://mandapi.com/api-de-ia-barata-brasil/) para comparar as opções disponíveis.

## Ferramentas para desenvolvedores

O Developer Kit está sendo entregue em etapas:

| Ferramenta | Estado atual |
| --- | --- |
| [`@mandapi/codegen`](packages/codegen/README.md) | Implementado e disponível pelo código deste repositório; ainda não publicado no npm |
| [`@mandapi/catalog`](packages/catalog/README.md) | Implementado e disponível pelo código deste repositório; ainda não publicado no npm |
| `@mandapi/model-schema` | Planejado para P3 |
| `@mandapi/ai-sdk-provider` | Planejado para P3 |
| Agent Skills | Planejado para P4 |

### Gerador de código

O Codegen gera exemplos para **Chat Completions, Responses, Anthropic Messages e Gemini Native**, em **Python, TypeScript, cURL, Go, Java, C# e Ruby**. A URL base é injetável, assim como configurações de rota e autenticação.

`buildBody()` é a fonte única do JSON. `buildRequest()` reúne corpo, rota e headers para todos os renderizadores. P2 atende a requisições sem streaming.

### Catálogo de modelos

O Catalog contém **9 modelos reais**, em um snapshot estático de dados públicos de 2026-10-01. Campos desconhecidos são omitidos; os demais têm sua origem registrada. Não há consulta à produção em tempo real.

O protocolo vem das declarações do catálogo, sem inferência pelo nome. O fixture `gpt-6-sol` declara somente Chat. Messages e Gemini Native são preferências explícitas para modelos com suporte declarado; essas escolhas não representam testes reais de disponibilidade.

## Comece pelo código

Use **Node.js 22.12+ na linha 22 LTS ou Node.js 24 LTS**, **pnpm 11.24.0** e Git:

```sh
git clone https://github.com/mandapi-ai/developer-kit.git
cd developer-kit
pnpm install --frozen-lockfile
pnpm build
```

Defina `MANDAPI_BASE_URL` localmente; a raiz documentada é `https://api.mandapi.com`. Salve o exemplo como `generate-example.mjs` na raiz do repositório:

```js
import { writeFileSync } from 'node:fs';
import { generateForModel } from './packages/codegen/dist/index.js';
import { catalog } from './packages/catalog/dist/index.js';

const baseUrl = process.env.MANDAPI_BASE_URL;
if (!baseUrl) throw new Error('Defina MANDAPI_BASE_URL');

writeFileSync('mandapi-example.py', generateForModel({
  catalog,
  model: 'gpt-6-sol',
  language: 'python',
  baseUrl,
  prompt: 'Reply with OK only.',
  headers: { 'User-Agent': 'MandAPI-Developer-Kit/0.1.0' },
}), 'utf8');
```

```sh
node generate-example.mjs
```

Para executar o Python gerado, defina também `MANDAPI_API_KEY` no ambiente local e rode:

```sh
python mandapi-example.py
```

Gerar código não envia requisições. Executar o Python chama a API e consome créditos. A chave vem do ambiente; mantenha-a fora dos arquivos e do Git.

## Para apps, agentes e automação

| Uso | Como começar |
| --- | --- |
| Aplicações e assistentes | Gere uma primeira chamada e integre o protocolo documentado |
| Agentes de programação | Consulte o catálogo antes de escolher modelo e protocolo |
| Automação | Compare custos para a sua carga e valide o resultado esperado |
| Prototipagem | Experimente modelos declarados sem refazer a configuração do gateway |

## Status do projeto

P2 concluído. O gateway está em operação; os pacotes atuais são:

```text
packages/
├── codegen/
└── catalog/
```

A [validação P2](docs/p2-validation.md) registra testes locais, builds e execução real de Python em **2026-10-01** para `gpt-6-sol` via Chat: HTTP 200 com conteúdo do assistente. Somente esse par modelo/protocolo foi marcado como testado ao vivo; os demais permanecem sem essa marcação. 86 testes, typechecks e builds passaram. A rota Gemini Native é configurável e ainda não foi testada ao vivo.

## Links rápidos

[Site](https://mandapi.com/) · [Documentação](https://mandapi.com/docs) · [Guias em português](https://docs.mandapi.com/) · [Modelos](https://mandapi.com/#/models) · [Preços em reais](https://mandapi.com/pricing) · [GitHub](https://github.com/mandapi-ai)

## Sobre a MandAPI AI

A MandAPI AI desenvolve infraestrutura e ferramentas para aplicações com múltiplos modelos. O foco inicial no Brasil reúne acesso a modelos, preços em reais e integrações reutilizáveis. As ferramentas abertas recebem contribuições da comunidade.

## Licença

MIT. Consulte [LICENSE](LICENSE). Referências de terceiros e requisitos de atribuição estão em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
