-- ── Analysis History (資料版本控制) ──────────────────────

CREATE TABLE IF NOT EXISTS analysis_history (
  analysis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  stock_id TEXT NOT NULL,
  analysis_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  price_date TEXT,
  tdcc_date TEXT,
  revenue_date TEXT,
  financial_date TEXT,
  prompt_version TEXT,
  model_version TEXT,
  result_summary TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_history_stock_id ON analysis_history(stock_id);
CREATE INDEX IF NOT EXISTS idx_analysis_history_time ON analysis_history(analysis_time DESC);

-- ── Stock Master (股票主檔) ────────────────────────────────

CREATE TABLE IF NOT EXISTS stock_master (
  stock_id TEXT PRIMARY KEY,
  stock_name TEXT NOT NULL,
  market TEXT NOT NULL, -- 'TSE' or 'OTC'
  industry_category TEXT,
  list_date TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_master_market ON stock_master(market);
CREATE INDEX IF NOT EXISTS idx_stock_master_active ON stock_master(is_active);

-- ── Prompt Templates (Prompt 版本管理) ─────────────────────

CREATE TABLE IF NOT EXISTS prompt_templates (
  prompt_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  content TEXT NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prompt_templates_active ON prompt_templates(is_active);

-- ── AI Analysis Cache (分析結果快取) ───────────────────────

CREATE TABLE IF NOT EXISTS ai_analysis_cache (
  cache_key TEXT PRIMARY KEY, -- format: {stock_id}_{template}_{data_version_hash}
  stock_id TEXT NOT NULL,
  template TEXT NOT NULL,
  data_version_hash TEXT NOT NULL,
  result TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_analysis_cache_stock ON ai_analysis_cache(stock_id);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_cache_expires ON ai_analysis_cache(expires_at);

-- ── Data Sync Log (資料同步日誌) ──────────────────────────

CREATE TABLE IF NOT EXISTS data_sync_log (
  sync_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sync_type TEXT NOT NULL, -- 'twse', 'tpex', 'tdcc', 'finmind'
  sync_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status TEXT NOT NULL, -- 'success', 'failed', 'partial'
  records_count INTEGER DEFAULT 0,
  error_message TEXT,
  metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_data_sync_log_type ON data_sync_log(sync_type);
CREATE INDEX IF NOT EXISTS idx_data_sync_log_time ON data_sync_log(sync_time DESC);
