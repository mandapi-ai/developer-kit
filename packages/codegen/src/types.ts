export type ProtocolId = 'chat' | 'responses' | 'messages' | 'gemini';
export type Language = 'python' | 'typescript' | 'curl' | 'go' | 'java' | 'csharp' | 'ruby';
export type JsonValue = string | number | boolean | null | JsonValue[] | JsonObject;
export interface JsonObject { [key: string]: JsonValue }
export type AuthType = 'bearer' | 'x-api-key' | 'x-goog-api-key';
export interface Message { role: 'system' | 'developer' | 'user' | 'assistant'; content: string }
export interface RequestOptions {
  model: string;
  protocol: ProtocolId;
  baseUrl: string;
  prompt?: string;
  messages?: readonly Message[];
  system?: string;
  maxTokens?: number;
  /** Full protocol-native JSON. Required fields are checked; unknown JSON fields are preserved. */
  body?: JsonObject;
  parameters?: JsonObject;
  /** Explicit gateway route override; {model} is URL-encoded by the wire layer. */
  endpointPath?: string;
  auth?: AuthType;
  apiKeyEnv?: string;
  headers?: Record<string, string>;
}
export interface GenerateOptions extends RequestOptions { language: Language }
export interface WireRequest {
  method: 'POST';
  url: string;
  baseUrl: string;
  path: string;
  headers: Record<string, string>;
  auth: { header: string; prefix: string; env: string };
  body: JsonObject;
}
/** Structural interface: codegen works independently of the catalog package. */
export interface ModelCatalog {
  getModel(id: string): { id: string; protocols: readonly { id: ProtocolId; preferred?: boolean }[] } | undefined;
  resolvePreferredProtocol(id: string): ProtocolId | undefined;
}
export interface GenerateForModelOptions extends Omit<GenerateOptions, 'protocol'> {
  catalog: ModelCatalog;
  protocol?: ProtocolId;
  /** Explicit fallback for missing catalog data; no name-based heuristic is applied. */
  fallbackProtocol?: ProtocolId;
}
