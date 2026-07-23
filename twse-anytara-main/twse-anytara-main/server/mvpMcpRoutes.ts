// MVP route: 9 free FinMind datasets + MCP backup + 12 framework prompts
// All data fetching is parameterized by stockId. Exported `runFrameworkAnalysis` is reused by jobQueue.
import { Request, Response } from "express";
import { callMcpSerial } from "./lib/mcpClient";
import { startJob, getJob, listJobs, deleteJob, deleteAllJobs } from "./lib/jobQueue";
import { syncTdcc, getTdccSqliteStatus } from "./lib/tdccDownload";
import { supabase } from "./services";
import { GoogleGenAI } from "@google/genai";

const FINMIND = "https://api.finmindtrade.com/api/v4/data";

export interface DynamicSettings {
  longcatApiKey: string;
  longcatBaseUrl: string;
  longcatModel: string;
  finmindApiKey: string;
}

export async function getDynamicSettings(): Promise<DynamicSettings> {
  const settings: DynamicSettings = {
    longcatApiKey: process.env.VITE_LONGCAT_API_KEY || process.env.LONGCAT_API_KEY || "",
    longcatBaseUrl: process.env.VITE_LONGCAT_BASE_URL || process.env.LONGCAT_BASE_URL || "",
    longcatModel: process.env.VITE_LONGCAT_MODEL || process.env.LONGCAT_MODEL || "LongCat-2.0",
    finmindApiKey: process.env.VITE_FINMIND_API_KEY || process.env.FINMIND_API_KEY || "",
  };

  // Best effort load from Supabase user_settings
  try {
    if (supabase) {
      const { data } = await supabase
        .from("user_settings")
        .select("longcat_api_key, longcat_base_url, longcat_model, finmind_api_key")
        .eq("id", "singleton")
        .maybeSingle();
      if (data) {
        if (data.longcat_api_key) settings.longcatApiKey = data.longcat_api_key;
        if (data.longcat_base_url) settings.longcatBaseUrl = data.longcat_base_url;
        if (data.longcat_model) settings.longcatModel = data.longcat_model;
        if (data.finmind_api_key) settings.finmindApiKey = data.finmind_api_key;
      }
    }
  } catch (e) {
    console.warn("[getDynamicSettings] Supabase settings query failed, falling back to process.env", e);
  }

  return settings;
}

function getTaipeiDateStr(): string {
  const d = new Date();
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = formatter.formatToParts(d);
  const year = parts.find(p => p.type === "year")?.value || "";
  const month = parts.find(p => p.type === "month")?.value || "";
  const day = parts.find(p => p.type === "day")?.value || "";
  return `${year}-${month}-${day}`;
}

function getPastTaipeiDateStr(yearsAgo: number): string {
  const d = new Date();
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = formatter.formatToParts(d);
  const year = parts.find(p => p.type === "year")?.value || "";
  const month = parts.find(p => p.type === "month")?.value || "";
  const day = parts.find(p => p.type === "day")?.value || "";
  
  const pastYear = Number(year) - yearsAgo;
  return `${pastYear}-${month}-${day}`;
}

function getLatestTradingDayYYYYMMDD(): string {
  const taipeiTimeStr = new Date().toLocaleString("en-US", { timeZone: "Asia/Taipei" });
  const taipeiDate = new Date(taipeiTimeStr);
  const dayOfWeek = taipeiDate.getDay();
  const hour = taipeiDate.getHours();
  const minute = taipeiDate.getMinutes();

  let targetDate = taipeiDate;
  if (dayOfWeek >= 1 && dayOfWeek <= 5) {
    if (hour < 14 || (hour === 14 && minute < 30)) {
      targetDate = new Date(taipeiDate);
      targetDate.setDate(targetDate.getDate() - 1);
    }
  } else {
    targetDate = new Date(taipeiDate);
    while (targetDate.getDay() === 0 || targetDate.getDay() === 6) {
      targetDate.setDate(targetDate.getDate() - 1);
    }
  }

  const y = targetDate.getFullYear();
  const m = String(targetDate.getMonth() + 1).padStart(2, '0');
  const d = String(targetDate.getDate()).padStart(2, '0');
  return `${y}${m}${d}`;
}

