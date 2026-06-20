import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { 
  Bot, 
  Search, 
  Terminal, 
  Sparkles, 
  FileText, 
  CheckCircle, 
  AlertTriangle, 
  XOctagon, 
  Clock, 
  Database,
  Building,
  TrendingUp,
  Briefcase
} from 'lucide-react';

interface DebugLog {
  timestamp: string;
  step: string;
  status: 'success' | 'warning' | 'error' | 'info';
  message: string;
  duration?: number;
}

interface QueryParam {
  dataset: string;
  data_id: string;
  start_date: string;
  end_date?: string;
}

export function AIAnalysisView() {
  const [stockId, setStockId] = useState('2330');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<DebugLog[]>([]);
  const [extractedParams, setExtractedParams] = useState<QueryParam[]>([]);
  const [rawDataSummary, setRawDataSummary] = useState<{
    balanceSheetCount: number;
    financialStatementsCount: number;
    priceCount: number;
  } | null>(null);
  
  // Reports synthesized by Longcat
  const [reports, setReports] = useState<{
    general: string;
    hedgeFund: string;
    industry: string;
  } | null>(null);
  
  // Tab control for reports (general, hedgeFund, industry)
  const [activeReportTab, setActiveReportTab] = useState<'general' | 'hedgeFund' | 'industry'>('general');

  const runAnalysis = async () => {
    if (!stockId.trim()) return;
    setLoading(true);
    setError(null);
    setLogs([]);
    setExtractedParams([]);
    setRawDataSummary(null);
    setReports(null);

    // Initial local loading log to show immediate reaction
    setLogs([
      {
        timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
        step: '啟動分析',
        status: 'info',
        message: `向伺服器發送股票代號 [ ${stockId} ] 深度反饋式分析請求...`
      }
    ]);

    try {
      const response = await fetch('/api/ai-analysis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ stockId }),
      });

      const data = await response.json();
      
      if (data.logs) {
        setLogs(data.logs);
      }
      
      if (!response.ok || !data.success) {
        throw new Error(data.error || '分析服務發生未知錯誤，請檢查伺服器日誌。');
      }

      setExtractedParams(data.extractedParams || []);
      setRawDataSummary(data.rawDataSummary || null);
      setReports(data.reports || null);
    } catch (err: any) {
      setError(err.message || '連線伺服器失敗');
      setLogs((prev) => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
          step: '致命錯誤',
          status: 'error',
          message: err.message || '伺服器端發生未捕獲異常，流程終止。'
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: 'success' | 'warning' | 'error' | 'info') => {
    switch (status) {
      case 'success':
        return <span className="inline-flex items-center gap-1 text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full"><CheckCircle size={12} /> 成功</span>;
      case 'warning':
        return <span className="inline-flex items-center gap-1 text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-full"><AlertTriangle size={12} /> 警告</span>;
      case 'error':
        return <span className="inline-flex items-center gap-1 text-xs bg-rose-500/10 text-rose-400 border border-rose-500/20 px-2 py-0.5 rounded-full"><XOctagon size={12} /> 錯誤</span>;
      case 'info':
      default:
        return <span className="inline-flex items-center gap-1 text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full"><Clock size={12} /> 執行</span>;
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-20">
      {/* Upper header */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm relative overflow-hidden">
        <div className="absolute right-0 top-0 -mr-16 -mt-16 w-64 h-64 bg-blue-500/5 rounded-full blur-3xl pointer-events-none"></div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-indigo-500/10 text-indigo-400 rounded-lg border border-indigo-500/20 shadow-inner">
              <Bot size={28} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                AI 深度方法論與反饋式分析
                <span className="text-xs font-mono font-normal tracking-wide px-2 py-0.5 bg-blue-500/10 border border-blue-500/30 text-blue-400 rounded">
                  Double-Loop Agent
                </span>
              </h2>
              <p className="text-slate-400 text-xs mt-1">
                基於高盛分析師彙總指標、頂尖產業供應鏈生命週期模型、與美式避險基金應收/合約負債精確比對等三大方法論手冊，實時打通 FinMind 原始數據。
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2 min-w-[280px]">
            <div className="relative flex-1">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                <Search size={16} />
              </div>
              <input
                type="text"
                value={stockId}
                onChange={(e) => setStockId(e.target.value)}
                placeholder="輸入台股代碼 (如: 2330)"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
                onKeyDown={(e) => e.key === 'Enter' && runAnalysis()}
              />
            </div>
            <button
              onClick={runAnalysis}
              disabled={loading}
              className={`px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-sm transition-all shadow-blue-900/10 active:scale-95 disabled:opacity-50 disabled:pointer-events-none disabled:transform-none`}
            >
              <Sparkles size={16} { ...loading ? { className: 'animate-spin' } : {} } />
              {loading ? '分析中...' : '進行深度分析'}
            </button>
          </div>
        </div>
      </div>

      {/* Main split dashboard panel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        
        {/* Left Side: Debug & Flow Logs Console */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col h-[750px]">
          <div className="px-5 py-4 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Terminal size={18} className="text-blue-400" />
              <div>
                <h3 className="font-bold text-sm text-slate-200">⚙️ 執行管線與實時 Debug 控制台</h3>
                <p className="text-slate-500 text-[11px]">雙層反饋工作流：解構方法論 ➔ 提取參數 ➔ 拉取 Raw Data ➔ 最終合成</p>
              </div>
            </div>
            {loading && <span className="inline-flex h-2 w-2 rounded-full bg-blue-400 animate-ping"></span>}
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-xs scrollbar-thin scrollbar-thumb-slate-800">
            {logs.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-600 space-y-2 py-20">
                <Terminal size={32} className="opacity-40 animate-pulse text-slate-500" />
                <p className="text-[11px] font-sans">控制台目前無任何活動日誌</p>
                <p className="text-[10px] font-sans opacity-70">請輸入你要探勘的台股代碼，並啟動分析。</p>
              </div>
            ) : (
              logs.map((log, index) => (
                <div key={index} className="bg-slate-950 border border-slate-900 rounded-lg p-3 space-y-2 shadow-sm hover:border-slate-800 transition-all">
                  <div className="flex items-center justify-between text-[11px]">
                    <div className="flex items-center gap-2 text-slate-400">
                      <span className="text-slate-600 bg-slate-900 px-1 py-0.5 rounded font-bold">{log.timestamp}</span>
                      <strong className="text-slate-200 font-semibold font-sans">{log.step}</strong>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {log.duration !== undefined && (
                        <span className="text-[10px] text-indigo-400 font-bold bg-indigo-500/5 px-1.5 py-0.2 rounded border border-indigo-500/10">
                          +{log.duration}ms
                        </span>
                      )}
                      {getStatusBadge(log.status)}
                    </div>
                  </div>
                  <p className="text-slate-300 whitespace-pre-wrap font-sans leading-relaxed text-xs">
                    {log.message}
                  </p>
                </div>
              ))
            )}

            {/* If parameters are extracted, output them beautifully */}
            {extractedParams.length > 0 && (
              <div className="bg-blue-950/15 border border-blue-950/40 rounded-lg p-3 space-y-2">
                <div className="flex items-center gap-1.5 text-blue-400 text-[11px]">
                  <Database size={13} />
                  <span className="font-semibold font-sans">Longcat 已提取並匹配之 FinMind 資料集</span>
                </div>
                <pre className="text-[10px] text-blue-300/80 leading-relaxed overflow-x-auto bg-slate-950 p-2.5 rounded border border-blue-950/20 max-h-40">
                  {JSON.stringify(extractedParams, null, 2)}
                </pre>
              </div>
            )}

            {/* Show Raw Data counts if available */}
            {rawDataSummary && (
              <div className="bg-emerald-950/15 border border-emerald-950/40 rounded-lg p-3 space-y-2">
                <div className="flex items-center gap-1.5 text-emerald-400 text-[11px]">
                  <CheckCircle size={13} />
                  <span className="font-semibold font-sans">FinMind 資料中心 API 回傳纯數據計數</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-[10px] text-slate-300 font-sans">
                  <div className="bg-slate-950 p-2 rounded border border-emerald-950/20 text-center">
                    <p className="text-slate-500 text-[9px] uppercase">資產負債表</p>
                    <p className="text-xs font-bold text-emerald-400 mt-1">{rawDataSummary.balanceSheetCount} 筆</p>
                  </div>
                  <div className="bg-slate-950 p-2 rounded border border-emerald-950/20 text-center">
                    <p className="text-slate-500 text-[9px] uppercase">綜合損益表</p>
                    <p className="text-xs font-bold text-emerald-400 mt-1">{rawDataSummary.financialStatementsCount} 筆</p>
                  </div>
                  <div className="bg-slate-950 p-2 rounded border border-emerald-950/20 text-center">
                    <p className="text-slate-500 text-[9px] uppercase">股價日均 K</p>
                    <p className="text-xs font-bold text-emerald-400 mt-1">{rawDataSummary.priceCount} 筆</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Methodology Reports Viewer */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden h-[750px] flex flex-col">
          {/* Header tabs */}
          <div className="px-5 pt-4 pb-0 border-b border-slate-800 bg-slate-900/50">
            <h3 className="font-bold text-sm text-slate-200 mb-3 flex items-center gap-1.5">
              <FileText size={18} className="text-indigo-400" />
              方法論主題報告合成 (雙向點擊即時渲染)
            </h3>
            
            <div className="flex gap-1.5">
              <button
                onClick={() => setActiveReportTab('general')}
                className={`px-3 py-2 text-xs font-medium rounded-t-lg border-t border-x transition-colors flex items-center gap-1.5 ${
                  activeReportTab === 'general'
                    ? 'bg-slate-950 text-blue-400 border-slate-800 border-b-transparent'
                    : 'bg-transparent text-slate-500 border-transparent hover:text-slate-300 hover:bg-slate-800/10'
                }`}
              >
                <Building size={13} />
                高盛綜合分析
              </button>
              <button
                onClick={() => setActiveReportTab('hedgeFund')}
                className={`px-3 py-2 text-xs font-medium rounded-t-lg border-t border-x transition-colors flex items-center gap-1.5 ${
                  activeReportTab === 'hedgeFund'
                    ? 'bg-slate-950 text-blue-400 border-slate-800 border-b-transparent'
                    : 'bg-transparent text-slate-500 border-transparent hover:text-slate-300 hover:bg-slate-800/10'
                }`}
              >
                <Briefcase size={13} />
                避險基金高級財務
              </button>
              <button
                onClick={() => setActiveReportTab('industry')}
                className={`px-3 py-2 text-xs font-medium rounded-t-lg border-t border-x transition-colors flex items-center gap-1.5 ${
                  activeReportTab === 'industry'
                    ? 'bg-slate-950 text-blue-400 border-slate-800 border-b-transparent'
                    : 'bg-transparent text-slate-500 border-transparent hover:text-slate-300 hover:bg-slate-800/10'
                }`}
              >
                <TrendingUp size={13} />
                頂尖產業與估值
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-6 bg-slate-950 scrollbar-thin scrollbar-thumb-slate-800">
            {!reports ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-600 space-y-2 py-40">
                <FileText size={40} className="text-slate-700 animate-pulse" />
                <p className="text-sm font-semibold text-slate-500">尚無生成報告</p>
                <p className="text-xs text-slate-600 text-center max-w-sm">
                  進行分析後，FinMind 的真實純數值將套用三個分析師方法論手冊。隨後，報告將自動比對生成，您可在此進行切換及檢視。
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-xs border-b border-slate-900 pb-3 mb-4">
                  <span className="text-slate-500">專屬代碼：{stockId}</span>
                  <span className="text-indigo-400/90 font-mono flex items-center gap-1 bg-indigo-500/5 border border-indigo-500/10 px-2 py-0.5 rounded">
                    生成核心：Longcat gpt-4o
                  </span>
                </div>
                
                {/* Embedded custom styling for beautiful rendering of ReactMarkdown */}
                <div className="prose prose-invert prose-sm max-w-none prose-headings:font-bold prose-headings:text-slate-100 prose-p:text-slate-300 prose-p:leading-relaxed prose-strong:text-blue-400 prose-li:text-slate-300 prose-ul:list-disc prose-ul:pl-5">
                  <ReactMarkdown>
                    {activeReportTab === 'general' ? reports.general :
                     activeReportTab === 'hedgeFund' ? reports.hedgeFund :
                     reports.industry}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
