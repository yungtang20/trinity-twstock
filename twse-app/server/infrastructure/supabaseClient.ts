/**
 * TRINITY — 後端 Supabase Client
 *
 * 由 server 統一管理，前端不可直接引用。
 * 僅用於 AI 分析備份，不作為主要資料來源。
 */

import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { config } from '../config';

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  if (!config.supabase.enabled) return null;
  if (!client) {
    client = createClient(config.supabase.url, config.supabase.anonKey);
  }
  return client;
}