const FINMIND_DATASETS = [
  { ds: "TaiwanStockPrice",            label: "股价日K",         getDates: () => ({ sd: getPastTaipeiDateStr(2), ed: getTaipeiDateStr() }) },
  { ds: "TaiwanStockMonthRevenue",     label: "月营收",           getDates: () => ({ sd: getPastTaipeiDateStr(3), ed: getTaipeiDateStr() }) },
  { ds: "TaiwanStockPER",              label: "PER/PBR/Yield日", getDates: () => ({ sd: getPastTaipeiDateStr(2), ed: getTaipeiDateStr() }) },
  { ds: "TaiwanStockFinancialStatements", label: "季损益科目值", getDates: () => ({ sd: getPastTaipeiDateStr(4), ed: getTaipeiDateStr() }) },
  { ds: "TaiwanStockBalanceSheet",     label: "負債/資產歷程",   getDates: () => ({ sd: getPastTaipeiDateStr(4), ed: getTaipeiDateStr() }) },
  { ds: "TaiwanStockInstitutionalInvestorsBuySell", label: "三大法人買超日", getDates: () => ({ sd: getPastTaipeiDateStr(2), ed: getTaipeiDateStr() }) },
  { ds: "TaiwanStockMarginPurchaseShortSale", label: "融资券日", getDates: () => ({ sd: getPastTaipeiDateStr(2), ed: getTaipeiDateStr() }) },
  { ds: "TaiwanStockDividend",         label: "年度股利",         getDates: () => ({ sd: getPastTaipeiDateStr(10), ed: getTaipeiDateStr() }) },
  { ds: "TaiwanStockShareholding",     label: "外資持有比率日",   getDates: () => ({ sd: getPastTaipeiDateStr(2), ed: getTaipeiDateStr() }) },
];

const fetchFinMind = async (ds: string, stockId: string, sd: string, ed: string, finmindApiKey: string): Promise<string> => {
  if (!finmindApiKey) return `[${ds}: 未設 VITE_FINMIND_API_KEY]`;
  try {
    const r = await fetch(`${FINMIND}?dataset=${ds}&data_id=${stockId}&start_date=${sd}&end_date=${ed}&token=${finmindApiKey}`);
    const j = await r.json() as any;
    const rows = (j.data || []).length;
    if (rows === 0) return `[${ds}: 0 rows, free tier 被擋或無資料]`;
    return `[${ds}] rows=${rows}\n${JSON.stringify((j.data || []).slice(-8)).slice(0, 2000)}`;
  } catch (e: any) { return `[${ds}: ${e.message}]`; }
};

const fetchMcpRealtime = async (stockId: string): Promise<string> => {
  try {
    const dateStr = getLatestTradingDayYYYYMMDD();
    const res = await callMcpSerial([
      { name: "get_realtime_quote", args: { stock_nos: [stockId] } },
      { name: "get_market_valuation_by_date", args: { date: dateStr, stock_no: stockId } },
    ]);
    return Object.entries(res).map(([k, v]) => `[${k}]\n${v}`).join("\n\n");
  } catch (e: any) { return `[MCP 即時: ${e.message}]`; }
};

