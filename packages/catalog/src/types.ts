/** The only supported protocol identifiers in the canonical Catalog contract. */
export type ProtocolId = 'chat' | 'responses' | 'messages' | 'gemini';

export interface ProtocolSupport {
  readonly id: ProtocolId;
  /** Catalog maintenance policy; not a claim that the route was tested. */
  readonly preferred?: boolean;
  /** Set true only after a recorded live test against the intended gateway. */
  readonly tested?: boolean;
}

export interface ModelCapabilities {
  readonly text?: boolean;
  readonly vision?: boolean;
  readonly tools?: boolean;
  readonly structuredOutput?: boolean;
  readonly reasoning?: boolean;
  readonly embedding?: boolean;
  readonly imageGeneration?: boolean;
  readonly audio?: boolean;
  readonly video?: boolean;
}

export type ModelCapability = keyof ModelCapabilities;

export interface MandapiModel {
  readonly id: string;
  readonly name: string;
  readonly family?: string;
  readonly provider?: string;
  readonly protocols: readonly ProtocolSupport[];
  /** Derived from protocols by createCatalog; never an independent routing input. */
  readonly preferredProtocol?: ProtocolId;
  readonly capabilities: ModelCapabilities;
  readonly limits?: {
    readonly context?: number;
    readonly maxOutput?: number;
  };
  readonly pricing?: {
    readonly currency?: string;
    readonly input?: number;
    readonly output?: number;
    readonly cacheRead?: number;
    readonly cacheWrite?: number;
    readonly unit?: string;
  };
  readonly runtime?: {
    readonly status?: string;
    readonly successRate?: number;
    readonly ttftMs?: number;
    readonly throughputTps?: number;
    readonly observedAt?: string;
  };
}

/** Caller supplied routing data lives only in the protocols array. */
export type MandapiModelInput = Omit<MandapiModel, 'preferredProtocol'>;

export interface FindModelsOptions {
  readonly capability?: ModelCapability;
  readonly protocol?: ProtocolId;
}

export interface ModelCatalog {
  getModel(id: string): MandapiModel | undefined;
  /** Alias matching catalog.get(id). */
  get(id: string): MandapiModel | undefined;
  listModels(): readonly MandapiModel[];
  findModels(options?: FindModelsOptions): readonly MandapiModel[];
  resolvePreferredProtocol(id: string): ProtocolId | undefined;
}
