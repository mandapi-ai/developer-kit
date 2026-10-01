import { DEFAULT_PROMPT } from '../config/placeholders.js';
import type { Message, RequestOptions } from '../types.js';
export function buildMessages(options: RequestOptions): Message[] {
  if (options.messages !== undefined && options.prompt !== undefined) throw new Error('Use prompt or messages, not both');
  const messages = options.messages ? options.messages.map(message => ({ ...message })) : [{ role: 'user' as const, content: options.prompt ?? DEFAULT_PROMPT }];
  if (options.system !== undefined) messages.unshift({ role: 'system', content: options.system });
  if (!messages.length) throw new Error('At least one message is required');
  for (const message of messages) {
    if (!['system', 'developer', 'user', 'assistant'].includes(message.role) || typeof message.content !== 'string') throw new Error('Messages must have a supported role and string content; use body for native multimodal/tool payloads');
  }
  return messages;
}
