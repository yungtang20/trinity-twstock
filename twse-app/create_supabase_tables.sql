-- ============================================================
-- Supabase Table Creation Script
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard
-- ============================================================

-- 股票歷史股價（主要表格）
CREATE TABLE IF NOT EXISTS stock_history (
  id BIGSERIAL PRIMARY KEY,
  stock_id TEXT NOT NULL,
  date DATE NOT NULL,
  open NUMERIC,
  high NUMERIC,
  low NUMERIC,
  close NUMERIC,
  volume BIGINT,
  amount NUMERIC,
  UNIQUE(stock_id, date)
);

-- 籌碼資料
CREATE TABLE IF NOT EXISTS institutional_data (
  id BIGSERIAL PRIMARY KEY,
  stock_id TEXT NOT NULL,
  date DATE NOT NULL,
  foreign_net BIGINT,
  trust_net BIGINT,
  dealer_net BIGINT,
  institutional_net BIGINT,
  UNIQUE(stock_id, date)
);

-- 集保資料
CREATE TABLE IF NOT EXISTS shareholding_unified (
  id BIGSERIAL PRIMARY KEY,
  stock_id TEXT NOT NULL,
  date DATE NOT NULL,
  whale_ratio NUMERIC,
  retail_ratio NUMERIC,
  whale_shares BIGINT,
  total_shares BIGINT,
  UNIQUE(stock_id, date)
);

-- 除權息事件
CREATE TABLE IF NOT EXISTS dividend_events (
  id BIGSERIAL PRIMARY KEY,
  stock_id TEXT NOT NULL,
  date DATE NOT NULL,
  dividend_type TEXT,
  amount NUMERIC,
  UNIQUE(stock_id, date, dividend_type)
);

-- 交易日曆
CREATE TABLE IF NOT EXISTS stock_trading_calendar (
  date DATE PRIMARY KEY,
  is_trading_day BOOLEAN DEFAULT true,
  note TEXT
);

-- PER 資料
CREATE TABLE IF NOT EXISTS per_data (
  id BIGSERIAL PRIMARY KEY,
  stock_id TEXT NOT NULL,
  date DATE NOT NULL,
  per NUMERIC,
  peg NUMERIC,
  UNIQUE(stock_id, date)
);

-- 建立索引
CREATE INDEX IF NOT EXISTS idx_stock_history_stock_id ON stock_history(stock_id);
CREATE INDEX IF NOT EXISTS idx_stock_history_date ON stock_history(date);
CREATE INDEX IF NOT EXISTS idx_institutional_data_stock_id ON institutional_data(stock_id);
CREATE INDEX IF NOT EXISTS idx_institutional_data_date ON institutional_data(date);
CREATE INDEX IF NOT EXISTS idx_shareholding_unified_stock_id ON shareholding_unified(stock_id);
CREATE INDEX IF NOT EXISTS idx_dividend_events_stock_id ON dividend_events(stock_id);
CREATE INDEX IF NOT EXISTS idx_per_data_stock_id ON per_data(stock_id);

-- 啟用 RLS（Row Level Security）
ALTER TABLE stock_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE institutional_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE shareholding_unified ENABLE ROW LEVEL SECURITY;
ALTER TABLE dividend_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_trading_calendar ENABLE ROW LEVEL SECURITY;
ALTER TABLE per_data ENABLE ROW LEVEL SECURITY;

-- 建立匿名存取政策
CREATE POLICY "Allow anonymous read" ON stock_history FOR SELECT USING (true);
CREATE POLICY "Allow anonymous read" ON institutional_data FOR SELECT USING (true);
CREATE POLICY "Allow anonymous read" ON shareholding_unified FOR SELECT USING (true);
CREATE POLICY "Allow anonymous read" ON dividend_events FOR SELECT USING (true);
CREATE POLICY "Allow anonymous read" ON stock_trading_calendar FOR SELECT USING (true);
CREATE POLICY "Allow anonymous read" ON per_data FOR SELECT USING (true);
