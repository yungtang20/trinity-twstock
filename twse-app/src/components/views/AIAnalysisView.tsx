import React, { useState, useCallback } from 'react';
import { Brain, Play, Loader2, Database, AlertCircle, TrendingUp, BarChart3, PieChart, Target, Layers, Banknote, Building2, Briefcase, Sparkles, CheckCircle, RefreshCw } from "lucide-react";
import { runAIAnalysis, fetchFinMindData, FinMindQueryParams } from "../../lib/ai-api";
import { ErrorAlert } from '../ui/ErrorAlert';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import { useRetry } from '../../hooks/useRetry';

interface PromptTemplate {
  id: string;
  name: string;
  icon: React.ElementType;
  color: string;
  prompt: string;
  datasets: string[];
  needsInput?: boolean;
}

const PROMPT_TEMPLATES: PromptTemplate[] = [
  {
    id: 'gs',
    name: '高盛基本面分析篩選器',
    icon: Building2,
    color: 'text-blue-400',
    prompt: `你是高盛資深分析師。請使用以下數據，進行基本面分析篩選：1) 營收成長率 2) 利潤率趨勢 3) ROE/ROIC 4) 自由現金流 5) 估值水準（P/E、EV/EBITDA）6) 投資建議。只基於數據分析，不編造內容。若數據不足，回答「無數據」。`,
    datasets: ['TaiwanStockPrice', 'TaiwanStockFinancialStatements', 'TaiwanStockMonthRevenue', 'TaiwanStockPER'],
  },
  {
    id: 'ms',
    name: '摩根士丹利技術分析儀表板',
    icon: TrendingUp,
    color: 'text-emerald-400',
    prompt: `你是摩根士丹利技術分析師。請使用以下數據，生成技術分析儀表板：1) 均線趨勢（MA5/25/60/200）2) 支撐/壓力位 3) RSI/MACD 4) 成交量分析 5) 停損/停利建議 6) 交易計畫。只基於數據分析，不編造內容。若數據不足，回答「無數據」。`,
    datasets: ['TaiwanStockPrice', 'TaiwanStockDayTrading', 'TaiwanStockMarginPurchaseShortSale'],
  },
  {
    id: 'br',
    name: '橋水風險評估備忘錄',
    icon: AlertCircle,
    color: 'text-rose-400',
    prompt: `你是橋水基金風險分析師。請使用以下數據，生成風險評估備忘錄：1) 系統性風險評估 2) 個股波動度 3) 相關性分析 4) 最大回撤風險 5) 避險建議。先說怎麼輸，再談怎麼贏。只基於數據分析，不編造內容。若數據不足，回答「無數據」。`,
    datasets: ['TaiwanStockPrice', 'TaiwanStockShareholding', 'TaiwanStockInstitutionalInvestorsBuySell'],
  },
  {
    id: 'jpm',
    name: '摩根大通財報分析器',
    icon: Banknote,
    color: 'text-purple-400',
    prompt: `你是摩根大通財報分析師。請使用以下數據，進行財報分析：1) 損益表分析 2) 資產負債表分析 3) 現金流量表分析 4) 關鍵比率 5) 財報前後比較 6) 投資建議。只基於數據分析，不編造內容。若數據不足，回答「無數據」。`,
    datasets: ['TaiwanStockPrice', 'TaiwanStockFinancialStatements', 'TaiwanStockMonthRevenue', 'TaiwanStockDividend'],
  },
  {
    id: 'wallstreet',
    name: '華爾街分析師',
    icon: Sparkles,
    color: 'text-pink-400',
    prompt: `你是資深華爾街分析師。請使用以下數據，生成完整分析報告：1) 公司簡介 2) 財務概況 3) 技術面 4) 籌碼面 5) 基本面 6) 投資建議（買進/持有/賣出）。只基於數據分析，不編造內容。若數據不足，回答「無數據」。`,
    datasets: ['TaiwanStockPrice', 'TaiwanStockFinancialStatements', 'TaiwanStockInstitutionalInvestorsBuySell', 'TaiwanStockShareholding', 'TaiwanStockPER'],
  },
  {
    id: 'cw',
    name: '城堡行業輪動策略師',
    icon: Target,
    color: 'text-orange-400',
    prompt: '你是城堡投資行業輪動策略師。請使用以下數據，分析現在該買哪個板塊：1) 行業輪動趨勢 2) 各板塊表現 3) 資金流向 4) 技術面 5) 推薦板塊。現在該買哪個板塊？只基於數據分析，不編造內容。若數據不足，回答「無數據」。',
    datasets: ['TaiwanStockPrice', 'TaiwanStockInstitutionalInvestorsBuySell'],
  },
];

