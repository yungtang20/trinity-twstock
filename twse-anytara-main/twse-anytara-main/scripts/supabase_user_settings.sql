-- 在 Supabase 跑一次 (SQL Editor): 建立 user_settings 表
-- POST /api/settings 會 synchronous 寫呢個表, server 重啟都會自動 restore

CREATE TABLE IF NOT EXISTS user_settings (
  id         TEXT PRIMARY KEY,
  longcat_api_key    TEXT NOT NULL DEFAULT '',
  longcat_base_url   TEXT NOT NULL DEFAULT 'https://api.longcat.chat/openai/v1',
  longcat_model      TEXT NOT NULL DEFAULT 'LongCat-2.0',
  finmind_api_key    TEXT NOT NULL DEFAULT '',
  webhook_url        TEXT NOT NULL DEFAULT '',
  updated_at         TIMESTAMPTZ DEFAULT now()
);

-- 預設值
INSERT INTO user_settings (id) VALUES ('singleton')
ON CONFLICT (id) DO NOTHING;

-- RLS: 開放讀取俾 anon (之後再 tighten)
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow anon read" ON user_settings FOR SELECT USING (true);
CREATE POLICY "allow service role write" ON user_settings FOR ALL WITH CHECK (true);
