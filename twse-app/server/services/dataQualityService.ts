import { getSupabase } from '../infrastructure/supabaseClient';

// ── Types ──────────────────────────────────────────────────

export interface DataQualityReport {
  stock_id: string;
  timestamp: string;
  checks: {
    name: string;
    status: 'pass' | 'warn' | 'fail';
    message: string;
  }[];
  overall_score: number; // 0-100
}

// ── Validate Price Data ────────────────────────────────────

async function validatePriceData(stockId: string): Promise<DataQualityReport['checks']> {
  const checks: DataQualityReport['checks'] = [];

  const supabase = getSupabase();
  if (!supabase) {
    checks.push({ name: 'price_connection', status: 'fail', message: 'Supabase 未連線' });
    return checks;
  }

  try {
    const { data, error } = await supabase
      .from('stock_price')
      .select('date, close, volume')
      .eq('stock_id', stockId)
      .order('date', { ascending: false })
      .limit(250);

    if (error) {
      checks.push({ name: 'price_query', status: 'fail', message: `查詢失敗: ${error.message}` });
      return checks;
    }

    if (!data || data.length === 0) {
      checks.push({ name: 'price_data', status: 'fail', message: '無價格數據' });
      return checks;
    }

    checks.push({ name: 'price_data', status: 'pass', message: `${data.length} 筆價格數據` });

    // Check for null/zero values
    const invalidRows = data.filter((r) => !r.close || r.close <= 0);
    if (invalidRows.length > 0) {
      checks.push({
        name: 'price_values',
        status: 'warn',
        message: `${invalidRows.length} 筆無效價格`,
      });
    } else {
      checks.push({ name: 'price_values', status: 'pass', message: '價格數據有效' });
    }

    // Check data freshness
    const latestDate = new Date(data[0].date);
    const today = new Date();
    const daysDiff = Math.floor((today.getTime() - latestDate.getTime()) / (1000 * 60 * 60 * 24));

    if (daysDiff > 7) {
      checks.push({
        name: 'price_freshness',
        status: 'warn',
        message: `數據過舊: ${daysDiff} 天前`,
      });
    } else {
      checks.push({ name: 'price_freshness', status: 'pass', message: `數據新鮮: ${daysDiff} 天前` });
    }
  } catch {
    checks.push({ name: 'price_query', status: 'fail', message: '查詢異常' });
  }

  return checks;
}

// ── Validate Institutional Data ────────────────────────────

async function validateInstitutionalData(stockId: string): Promise<DataQualityReport['checks']> {
  const checks: DataQualityReport['checks'] = [];

  const supabase = getSupabase();
  if (!supabase) {
    checks.push({ name: 'inst_connection', status: 'fail', message: 'Supabase 未連線' });
    return checks;
  }

  try {
    const { data, error } = await supabase
      .from('stock_institutional')
      .select('date, foreign_net, trust_net')
      .eq('stock_id', stockId)
      .order('date', { ascending: false })
      .limit(30);

    if (error) {
      checks.push({ name: 'inst_query', status: 'fail', message: `查詢失敗: ${error.message}` });
      return checks;
    }

    if (!data || data.length === 0) {
      checks.push({ name: 'inst_data', status: 'warn', message: '無法人數據' });
      return checks;
    }

    checks.push({ name: 'inst_data', status: 'pass', message: `${data.length} 筆法人數據` });
  } catch {
    checks.push({ name: 'inst_query', status: 'fail', message: '查詢異常' });
  }

  return checks;
}

// ── Validate TDCC Data ─────────────────────────────────────

async function validateTdccData(stockId: string): Promise<DataQualityReport['checks']> {
  const checks: DataQualityReport['checks'] = [];

  const supabase = getSupabase();
  if (!supabase) {
    checks.push({ name: 'tdcc_connection', status: 'fail', message: 'Supabase 未連線' });
    return checks;
  }

  try {
    const { data, error } = await supabase
      .from('stock_features')
      .select('date, whale_ratio')
      .eq('stock_id', stockId)
      .order('date', { ascending: false })
      .limit(26);

    if (error) {
      checks.push({ name: 'tdcc_query', status: 'fail', message: `查詢失敗: ${error.message}` });
      return checks;
    }

    if (!data || data.length === 0) {
      checks.push({ name: 'tdcc_data', status: 'warn', message: '無 TDCC 數據' });
      return checks;
    }

    checks.push({ name: 'tdcc_data', status: 'pass', message: `${data.length} 筆 TDCC 數據` });
  } catch {
    checks.push({ name: 'tdcc_query', status: 'fail', message: '查詢異常' });
  }

  return checks;
}

// ── Validate Stock Meta ────────────────────────────────────

async function validateStockMeta(stockId: string): Promise<DataQualityReport['checks']> {
  const checks: DataQualityReport['checks'] = [];

  const supabase = getSupabase();
  if (!supabase) {
    checks.push({ name: 'meta_connection', status: 'fail', message: 'Supabase 未連線' });
    return checks;
  }

  try {
    const { data, error } = await supabase
      .from('stock_meta')
      .select('stock_id, stock_name, market')
      .eq('stock_id', stockId)
      .single();

    if (error) {
      checks.push({ name: 'meta_query', status: 'fail', message: `查詢失敗: ${error.message}` });
      return checks;
    }

    if (!data) {
      checks.push({ name: 'meta_data', status: 'fail', message: '股票不存在' });
      return checks;
    }

    checks.push({ name: 'meta_data', status: 'pass', message: `${data.stock_name} (${data.market})` });
  } catch {
    checks.push({ name: 'meta_query', status: 'fail', message: '查詢異常' });
  }

  return checks;
}

// ── Run All Validation ─────────────────────────────────────

export async function validateStockData(stockId: string): Promise<DataQualityReport> {
  const timestamp = new Date().toISOString();

  const [priceChecks, instChecks, tdccChecks, metaChecks] = await Promise.all([
    validatePriceData(stockId),
    validateInstitutionalData(stockId),
    validateTdccData(stockId),
    validateStockMeta(stockId),
  ]);

  const checks = [...priceChecks, ...instChecks, ...tdccChecks, ...metaChecks];

  // Calculate overall score
  const passCount = checks.filter((c) => c.status === 'pass').length;
  const warnCount = checks.filter((c) => c.status === 'warn').length;
  const failCount = checks.filter((c) => c.status === 'fail').length;

  const overall_score = Math.round(
    ((passCount * 100 + warnCount * 50) / (checks.length * 100)) * 100
  );

  return {
    stock_id: stockId,
    timestamp,
    checks,
    overall_score,
  };
}