type AnalysisPhase = 'idle' | 'collecting' | 'generating' | 'complete';

interface AnalysisLog {
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'error' | 'data';
}

export function AIAnalysisView() {
  const [stockId, setStockId] = useState('2330');
  const [phase, setPhase] = useState<AnalysisPhase>('idle');
  const [currentStep, setCurrentStep] = useState(0);
  const [totalSteps, setTotalSteps] = useState(0);
  const [logs, setLogs] = useState<AnalysisLog[]>([]);
  const [results, setResults] = useState<Record<string, string>>({});
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null);
  const [rawData, setRawData] = useState<any[] | null>(null);
  const [showRawData, setShowRawData] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorDetails, setErrorDetails] = useState<string | null>(null);

  const addLog = useCallback((message: string, type: AnalysisLog['type'] = 'info') => {
    setLogs(prev => [...prev, { timestamp: new Date().toLocaleTimeString(), message, type }]);
  }, []);

  const collectFinMindData = useCallback(async (datasets: string[], stock: string) => {
    const allData: any[] = [];
    for (const ds of datasets) {
      try {
        const params: FinMindQueryParams = {
          dataset: ds,
          data_id: stock,
          start_date: '2015-01-01',
          end_date: new Date().toISOString().split('T')[0],
        };
        const result = await fetchFinMindData(params);
        if (result?.data?.length > 0) {
          allData.push({ dataset: ds, data: result.data });
          addLog(`[✓] ${ds}: ${result.data.length} 筆`, 'success');
        } else {
          addLog(`[○] ${ds}: 無數據`, 'info');
        }
      } catch (e: any) {
        addLog(`[✗] ${ds} 調閱失敗: ${e.message}`, 'error');
      }
    }
    return allData;
  }, [addLog]);

  const generateReport = useCallback(async (template: PromptTemplate, data: any[], stock: string) => {
    const prompt = `${template.prompt}\n\n股票代號：${stock}\n\n可用數據：\n${JSON.stringify(data, null, 2)}\n\n只接受數據分析，不編造內容。若數據不足，回答「無數據」。`;
    const result = await runAIAnalysis(stock, prompt);
    return result.report || '無數據';
  }, []);

  const handleRun = useCallback(async (template: PromptTemplate) => {
    if (!stockId.trim()) {
      setError('請輸入股票代號');
      return;
    }

    setSelectedPrompt(template.id);
    setPhase('collecting');
    setError(null);
    setErrorDetails(null);
    setLogs([]);
    setCurrentStep(0);
    setTotalSteps(0);

    try {
      addLog(`[開始] ${template.name}...`, 'info');
      const data = await collectFinMindData(template.datasets, stockId.trim());
      setRawData(data);

      if (data.length === 0) {
        setResults(prev => ({ ...prev, [template.id]: '無數據' }));
        addLog(`[完成] 無數據`, 'info');
        setPhase('complete');
        return;
      }

      setPhase('generating');
      setCurrentStep(1);
      setTotalSteps(1);
      addLog(`[報告] LongCat 生成報告...`, 'info');

      const report = await generateReport(template, data, stockId.trim());
      setResults(prev => ({ ...prev, [template.id]: report }));

      addLog(`[完成] ${template.name} 報告生成完成`, 'success');
      setPhase('complete');
    } catch (err: any) {
      const errorMessage = err.message || '分析過程發生錯誤';
      addLog(`[錯誤] ${errorMessage}`, 'error');
      setError(errorMessage);
      setErrorDetails(`模板: ${template.name}\n股票: ${stockId}\n錯誤: ${errorMessage}`);
      setPhase('idle');
    }
  }, [stockId, collectFinMindData, generateReport, addLog]);

  const {
    execute: handleRunWithRetry,
    retry: retryAnalysis
  } = useRetry(
    () => {
      const template = PROMPT_TEMPLATES.find(t => t.id === selectedPrompt);
      if (!template) return Promise.reject(new Error('未選擇模板'));
      return handleRun(template);
    },
    {
      maxRetries: 2,
      baseDelay: 3000,
      shouldRetry: (error) => {
        if (error.message.includes('請輸入')) return false;
        if (error.message.includes('無數據')) return false;
        return true;
      },
    }
  );

  const handleRunAll = useCallback(async () => {
    if (!stockId.trim()) {
      setError('請輸入股票代號');
      return;
    }

    setPhase('collecting');
    setError(null);
    setErrorDetails(null);
    setLogs([]);
    setResults({});
    setTotalSteps(PROMPT_TEMPLATES.length);

    addLog(`[開始] 批量分析 ${PROMPT_TEMPLATES.length} 份報告...`, 'info');

    try {
      const allDatasets = [...new Set(PROMPT_TEMPLATES.flatMap(t => t.datasets))];
      addLog(`[資料] 從 FinMind 調取 ${allDatasets.length} 個數據集...`, 'info');
      const data = await collectFinMindData(allDatasets, stockId.trim());
      setRawData(data);

      if (data.length === 0) {
        addLog(`[完成] 無數據`, 'info');
        setPhase('complete');
        return;
      }

      setPhase('generating');
      for (let i = 0; i < PROMPT_TEMPLATES.length; i++) {
        const template = PROMPT_TEMPLATES[i];
        setCurrentStep(i + 1);
        addLog(`[報告] ${template.name} (${i + 1}/${PROMPT_TEMPLATES.length})...`, 'info');

        try {
          const report = await generateReport(template, data, stockId.trim());
          setResults(prev => ({ ...prev, [template.id]: report }));
          addLog(`[✓] ${template.name} 完成`, 'success');
        } catch (err: any) {
          addLog(`[✗] ${template.name} 失敗: ${err.message}`, 'error');
          setResults(prev => ({ ...prev, [template.id]: '生成失敗' }));
        }
      }

      addLog(`[完成] 已生成 ${Object.keys(results).length} 份報告`, 'success');
      setPhase('complete');
    } catch (err: any) {
      const errorMessage = err.message || '批量分析過程發生錯誤';
      addLog(`[錯誤] ${errorMessage}`, 'error');
      setError(errorMessage);
      setErrorDetails(`股票: ${stockId}\n錯誤: ${errorMessage}`);
      setPhase('idle');
    }
  }, [stockId, collectFinMindData, generateReport, addLog, results]);

  const {
    execute: handleRunAllWithRetry,
    retry: retryBatchAnalysis
  } = useRetry(handleRunAll, {
    maxRetries: 2,
    baseDelay: 5000,
    shouldRetry: (error) => {
      if (error.message.includes('請輸入')) return false;
      return true;
    },
  });

  const clearError = useCallback(() => {
    setError(null);
    setErrorDetails(null);
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3 bg-slate-950 border border-white/[0.06] rounded-2xl px-5 py-3">
        <Brain className="text-purple-400" size={20} />
        <h1 className="text-lg font-bold text-white">AI 智能分析</h1>
        <span className="text-[10px] bg-emerald-500/15 text-emerald-400 px-2 py-0.5 rounded-full font-bold flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />FinMind
        </span>
      </div>

      {error && (
        <ErrorAlert
          type="error"
          title="分析過程發生錯誤"
          message={error}
          details={errorDetails || undefined}
          onRetry={retryAnalysis}
          showRetry={!error.includes('請輸入')}
          onDismiss={clearError}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
        <div className="bg-slate-950 border border-white/[0.06] rounded-2xl p-4 space-y-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold text-white">分析模板</h2>
            <button
              onClick={handleRunAllWithRetry}
              disabled={phase === 'collecting' || phase === 'generating'}
              className="px-3 py-1 bg-purple-600 hover:bg-purple-500 text-white text-xs rounded-lg transition-all flex items-center gap-1 disabled:opacity-50"
            >
              {phase === 'collecting' || phase === 'generating' ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Play size={12} />
              )}
              全部執行
            </button>
          </div>

          <div className="mb-3">
            <label className="block text-xs text-slate-400 mb-1">股票代號 / 股名</label>
            <input
              type="text"
              value={stockId}
              onChange={(e) => setStockId(e.target.value)}
              placeholder="例如: 2330"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-purple-500 font-mono"
            />
          </div>

          <div className="mb-3 bg-slate-900/50 border border-slate-800 rounded-lg p-3">
            <h4 className="text-[10px] font-bold text-slate-300 mb-2">📊 數據收集策略</h4>
            <div className="text-[10px] text-slate-500 space-y-1">
              <p>• <span className="text-cyan-400">FinMind</span>：6 個免費數據集</p>
              <p>• <span className="text-purple-400">LongCat</span>：max_tokens = 128,000</p>
              <p>• 日期範圍：2015-01-01 至今日</p>
            </div>
          </div>

          <div className="space-y-1 max-h-[400px] overflow-y-auto">
            {PROMPT_TEMPLATES.map(template => (
              <button
                key={template.id}
                onClick={() => handleRunWithRetry()}
                disabled={phase === 'collecting' || phase === 'generating'}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-left transition-all border ${
                  selectedPrompt === template.id
                    ? 'bg-purple-500/15 border-purple-500/30 text-white'
                    : 'bg-slate-900/50 border-slate-800 text-slate-300 hover:bg-slate-800/50'
                } disabled:opacity-50`}
              >
                <template.icon size={16} className={selectedPrompt === template.id ? template.color : 'text-slate-500'} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium truncate">{template.name}</div>
                  <div className="text-[10px] text-slate-500 truncate">{template.datasets.join(', ')}</div>
                </div>
                {results[template.id] && (
                  <CheckCircle size={12} className={results[template.id] === '生成失敗' ? 'text-red-500' : 'text-emerald-500'} />
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="bg-slate-950 border border-white/[0.06] rounded-2xl p-4">
          {selectedPrompt && !results[selectedPrompt] && phase === 'idle' && (
            <button
              onClick={() => {
                const template = PROMPT_TEMPLATES.find(t => t.id === selectedPrompt);
                if (template) handleRunWithRetry();
              }}
              className="w-full px-6 py-3 bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-xl transition-colors flex items-center justify-center gap-2 mb-4"
            >
              <Play size={16} /> 開始分析
            </button>
          )}

          {(phase === 'collecting' || phase === 'generating') && (
            <div className="flex items-center justify-center py-16 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin mr-3" />
              <span>{phase === 'collecting' ? '從 FinMind 調取數據...' : 'LongCat 生成報告...'} ({currentStep}/{totalSteps})</span>
            </div>
          )}

          {Object.keys(results).length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white">分析結果</h3>
                <button
                  onClick={() => setShowRawData(!showRawData)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${showRawData ? 'bg-cyan-500/20 text-cyan-400' : 'bg-slate-800 text-slate-400'}`}
                >
                  {showRawData ? '隱藏原始數據' : '查看原始數據'}
                </button>
              </div>

              {showRawData && rawData && rawData.length > 0 && (
                <div className="bg-slate-900 rounded-lg p-3 space-y-2">
                  <h4 className="text-xs font-medium text-slate-300">數據來源</h4>
                  {rawData.map((d, idx) => (
                    <div key={idx} className="flex items-center justify-between bg-slate-800 rounded px-2 py-1">
                      <span className="text-xs text-emerald-400">FinMind: {d.dataset}</span>
                      <span className="text-[10px] text-slate-500">{d.data.length} 筆</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="space-y-3 max-h-[500px] overflow-y-auto">
                {PROMPT_TEMPLATES.filter(t => results[t.id]).map(template => (
                  <div key={template.id} className="bg-slate-900 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <template.icon size={16} className={template.color} />
                      <h4 className="text-sm font-bold text-white">{template.name}</h4>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                        results[template.id] === '生成失敗'
                          ? 'bg-red-500/15 text-red-400'
                          : results[template.id] === '無數據'
                          ? 'bg-amber-500/15 text-amber-400'
                          : 'bg-emerald-500/15 text-emerald-400'
                      }`}>
                        {results[template.id] === '生成失敗' ? '失敗' : results[template.id] === '無數據' ? '無數據' : '完成'}
                      </span>
                    </div>
                    <div className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
                      {results[template.id]}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {Object.keys(results).length === 0 && phase === 'idle' && !error && (
            <div className="flex flex-col items-center justify-center py-16 text-slate-500">
              <Brain size={48} className="mb-4 opacity-30" />
              <p className="text-sm">選擇左側模板，開始 AI 分析</p>
              <p className="text-xs mt-1">所有數據將從 FinMind 即時抓取</p>
            </div>
          )}
        </div>
      </div>

      {logs.length > 0 && (
        <div className="bg-slate-950 border border-white/[0.06] rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Database className="text-cyan-400" size={16} />
            <h3 className="text-sm font-bold text-white">執行過程</h3>
          </div>
          <div className="bg-slate-900 rounded-lg p-3 font-mono text-xs max-h-48 overflow-y-auto space-y-1">
            {logs.map((log, idx) => (
              <div key={idx} className={`${
                log.type === 'success' ? 'text-emerald-400' :
                log.type === 'error' ? 'text-red-400' :
                log.type === 'data' ? 'text-cyan-400' :
                'text-slate-400'
              }`}>
                <span className="text-slate-500">[{log.timestamp}]</span> {log.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