const FRAMEWORK_PROMPTS: Record<string, { sys: string; ask: (stockId: string, dataBlock: string) => string; mtok: number }> = {
  goldman: {
    sys: "你是高盛 (Goldman Sachs) 资深分析师 (20 年资历, 管理兆元 AUM)。产出繁体中文 Markdown Pitch-book 研报。",
    ask: (stockId, data) => `针对【标的 ${stockId}】产出完整 12 段高盛研报。必须引用资料中数字。

${data}

**严禁使用模型预训练的「2024 旧数据」，强制引用上方资料数字**。
12 段: 1.Rating Box 2.护城河 3.收入 4.盈利三率 5.负债/F CF 7.竞争 8.估值同业 9.看多看空各 5 点 10.3 情境 11.融资券/法人流 12.一段式结论 (6000-9000字)`,
    mtok: 7500,
  },
  morgan_stanley: {
    sys: "摩士丹利技术分析师。繁体中文 Markdown。",
    ask: (stockId, data) => `针对【标的 ${stockId}】产出 8 段技术分析报告:
1.趋势(支撑压力) 2.均线系统 3.RSI 4.MACD 5.布林带 6.量价关系 7.交易设定(进/停損/目标) 8.失效条件
提供明确价位计算过程。引用资料数字。4000-6000字。${data}`,
    mtok: 6500,
  },
  bridgewater: {
    sys: "桥水风险分析师。繁体中文 Markdown。",
    ask: (stockId, data) => `针对【标的 ${stockId}】产出桥水风险备忘录:
1.风险仪表板(波动率/Beta/VaR/MaxDD)
2.法人流分析(引用三大法人日资料)
3.融资券水位判读
4.系统性情境
5.对冲建议
先提供波动率/Beta/VaR 数字计算。3000-5000字。${data}`,
    mtok: 6000,
  },
  jpmorgan: {
    sys: "摩根大通财报分析师。繁体中文。",
    ask: (stockId, data) => `针对【标的 ${stockId}】产出摩根大通财报分析:
1.季营收/YoY 走势(引用季损益资料)
2.惊喜/失望模式
3.关键 KPI
4.管理层指引判讀
5.交易计划
计算 YoY/QoQ 成长率。3000-5000字。${data}`,
    mtok: 6000,
  },
  blackrock: {
    sys: "贝莱德收息分析师。繁体中文。",
    ask: (stockId, data) => `针对【标的 ${stockId}】产出 BlackRock 股息分析:
1.10 年股利元数 + 当前殖利率
2.安全性评分卡(0-100)
3.收益陷阱检查
4.DRIP 10 年複利模拟
5.结论
引用 PER 資料 + 股利资料。3000-5000字。${data}`,
    mtok: 6000,
  },
  citadel: {
    sys: "城堡宏观轮动师。繁体中文。",
    ask: (stockId, data) => `针对【标的 ${stockId}】产出 Citadel 宏观轮动分析:
1.经济周期定位
2.外资产业分布
3.防守 vs 进攻配置
4.推荐 ETF 清单
引用外资产业资料 + 大盘评估。3000-5000字。${data}`,
    mtok: 6000,
  },
  renaissance: {
    sys: "文艺复兴量化研究员。繁体中文。",
    ask: (stockId, data) => `针对【标的 ${stockId}】产出多因子选股报告:
1.价值因子: PER 百分位 (引用 PER 日 K)
2.品质因子: ROE 稳定性
3.动量因子: 6/12 月報酬
4.成长因子: 营收盈余年成长
5.情绪因子: 法人流 + 外资持股变化
综合评分 + 选股清单。3000-5000字。${data}`,
    mtok: 6000,
  },
  vanguard: {
    sys: "先锋 ETF 组合师。繁体中文。",
    ask: (stockId, data) => `针对【标的 ${stockId}】产出 Vanguard IPS:
1.资产配置(股/债/现)
2.Core + Satellite ETF 清单
3.地理分散
4.预期风险/回报
5.再平衡规则
引用大盘指标计算波動率。3000-5000字。${data}`,
    mtok: 6000,
  },
  deshaw: {
    sys: "D.E. Shaw 期权架构师。繁体中文。",
    ask: (stockId, data) => `针对【标的 ${stockId}】产出期权策略报告:
1.两套完整期权策略 + Greeks 解说
2.进场/退场/调整规则
引用即时股价 + PER 数字。3000-5000字。${data}`,
    mtok: 6000,
  },
  twosigma: {
    sys: "Two Sigma 巨观分析师。繁体中文。",
    ask: (stockId, data) => `针对【标的 ${stockId}】产出 Two Sigma 巨观展望:
1.一页摘要 + 法人流趋势
2.外資持股比率變化
3.融資券壓力測試
引用法人日 / 外資持股日资料。3000-5000字。${data}`,
    mtok: 6000,
  },
  hedge_fund: {
    sys: "避险基金高级分析师合约负债 + 供应链。繁体中文。",
    ask: (stockId, data) => `针对【标的 ${stockId}】产出供应链压力测试:
1.合約負債 / AP 分析 (引用 BalanceSheet 历史)
2.法人 / Margin 散户接刀风险
3.EPS 估值三情境
引用 909 期負债 + 法人流资料。3000-5000字。${data}`,
    mtok: 6000,
  },
  industry: {
    sys: "顶尖产业分析师。繁体中文。",
    ask: (stockId, data) => `针对【标的 ${stockId}】产出产业分析:
1.供应链地图
2.合約負債結構判讀
3.ROE 趨勢
引用 BalanceSheet / MonthRevenue 历史. 3000-5000字。${data}`,
    mtok: 6000,
  },
  berkshire: {
    sys: "波克夏·哈薩威（Berkshire Hathaway）董事會核心決策模擬器（由華倫·巴菲特與查理·蒙格共同主持）。繁體中文 Markdown 撰寫。",
    ask: (stockId, data) => `針對【標的 ${stockId}】產出「波克夏董事會價值投資與多元思維備忘錄」：

請將報告分為以下 6 大章節，深度進行商業、護城河與資本分配分析：

1. **巴菲特與蒙格的虛擬對話 (Berkshire Fireside Chat)**
   - 模擬巴菲特與蒙格針對該企業的商業模式、特許經營權與估值進行 3 輪對話與辯論。巴菲特著重「護城河與優質管理、長期持有價值」，蒙格著重「Lollapalooza 效應與多元思維、逆向思考（不要做傻事）」，語氣必須符合兩人經典幽默且充滿睿智的口吻。
   
2. **商譽與護城河質性評估 (Moat & Franchise Quality)**
   - 深入評估其特許權（Franchise）與消費壟斷力，分析是「無形資產、轉換成本、網絡效應、還是成本優勢」？
   - 計算與分析其「資本分配效率與長期 ROE / ROIC 穩定度」。

3. **自由現金流與「股東盈餘」折現 (Shareholder Earnings & DCF)**
   - 計算該標的的「股東盈餘 (Shareholder Earnings)」：營業現金流 + 折舊攤銷 - 必要資本支出。
   - 使用保守的折現率與安全邊際（Margin of Safety）估算其內在價值。

4. **蒙格多元思維模型檢視 (Munger's Lollapalooza Checklist)**
   - 從跨學學科角度（如物理學臨界點、生物學演化、心理學誤判、工程學安全冗餘等），分析該企業是否存在多重力量疊加的「Lollapalooza 效應」。
   
5. **安全邊際與資本分配建議 (Margin of Safety & Allocation)**
   - 給出董事會決策決議：【強力買進且終身持有】、【列入觀察名單】還是【果斷避開（太過複雜或不具備安全邊際）】。
   
6. **逆向思考：什麼會讓我們毀滅？ (Invert, Always Invert)**
   - 「反過來想，總是反過來想」。列出 5 個將導致該企業在未來 10 年內徹底破產或喪失競爭力的毀滅性因素。

請務必引用下方最新數據與歷史財務數字，嚴禁使用預訓練的舊數據。5000-8000 字：
${data}`,
    mtok: 7500,
  },
};

