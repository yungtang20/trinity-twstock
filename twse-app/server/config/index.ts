/**
 * TRINITY — 後端統一配置管理
 *
 * 所有敏感資訊統一由 server 環境變數管理。
 * 前端不可直接引用此模組。
 */

function env(key: string, fallback?: string): string {
  const value = process.env[key];
  if (value === undefined || value === '') {
    if (fallback !== undefined) return fallback;
    if (process.env.NODE_ENV === 'production') {
      throw new Error(`Missing required environment variable: ${key}`);
    }
    return '';
  }
  return value;
}

export const config = {
  env: env('NODE_ENV', 'development'),
  port: parseInt(env('PORT', '3000'), 10),

  supabase: {
    url: env('SUPABASE_URL'),
    anonKey: env('SUPABASE_ANON_KEY'),
    get enabled(): boolean {
      return !!(this.url && this.anonKey);
    },
  },

  longcat: {
    apiKey: env('LONGCAT_API_KEY'),
    baseUrl: env('LONGCAT_BASE_URL', 'https://api.longcat.chat/openai/v1'),
    model: env('LONGCAT_MODEL', 'LongCat-2.0-Preview'),
  },

  finmind: {
    apiKey: env('FINMIND_API_KEY'),
  },

  update: {
    webhookUrl: env('UPDATE_WEBHOOK_URL'),
  },
} as const;

export type Config = typeof config;
