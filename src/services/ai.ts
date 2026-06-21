import { API_CONFIG } from '../config/apis';
import OpenAI from 'openai';

interface AIProviderOptions {
  provider: 'longcat' | 'openai' | 'gemini';
  apiKey?: string;
  baseURL?: string;
}

export function createAIClient(options: AIProviderOptions) {
  if (options.provider === 'longcat' || options.provider === 'openai') {
    return new OpenAI({
      apiKey: options.apiKey || (typeof process !== 'undefined' ? process.env.VITE_LONGCAT_API_KEY : ''),
      baseURL: options.baseURL || API_CONFIG.LONGCAT_BASE_URL,
    });
  }
  // Add other providers like Gemini here later
  throw new Error(`Provider ${options.provider} is not fully implemented yet.`);
}