export async function runFrameworkAnalysis(stockId: string, frameworkId: string): Promise<string> {
  const settings = await getDynamicSettings();
  const rawGeminiKey = (process.env.GEMINI_API_KEY || "").trim();
  const hasGemini = !!rawGeminiKey; 
  const hasLongcat = !!settings.longcatApiKey;
  
  if (!hasLongcat && !hasGemini) {
    throw new Error("未偵測到有效的 Gemini 或 LongCat API 金鑰，請先到 設定 或環境變數中配置。");
  }

  const prompt = FRAMEWORK_PROMPTS[frameworkId] || FRAMEWORK_PROMPTS.goldman;

  const finmindResults = await Promise.all(
    FINMIND_DATASETS.map(async (d) => {
      const { sd, ed } = d.getDates();
      return `## ${d.label} (${d.ds})\n${await fetchFinMind(d.ds, stockId, sd, ed, settings.finmindApiKey)}`;
    })
  );
  const mcpBlock = await fetchMcpRealtime(stockId);
  const tdccStatus = getTdccSqliteStatus();
  const tdccBlock = `\n## 最新 TDCC 股權分散\nSQLite: latest=${tdccStatus.latest}, distinct=${tdccStatus.totalDistinctStocks}, totalRows=${tdccStatus.totalRows}`;

  const dataBlock = `--- FINMIND 9 datasets ---\n${finmindResults.join("\n\n")}\n\n--- MCP 即時 ---\n${mcpBlock}${tdccBlock}\n--- END ---`;
  const userMsg = prompt.ask(stockId, dataBlock);

  const errors: string[] = [];

  // 1. Prioritize LongCat if configured (since the user explicitly provided this key in Settings)
  if (hasLongcat) {
    try {
      console.log(`[jobQueue] Attempting LongCat for stock ${stockId}, framework ${frameworkId}`);
      const baseUrl = (settings.longcatBaseUrl || "https://api.longcat.chat").trim().replace(/\/$/, "");
      let completionsUrl = baseUrl;
      if (baseUrl === "https://api.longcat.chat") {
        completionsUrl = "https://api.longcat.chat/openai/v1/chat/completions";
      } else if (!completionsUrl.endsWith("/chat/completions")) {
        completionsUrl = completionsUrl.endsWith("/v1")
          ? `${completionsUrl}/chat/completions`
          : `${completionsUrl}/v1/chat/completions`;
      }

      const res = await fetch(completionsUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + settings.longcatApiKey },
        body: JSON.stringify({
          model: settings.longcatModel || "LongCat-2.0",
          messages: [{ role: "system", content: prompt.sys }, { role: "user", content: userMsg }],
          temperature: 0.25,
          max_tokens: prompt.mtok,
        }),
      });
      if (!res.ok) {
        const errText = await res.text().catch(() => "");
        throw new Error(`LongCat ${res.status}: ${errText.slice(0, 200)}`);
      }
      const j = await res.json() as any;
      if (j.error) throw new Error(`LongCat error: ${JSON.stringify(j.error).slice(0, 200)}`);
      const report = j.choices?.[0]?.message?.content;
      if (!report) throw new Error("LongCat 空回覆");
      console.log(`[jobQueue] LongCat analysis completed successfully for ${stockId} (${frameworkId})`);
      return report;
    } catch (e: any) {
      console.error(`[jobQueue] LongCat failed: ${e.message}`);
      errors.push(`LongCat 錯誤: ${e.message}`);
    }
  }

  // 2. Try Gemini if LongCat was not available or if LongCat failed
  if (hasGemini) {
    try {
      console.log(`[jobQueue] Attempting Gemini for stock ${stockId}, framework ${frameworkId}`);
      const ai = new GoogleGenAI({
        apiKey: rawGeminiKey,
        httpOptions: {
          headers: {
            'User-Agent': 'aistudio-build',
          }
        }
      });
      const response = await ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: userMsg,
        config: {
          systemInstruction: prompt.sys,
          temperature: 0.25,
        }
      });
      if (response.text) {
        console.log(`[jobQueue] Gemini analysis completed successfully for ${stockId} (${frameworkId})`);
        return response.text;
      }
      throw new Error("Gemini 回傳了空的內容。");
    } catch (e: any) {
      console.error(`[jobQueue] Gemini failed: ${e.message}`);
      errors.push(`Gemini 錯誤: ${e.message}`);
    }
  }

  // If both failed, throw combined error
  throw new Error(`所有 AI 分析引擎皆不可用或呼叫失敗: ${errors.join(" | ")}`);
}

