import type { MandapiModelInput } from '../types.js';

/** Provenance for the shipped static snapshot, separate from measured runtime data. */
export const fixtureSources = Object.freeze({
  observedOn: '2026-10-01',
  prices: 'https://mandapi.com/api/prices',
  protocols: 'https://api.mandapi.com/api/pricing',
  generatedAt: '2026-10-01T05:07:35.316Z',
  version: 'prod-2026-09-12.1',
});

// Endpoint types are copied from the public protocol table, not inferred from IDs.
// Native Messages/Gemini preference is a maintained choice of this static catalog.
// No tested:true or unsupported Responses declaration is invented.
export const fixtureModels: readonly MandapiModelInput[] = [
  {
    "id": "gpt-6-sol",
    "name": "gpt-6-sol",
    "provider": "OpenAI",
    "protocols": [
      {
        "id": "chat",
        "preferred": true,
        "tested": true
      }
    ],
    "capabilities": {},
    "pricing": {
      "currency": "BRL",
      "input": 0.4,
      "output": 2,
      "unit": "per_million_tokens"
    },
    "runtime": {
      "status": "operational"
    }
  },
  {
    "id": "gpt-5.6-sol",
    "name": "GPT-5.6 Sol",
    "family": "gpt-general",
    "provider": "OpenAI",
    "protocols": [
      {
        "id": "chat",
        "preferred": true
      }
    ],
    "capabilities": {
      "reasoning": true,
      "tools": true,
      "vision": true
    },
    "limits": {
      "context": 400000
    },
    "pricing": {
      "currency": "BRL",
      "input": 1,
      "output": 6,
      "unit": "per_million_tokens"
    },
    "runtime": {
      "status": "operational"
    }
  },
  {
    "id": "claude-opus-5",
    "name": "Claude Opus 5",
    "family": "claude-opus",
    "provider": "Anthropic",
    "protocols": [
      {
        "id": "messages",
        "preferred": true
      },
      {
        "id": "chat"
      }
    ],
    "capabilities": {
      "reasoning": true,
      "tools": true,
      "vision": true
    },
    "limits": {
      "context": 400000
    },
    "pricing": {
      "currency": "BRL",
      "input": 2,
      "output": 10,
      "unit": "per_million_tokens"
    },
    "runtime": {
      "status": "operational"
    }
  },
  {
    "id": "claude-sonnet-5",
    "name": "Claude Sonnet 5",
    "family": "claude-sonnet",
    "provider": "Anthropic",
    "protocols": [
      {
        "id": "messages",
        "preferred": true
      },
      {
        "id": "chat"
      }
    ],
    "capabilities": {
      "reasoning": true,
      "tools": true,
      "vision": true
    },
    "limits": {
      "context": 1000000
    },
    "pricing": {
      "currency": "BRL",
      "input": 1.2,
      "output": 6,
      "unit": "per_million_tokens"
    },
    "runtime": {
      "status": "operational"
    }
  },
  {
    "id": "gemini-3.1-pro-preview",
    "name": "Gemini 3.1 Pro (Preview)",
    "family": "gemini-pro",
    "provider": "Google",
    "protocols": [
      {
        "id": "gemini",
        "preferred": true
      },
      {
        "id": "chat"
      }
    ],
    "capabilities": {
      "reasoning": true,
      "tools": true,
      "vision": true,
      "audio": true
    },
    "limits": {
      "context": 1000000
    },
    "pricing": {
      "currency": "BRL",
      "input": 5.5,
      "output": 32,
      "unit": "per_million_tokens"
    },
    "runtime": {
      "status": "operational"
    }
  },
  {
    "id": "deepseek-v4.1-flash",
    "name": "deepseek-v4.1-flash",
    "provider": "DeepSeek",
    "protocols": [
      {
        "id": "chat",
        "preferred": true
      }
    ],
    "capabilities": {},
    "pricing": {
      "currency": "BRL",
      "input": 0.39,
      "output": 0.99,
      "unit": "per_million_tokens"
    },
    "runtime": {
      "status": "operational"
    }
  },
  {
    "id": "glm-5.3",
    "name": "glm-5.3",
    "provider": "智谱",
    "protocols": [
      {
        "id": "chat",
        "preferred": true
      }
    ],
    "capabilities": {},
    "pricing": {
      "currency": "BRL",
      "input": 4.49,
      "output": 13.9,
      "unit": "per_million_tokens"
    },
    "runtime": {
      "status": "operational"
    }
  },
  {
    "id": "kimi-k3",
    "name": "kimi-k3",
    "provider": "Moonshot",
    "protocols": [
      {
        "id": "chat",
        "preferred": true
      }
    ],
    "capabilities": {},
    "pricing": {
      "currency": "BRL",
      "input": 8.49,
      "output": 42.9,
      "unit": "per_million_tokens"
    },
    "runtime": {
      "status": "operational"
    }
  },
  {
    "id": "mimo-v2.6-flash",
    "name": "mimo-v2.6-flash",
    "protocols": [
      {
        "id": "chat",
        "preferred": true
      }
    ],
    "capabilities": {},
    "pricing": {
      "currency": "BRL",
      "input": 0.39,
      "output": 0.79,
      "unit": "per_million_tokens"
    },
    "runtime": {
      "status": "operational"
    }
  }
];
