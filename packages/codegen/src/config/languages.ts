import type { Language } from '../types.js';
export const LANGUAGES: readonly Language[] = Object.freeze(['python', 'typescript', 'curl', 'go', 'java', 'csharp', 'ruby']);
export function validateLanguage(value: Language): void {
  if (!LANGUAGES.includes(value)) throw new Error(`Unsupported language: ${value}`);
}
