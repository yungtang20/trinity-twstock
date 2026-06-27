import { config } from '../config';
import { getSupabase } from '../infrastructure/supabaseClient';

// ── Types ──────────────────────────────────────────────────

export interface AnalysisResult {
  stock_id: string;
  template: string;
  result: string;
  created_at: string;
  data_version: DataVersion;
  prompt_version: string;
  model_version: string;
}

export interface DataVersion {
  price_date: string;
  tdcc_date: string;
  revenue_date: string;
  financial_date: string;
}

export interface AnalysisHistory {
  analysis_id: string;
  stock_id: string;
  analysis_time: string;
  price_date: string;
  tdcc_date: string;
  revenue_date: string;
  financial_date: string;
  prompt_version: string;
  model_version: string;
  result_summary: string;
}

// ── Prompt Templates ───────────────────────────────────────

const PROMPT_TEMPLATES: Record<string, { name: string; version: string }> = {
  goldman: { name: '高盛基本面分析', version: 'v1' },
  bridgewater: { name: '橋水避險基金分析', version: 'v1' },
  renaissance: { name: '文藝復興量化分析', version: 'v1' },
};

// ── Build AI Context ───────────────────────────────────────

export interface AIContext {
  stock_id: string;
  stock_name: string;
  price_data: { date: string; close: number; volume: number }[];
  institutional_data: { date: string; trust_net: number }[];
  tdcc_data: { date: string; whale_ratio: number }[];
  price_date: string;
  tdcc_date: string;
  data_quality: {
    price: boolean;
    institutional: boolean;
    tdcc: boolean;
  };
}

async function buildAIContext(stockId: string): Promise<AIContext | null> {
  const supabase = getSupabase();
  if (!supabase) return null;

  // Get stock meta
  const { data: meta } = await supabase
    .from('stock_meta')
    .select('stock_id, stock_name')
    .eq('stock_id', stockId)
    .single();

  if (!meta) return null;

  // Get price data (last 250 days)
  const { data: priceData } = await supabase
    .from('stock_price')
    .select('date, close, volume')
    .eq('stock_id', stockId)
    .order('date', { ascending: false })
    .limit(250);

  // Get institutional data (last 30 days)
  const { data: instData } = await supabase
    .from('stock_institutional')
    .select('date, trust_net')
    .eq('stock_id', stockId)
    .order('date', { ascending: false })
    .limit(30);

  // Get TDCC data (last 26 weeks)
  const { data: tdccData } = await supabase
    .from('stock_features')
    .select('date, whale_ratio')
    .eq('stock_id', stockId)
    .order('date', { ascending: false })
    .limit(26);

  if (!priceData || priceData.length === 0) return null;

  return {
    stock_id: stockId,
    stock_name: meta.stock_name,
    price_data: priceData,
    institutional_data: instData || [],
    tdcc_data: tdccData || [],
    price_date: priceData[0].date,
    tdcc_date: tdccData?.[0]?.date || 'N/A',
    data_quality: {
      price: priceData.length > 0,
      institutional: (instData?.length || 0) > 0,
      tdcc: (tdccData?.length || 0) > 0,
    },
  };
}

// ── Get AI Analysis ────────────────────────────────────────

export async function getAIAnalysis(
  stockId: string,
  template: string = 'goldman'
): Promise<AnalysisResult | null> {
  const context = await buildAIContext(stockId);
  if (!context) return null;

  const templateConfig = PROMPT_TEMPLATES[template];
  if (!templateConfig) return null;

  const result = await callAIAPI(context, templateConfig);

  return {
    stock_id: stockId,
    template,
    result,
    created_at: new Date().toISOString(),
    data_version: {
      price_date: context.price_date,
      tdcc_date: context.tdcc_date,
      revenue_date: 'N/A',
      financial_date: 'N/A',
    },
    prompt_version: templateConfig.version,
    model_version: config.longcat.model,
  };
}

// ── Call AI API ────────────────────────────────────────────

async function callAIAPI(
  context: AIContext,
  templateConfig: { name: string; version: string }
): Promise<string> {
  const { stock_id, stock_name, price_data, institutional_data, tdcc_data } = context;

  // Only keep essential data to avoid context explosion
  const recentPrices = price_data.slice(0, 50);
  const recentInst = institutional_data.slice(0, 10);
  const recentTdcc = tdcc_data.slice(0, 8);

  const prompt = `
## 分析目標
${stock_id} ${stock_name}

## 資料版本
- 股價日期: ${context.price_date}
- TDCC日期: ${context.tdcc_date}

## 最近股價資料 (最近 ${recentPrices.length} 日)
${recentPrices.map((p) => `${p.date}: close=${p.close}, volume=${p.volume}`).join('\n')}

## 最近法人資料 (最近 ${recentInst.length} 日)
${recentInst.map((i) => `${i.date}: trust_net=${i.trust_net}`).join('\n')}

## 最近TDCC資料 (最近 ${recentTdcc.length} 週)
${recentTdcc.map((t) => `${t.date}: whale=${t.whale_ratio}%`).join('\n')}

## 分析要求
使用 ${templateConfig.name} (${templateConfig.version}) 分析框架，評估此股票的投資價值。

請提供：
1. 投資建議（買進/持有/賣出）
2. 目標價
3. 止損價
4. 關鍵觀察指標
`;

  try {
    const res = await fetch(`${config.longcat.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${config.longcat.apiKey}`,
      },
      body: JSON.stringify({
        model: config.longcat.model,
        messages: [
          { role: 'system', content: '你是一位專業的台股分析師，請根據提供的數據進行分析。' },
          { role: 'user', content: prompt },
        ],
        temperature: 0.7,
        max_tokens: 2000,
      }),
    });

    if (!res.ok) {
      return `AI API error: ${res.status}`;
    }

    const json = await res.json();
    return json.choices?.[0]?.message?.content || 'No response';
  } catch (err: any) {
    return `AI API call failed: ${err.message}`;
  }
}

// ── Save Analysis History ──────────────────────────────────

export async function saveAnalysisHistory(result: AnalysisResult): Promise<void> {
  const supabase = getSupabase();
  if (!supabase) return;

  try {
    await supabase.from('analysis_history').insert({
      analysis_id: crypto.randomUUID(),
      stock_id: result.stock_id,
      analysis_time: result.created_at,
      price_date: result.data_version.price_date,
      tdcc_date: result.data_version.tdcc_date,
      revenue_date: result.data_version.revenue_date,
      financial_date: result.data_version.financial_date,
      prompt_version: result.prompt_version,
      model_version: result.model_version,
      result_summary: result.result.substring(0, 500),
    });
  } catch (err) {
    console.error('saveAnalysisHistory error:', err);
  }
}

// ── Get Analysis History ───────────────────────────────────

export async function getAnalysisHistory(
  stockId: string,
  limit = 10
): Promise<AnalysisHistory[]> {
  const supabase = getSupabase();
  if (!supabase) return [];

  try {
    const { data, error } = await supabase
      .from('analysis_history')
      .select('*')
      .eq('stock_id', stockId)
      .order('analysis_time', { ascending: false })
      .limit(limit);

    if (error) {
      console.error('getAnalysisHistory error:', error.message);
      return [];
    }

    return data || [];
  } catch {
    return [];
  }
}