// POST /api/job/batch  — create + fire-forget, returns job_id immediately
export async function jobBatchHandler(req: Request, res: Response) {
  const stockId = String(req.body?.stock_id || "").trim();
  const requestedFrameworks: string[] = Array.isArray(req.body?.frameworks) ? req.body.frameworks : [];
  if (!/^\d{4,6}$/.test(stockId)) return res.status(400).json({ success: false, error: "股號格式錯誤 (需 4-6 位)" });

  const settings = await getDynamicSettings();
  const hasLongcat = !!settings.longcatApiKey;
  const geminiKey = process.env.GEMINI_API_KEY;
  if (!hasLongcat && !geminiKey) return res.status(500).json({ success: false, error: "未偵測到有效的 Gemini 或 LongCat API 金鑰，請先到 設定 或環境變數中配置。" });

  const validIds = Object.keys(FRAMEWORK_PROMPTS);
  const frameworks = requestedFrameworks.filter((f) => validIds.includes(f));
  const finalFrameworks = frameworks.length ? frameworks : ["goldman"];

  const job = startJob(stockId, finalFrameworks);
  res.json({
    success: true,
    job_id: job.id,
    status: job.status,
    frameworkIds: finalFrameworks,
    per_framework: job.perFramework,
  });
}

// GET /api/job/:id  — poll status + reports
export async function jobGetHandler(req: Request, res: Response) {
  const id = req.params.id;
  const job = getJob(id);
  if (!job) return res.status(404).json({ success: false, error: "job 不存在" });
  res.json({ success: true, job });
}

// GET /api/jobs?limit=20
export async function jobListHandler(_req: Request, res: Response) {
  const limit = Math.min(Number((_req as any).query?.limit) || 20, 100);
  res.json({ success: true, jobs: listJobs(limit) });
}

// POST /api/tdcc/sync  — manual TDCC fetch (best-effort Supabase)
export async function jobDeleteHandler(req: Request, res: Response) {
  const ok = deleteJob(req.params.id);
  if (!ok) return res.status(404).json({ success: false, error: "job not found" });
  res.json({ success: true });
}

export async function jobDeleteAllHandler(_req: Request, res: Response) {
  const deleted = deleteAllJobs();
  res.json({ success: true, deleted });
}

export async function tdccSyncHandler(req: Request, res: Response) {
  try {
    const r = await syncTdcc({ toSqlite: true, toSupabase: true, log: (m) => console.log("[tdcc-api]", m) });
    res.json({ success: true, count: r.count, date: r.date });
  } catch (e: any) {
    res.status(500).json({ success: false, error: e.message?.slice(0, 200) });
  }
}

// GET /api/tdcc/status  — per-stock latest TDCC date / total in SQLite
export async function tdccStatusHandler(_req: Request, res: Response) {
  res.json({ success: true, status: getTdccSqliteStatus() });
}

// 向後相容: POST /api/analysis-mvp (舊 single-framework 叫用 => 改 golden batch)
export async function mvpMcpHandler(req: Request, res: Response) {
  (req.body as any).frameworks = (req.body as any).frameworks || ["goldman"];
  return jobBatchHandler(req, res);
}
