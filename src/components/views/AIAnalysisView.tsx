import React, { useState, useEffect, useRef } from 'react';
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
  Briefcase,
  Cpu,
  Layers,
  ArrowRight,
  Copy,
  Plus,
  Minus,
  Check,
  ChevronRight,
  DatabaseZap,
  BookOpen
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

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

const STOCK_SHORTCUTS = [
  { id: '2330', name: '台積電', desc: '半導體龍頭' },
  { id: '2317', name: '鴻海', desc: '全球代工巨擘' },
  { id: '2454', name: '聯發科', desc: 'IC 設計大廠' },
  { id: '2603', name: '長榮', desc: '航運龍頭' },
  { id: '3231', name: '緯創', desc: 'AI 伺服器核心' }
];

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
  
  // Reports synthesized by Longcat/Gemini
  const [reports, setReports] = useState<{
    general: string;
    hedgeFund: string;
    industry: string;
  } | null>(null);
  
  const [activeReportTab, setActiveReportTab] = useState<'general' | 'hedgeFund' | 'industry'>('general');
  const [fontSize, setFontSize] = useState<'sm' | 'md' | 'lg' | 'xl'>('md');
  const [copied, setCopied] = useState(false);
  
  const terminalEndRef = useRef<HTMLDivElement>(null);

  // Auto scroll to latest logs
  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const runAnalysis = async (targetId?: string) => {
    const finalStockId = (targetId || stockId).trim();
    if (!finalStockId) return;
    
    setStockId(finalStockId);
    setLoading(true);
    setError(null);
    setLogs([]);
    setExtractedParams([]);
    setRawDataSummary(null);
    setReports(null);

    // Initial log to show immediate reaction
    setLogs([
      {
        timestamp: new Date().toLocaleTimeString('zh-TW', { hour12: false }),
        step: '啟動分析',
        status: 'info',
        message: `向伺服器發送股票代號 [ ${finalStockId} ] 深度反饋式分析請求...`
      }
    ]);

    try {
      const response = await fetch('/api/ai-analysis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ stockId: finalStockId }),
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
        return <span className="inline-flex items-center gap-1 text-[10px] uppercase font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full"><CheckCircle size={10} /> OK</span>;
      case 'warning':
        return <span className="inline-flex items-center gap-1 text-[10px] uppercase font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-full"><AlertTriangle size={10} /> WARN</span>;
      case 'error':
        return <span className="inline-flex items-center gap-1 text-[10px] uppercase font-mono bg-rose-500/10 text-rose-400 border border-rose-500/20 px-2 py-0.5 rounded-full"><XOctagon size={10} /> ERR</span>;
      case 'info':
      default:
        return <span className="inline-flex items-center gap-1 text-[10px] uppercase font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full animate-pulse"><Clock size={10} /> RUN</span>;
    }
  };

  // Determine current active pipeline step
  const getPipelineStatus = () => {
    if (!loading && logs.length === 0) return { activeIndex: -1, text: '等待指令' };
    if (loading) {
      const lastLog = logs[logs.length - 1];
      if (!lastLog) return { activeIndex: 0, text: '解析 DOCX 方法論' };
      const stepText = lastLog.step || '';
      if (stepText.includes('DOCX') || stepText.includes('方法論')) return { activeIndex: 0, text: '解析投資人手冊中' };
      if (stepText.includes('提取') || stepText.includes('LongCat')) return { activeIndex: 1, text: 'AI 提取模型特徵' };
      if (stepText.includes('拉取') || stepText.includes('備援') || stepText.includes('FinMind')) return { activeIndex: 2, text: '拉取 FinMind 數據倉儲' };
      if (stepText.includes('整合分析') || stepText.includes('研判') || stepText.includes('核心')) return { activeIndex: 3, text: '大模型多視角合成中' };
      return { activeIndex: 3, text: '高維數據融合分析' };
    }
    return { activeIndex: 4, text: '分析完成' };
  };

  const { activeIndex: activeStepIdx, text: pipelineStateText } = getPipelineStatus();

  // Stepper steps config
  const steps = [
    { title: '解構方法論', desc: '解析巨量 DOCX 手冊' },
    { title: 'AI 提取參數', desc: 'LongCat 推演特徵' },
    { title: '數據採集倉儲', desc: 'FinMind 即時對接' },
    { title: '多维報告合成', desc: '雙向反饋深度智庫' }
  ];

  // Font size utilities
  const fontSizeClass = {
    sm: 'text-xs md:text-sm leading-relaxed',
    md: 'text-sm md:text-base leading-relaxed',
    lg: 'text-base md:text-lg leading-relaxed font-normal',
    xl: 'text-lg md:text-xl leading-loose font-normal'
  }[fontSize];

  // Copy current report helper
  const handleCopy = () => {
    if (!reports) return;
    const currentText = activeReportTab === 'general' ? reports.general :
                       activeReportTab === 'hedgeFund' ? reports.hedgeFund :
                       reports.industry;
    navigator.clipboard.writeText(currentText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-12 px-2 sm:px-4">
      {/* ── 1. Unified Control Cockpit Card ── */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg relative overflow-hidden">
        <div className="absolute right-0 top-0 -mr-16 -mt-16 w-80 h-80 bg-blue-500/5 rounded-full blur-[100px] pointer-events-none" />
        
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
          <div className="space-y-1.5 max-w-2xl">
            <h2 className="text-xl md:text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
              <span>AI 深度反饋式投研分析控制台</span>
              <span className="text-[10px] font-mono tracking-widest px-2.5 py-0.5 bg-blue-600/10 border border-blue-500/20 text-blue-400 rounded-full font-semibold uppercase">
                Double-Loop Reasoning
              </span>
            </h2>
            <p className="text-slate-400 text-xs leading-relaxed">
              融合三大華爾街頂尖方法論：高盛基本面篩選、避險基金高級 AP/CL QoQ 資金比對、與頂尖供應鏈做空壓力模型，實時探勘 FinMind / 本地關聯式資料庫深度融合運算。
            </p>
            
            {/* Quick stock shortcuts */}
            <div className="pt-2 flex flex-wrap items-center gap-2">
              <span className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
                <BookOpen size={11} /> 快速測試股票:
              </span>
              {STOCK_SHORTCUTS.map(sc => (
                <button
                  key={sc.id}
                  disabled={loading}
                  onClick={() => runAnalysis(sc.id)}
                  className={`text-slate-300 bg-slate-800/80 hover:bg-blue-600/20 hover:text-blue-400 text-xs px-2.5 py-1 rounded-lg border border-slate-700/60 transition-all font-mono duration-150 flex items-center gap-1 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${sc.id === stockId ? 'border-blue-500/50 text-blue-400 bg-blue-500/5' : ''}`}
                >
                  <span className="font-bold">{sc.id}</span>
                  <span className="text-xs opacity-75">{sc.name}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Unified dynamic action bar */}
          <div className="bg-slate-950 border border-slate-800/80 p-1.5 rounded-xl flex items-center gap-2 w-full lg:w-auto lg:min-w-[360px] max-w-lg shadow-inner">
            <div className="relative flex-1">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                <Search size={15} />
              </div>
              <input
                type="text"
                value={stockId}
                onChange={(e) => setStockId(e.target.value)}
                placeholder="台股代碼 (如: 2330)"
                maxLength={6}
                className="w-full bg-transparent border-0 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-0 font-mono tracking-wider"
                onKeyDown={(e) => e.key === 'Enter' && runAnalysis()}
                disabled={loading}
              />
            </div>
            <button
              onClick={() => runAnalysis()}
              disabled={loading || !stockId.trim()}
              className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-md hover:shadow-blue-500/10 active:scale-[0.98] transition-all disabled:opacity-50 disabled:pointer-events-none"
            >
              <Sparkles size={14} className={loading ? 'animate-spin' : 'animate-pulse'} />
              <span>{loading ? '探勘中...' : '深度智庫分析'}</span>
            </button>
          </div>
        </div>
        
        {/* Real-time horizontal micro stepper */}
        <div className="mt-6 border-t border-slate-800/60 pt-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {steps.map((st, sIdx) => {
              const isCompeted = sIdx < activeStepIdx;
              const isActive = sIdx === activeStepIdx;
              return (
                <div 
                  key={sIdx} 
                  className={`p-2.5 rounded-xl border transition-all duration-300 ${
                    isActive 
                      ? 'bg-blue-500/5 border-blue-500/40 text-blue-400' 
                      : isCompeted 
                        ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400' 
                        : 'bg-slate-950/40 border-slate-900/60 text-slate-500'
                  }`}
                >
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-mono font-bold ${
                      isActive 
                        ? 'bg-blue-500 text-slate-950 animate-pulse' 
                        : isCompeted 
                          ? 'bg-emerald-500 text-slate-950' 
                          : 'bg-slate-900 text-slate-600'
                    }`}>
                      {isCompeted ? '✓' : sIdx + 1}
                    </span>
                    <span className="text-xs font-bold leading-none">{st.title}</span>
                  </div>
                  <p className="text-[10px] opacity-80 leading-snug truncate">{st.desc}</p>
                </div>
              );
            })}
          </div>
          
          <div className="flex items-center justify-between mt-3 px-1 text-[11px]">
            <span className="text-slate-500 flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${loading ? 'bg-blue-400 animate-ping' : 'bg-slate-600'}`} />
              管道狀態：<span className={loading ? 'text-blue-400' : 'text-slate-400'}>{pipelineStateText}</span>
            </span>
            {loading && (
              <span className="text-xs font-mono text-indigo-400">
                Agent 執行管線總耗時 {(logs.length * 90) + 120}ms...
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── 2. The Integrated Cockpit Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* Left Hand: Cyber Quantum Terminal & Telemetry Bento (4 Columns) */}
        <div className="lg:col-span-4 space-y-6 flex flex-col">
          
          {/* Cyber Terminal */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden flex flex-col shadow-lg h-[360px] lg:h-[420px]">
            <div className="px-4.5 py-3 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal size={14} className="text-blue-400" />
                <h3 className="font-bold text-xs font-mono text-slate-200 tracking-wide">
                  REASONING WORKFLOW CONSOLE
                </h3>
              </div>
              <span className="text-[9px] font-mono bg-slate-950 text-indigo-400 border border-slate-800 px-1.5 py-0.5 rounded uppercase">
                Dual Loop Log
              </span>
            </div>

            <div className="flex-1 overflow-y-auto p-3.5 space-y-2.5 font-mono text-[11px] bg-slate-950/90 leading-relaxed scrollbar-thin scrollbar-thumb-slate-800/80">
              {logs.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-600 space-y-2.5 py-16">
                  <Terminal size={32} className="opacity-30 animate-pulse text-indigo-500" />
                  <p className="text-xs font-sans font-medium">中控台閒置中</p>
                  <p className="text-[10px] font-sans opacity-70 text-center max-w-[200px]">
                    請輸入你要智庫探勘的台股代碼，點選「深度智庫分析」啟動。
                  </p>
                </div>
              ) : (
                logs.map((log, index) => (
                  <div key={index} className="bg-slate-950 border border-slate-900/80 hover:border-slate-800/60 p-2.5 rounded-lg space-y-1.5 transition-all">
                    <div className="flex items-center justify-between text-[10px]">
                      <div className="flex items-center gap-1.5 text-slate-400">
                        <span className="text-slate-600 font-bold bg-slate-900 px-1 rounded">{log.timestamp}</span>
                        <strong className="text-slate-300 font-bold font-sans">{log.step}</strong>
                      </div>
                      <div className="flex items-center gap-1">
                        {log.duration !== undefined && (
                          <span className="text-[9px] text-indigo-400 bg-slate-900 px-1 rounded">
                            +{log.duration}ms
                          </span>
                        )}
                        {getStatusBadge(log.status)}
                      </div>
                    </div>
                    <p className="text-slate-400 whitespace-pre-wrap font-sans text-[11px] leading-relaxed">
                      {log.message}
                    </p>
                  </div>
                ))
              )}
              <div ref={terminalEndRef} />
            </div>
          </div>

          {/* Raw Telemetry Bento Indicators */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4.5 space-y-4 shadow-lg">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-xs text-slate-200 flex items-center gap-2 uppercase tracking-wide font-mono">
                <DatabaseZap size={14} className="text-emerald-400" />
                Raw Telemetry Metas
              </h3>
              <span className="text-[10px] text-slate-500 font-mono">
                Data Integration
              </span>
            </div>

            {rawDataSummary ? (
              <div className="space-y-3.5">
                <div className="grid grid-cols-3 gap-2.5">
                  <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800 text-center">
                    <p className="text-slate-500 text-[9px] font-medium uppercase font-mono">資產負債表</p>
                    <p className="text-sm font-bold text-emerald-400 mt-1 font-mono">{rawDataSummary.balanceSheetCount}</p>
                    <span className="text-[8px] text-slate-500 font-mono">Records</span>
                  </div>
                  <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800 text-center">
                    <p className="text-slate-500 text-[9px] font-medium uppercase font-mono">綜合損益表</p>
                    <p className="text-sm font-bold text-emerald-400 mt-1 font-mono">{rawDataSummary.financialStatementsCount}</p>
                    <span className="text-[8px] text-slate-500 font-mono">Records</span>
                  </div>
                  <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800 text-center">
                    <p className="text-slate-500 text-[9px] font-medium uppercase font-mono">歷史 K 線價量</p>
                    <p className="text-sm font-bold text-emerald-400 mt-1 font-mono">{rawDataSummary.priceCount}</p>
                    <span className="text-[8px] text-slate-500 font-mono">Days</span>
                  </div>
                </div>

                {extractedParams.length > 0 && (
                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-3 space-y-2">
                    <div className="flex items-center justify-between text-[10px] text-blue-400">
                      <span className="font-semibold flex items-center gap-1">
                        <Layers size={11} /> 匹配目標 FinMind 資料表
                      </span>
                      <span className="font-mono text-slate-500 font-bold">JSON</span>
                    </div>
                    <pre className="text-[9px] text-slate-400 leading-normal overflow-x-auto p-2 bg-slate-900 border border-slate-800.5 rounded font-mono max-h-24">
                      {JSON.stringify(extractedParams, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ) : (
              <div className="py-8 text-center text-slate-600 flex flex-col items-center justify-center space-y-1">
                <Database size={24} className="opacity-20" />
                <p className="text-xs font-sans">無即時數據源載體</p>
                <p className="text-[10px] opacity-75">執行分析後，FinMind 原生數值將在此解構呈現</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Hand: Interactive Methodology Intelligence Hub (8 Columns) */}
        <div className="lg:col-span-8">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-lg h-[500px] lg:h-[636px] flex flex-col">
            
            {/* Header with report selector tab triggers & premium utility deck */}
            <div className="px-4 sm:px-5 pt-4 border-b border-slate-800 bg-slate-900/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0">
              <div className="flex items-center gap-1.5 pb-2 sm:pb-0">
                <FileText size={16} className="text-blue-400" />
                <h3 className="font-bold text-sm text-slate-200 tracking-tight">
                  首席研究分析師方法論報告
                </h3>
              </div>
              
              {/* Report Tab Swapper */}
              <div className="flex gap-1 overflow-x-auto -mx-4 sm:mx-0 px-2 sm:px-0">
                <button
                  onClick={() => setActiveReportTab('general')}
                  className={`px-3 py-2 text-xs font-semibold rounded-t-xl border-t border-x transition-all duration-150 flex items-center gap-1.5 cursor-pointer whitespace-nowrap shrink-0 ${
                    activeReportTab === 'general'
                      ? 'bg-slate-950 text-blue-400 border-slate-800 border-b-transparent shadow-[0_-2px_10px_rgba(59,130,246,0.05)]'
                      : 'bg-transparent text-slate-500 border-transparent hover:text-slate-300'
                  }`}
                >
                  <Building size={12} />
                  高盛基本面綜合
                </button>
                <button
                  onClick={() => setActiveReportTab('hedgeFund')}
                  className={`px-3 py-2 text-xs font-semibold rounded-t-xl border-t border-x transition-all duration-150 flex items-center gap-1.5 cursor-pointer whitespace-nowrap shrink-0 ${
                    activeReportTab === 'hedgeFund'
                      ? 'bg-slate-950 text-blue-400 border-slate-800 border-b-transparent shadow-[0_-2px_10px_rgba(59,130,246,0.05)]'
                      : 'bg-transparent text-slate-500 border-transparent hover:text-slate-300'
                  }`}
                >
                  <Briefcase size={12} />
                  避險基金核心 AP/CL
                </button>
                <button
                  onClick={() => setActiveReportTab('industry')}
                  className={`px-3 py-2 text-xs font-semibold rounded-t-xl border-t border-x transition-all duration-150 flex items-center gap-1.5 cursor-pointer whitespace-nowrap shrink-0 ${
                    activeReportTab === 'industry'
                      ? 'bg-slate-950 text-blue-400 border-slate-800 border-b-transparent shadow-[0_-2px_10px_rgba(59,130,246,0.05)]'
                      : 'bg-transparent text-slate-500 border-transparent hover:text-slate-300'
                  }`}
                >
                  <TrendingUp size={12} />
                  頂尖產業供應鏈估值
                </button>
              </div>
            </div>

            {/* Utility Bar inside Markdown Container */}
            <div className="px-5 py-2.5 bg-slate-950 border-b border-slate-900 flex items-center justify-between shrink-0">
              <span className="text-[11px] text-slate-500 font-mono tracking-wider">
                {reports ? `TARGET STOCK ID: ${stockId}` : 'EXECUTIVE COCKPIT IDLE'}
              </span>
              
              {/* Readers tool: Copier & Font adjusters */}
              <div className="flex items-center gap-3.5">
                {reports && (
                  <div className="flex items-center bg-slate-900 border border-slate-800/80 rounded-lg p-0.5 shadow-sm">
                    <button 
                      onClick={() => setFontSize(prev => prev === 'xl' ? 'lg' : prev === 'lg' ? 'md' : 'sm')}
                      disabled={fontSize === 'sm'}
                      className="p-1 text-slate-500 hover:text-white disabled:opacity-30 cursor-pointer"
                      title="減小字級"
                    >
                      <Minus size={12} />
                    </button>
                    <span className="text-[10px] font-semibold text-slate-400 px-1 font-mono">AA</span>
                    <button 
                      onClick={() => setFontSize(prev => prev === 'sm' ? 'md' : prev === 'md' ? 'lg' : 'xl')}
                      disabled={fontSize === 'xl'}
                      className="p-1 text-slate-500 hover:text-white disabled:opacity-30 cursor-pointer"
                      title="增大字級"
                    >
                      <Plus size={12} />
                    </button>
                  </div>
                )}
                
                {reports && (
                  <button
                    onClick={handleCopy}
                    className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-400 hover:text-white bg-slate-900 border border-slate-800/80 rounded-lg transition-colors cursor-pointer"
                  >
                    {copied ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                    <span>{copied ? '已復製!' : '複製報告'}</span>
                  </button>
                )}
              </div>
            </div>

            {/* Report Reading Stage */}
            <div className="flex-1 overflow-y-auto p-5 sm:p-6 bg-slate-950 scrollbar-thin scrollbar-thumb-slate-800">
              {!reports ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-600 space-y-3.5 py-24">
                  <div className="w-14 h-14 rounded-full bg-slate-900/60 border border-slate-800/60 flex items-center justify-center relative">
                    <FileText size={24} className="text-slate-500 animate-pulse" />
                    <Sparkles size={12} className="absolute top-2 right-2 text-indigo-400 animate-bounce" />
                  </div>
                  <h4 className="text-sm font-semibold text-slate-400">尚無生成報告卡</h4>
                  <p className="text-xs text-slate-500 text-center max-w-sm leading-relaxed px-4">
                    請於上方控制台輸入股票代碼並按下「深度智庫分析」，FinMind 原始結構數值將被載入，套用三大定量方法論手冊對接大模型即時推理，並拼裝成三份多維透視智庫。
                  </p>
                  
                  {/* Visual Features List helper */}
                  <div className="pt-6 grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-xl w-full">
                    <div className="bg-slate-900/40 border border-slate-800/50 p-3 rounded-xl">
                      <h5 className="text-[11px] font-bold text-slate-400 mb-1 flex items-center gap-1">
                        <Building size={11} className="text-amber-400" />
                        高盛多維基本面
                      </h5>
                      <p className="text-[10px] text-slate-500 line-clamp-2">安全邊際、成長性、營收扣抵和定價話語權綜合篩選。</p>
                    </div>
                    <div className="bg-slate-900/40 border border-slate-800/50 p-3 rounded-xl">
                      <h5 className="text-[11px] font-bold text-slate-400 mb-1 flex items-center gap-1">
                        <Briefcase size={11} className="text-indigo-400" />
                        避險基金 AP/CL
                      </h5>
                      <p className="text-[10px] text-slate-500 line-clamp-2">聚焦應付款項 AP、合約負債 CL 四季變更率與做空韌性壓力測試。</p>
                    </div>
                    <div className="bg-slate-900/40 border border-slate-800/50 p-3 rounded-xl">
                      <h5 className="text-[11px] font-bold text-slate-400 mb-1 flex items-center gap-1">
                        <TrendingUp size={11} className="text-emerald-400" />
                        產業鏈地圖三段估值
                      </h5>
                      <p className="text-[10px] text-slate-500 line-clamp-2">波特五力防禦指數配合 2026 年 EPS 預測情境自動生長合理便宜價。</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-[11px] border-b border-slate-900 pb-3 mb-2 shrink-0">
                    <span className="text-slate-500 font-mono">STOCK IDENTIFIER: {stockId}</span>
                    <span className="text-indigo-400/95 font-mono flex items-center gap-1.5 bg-indigo-500/5 border border-indigo-500/10 px-2.5 py-0.5 rounded-md">
                      <Cpu size={11} className="animate-spin" />
                      <span>AGENTS: Dual-Loop Engine</span>
                    </span>
                  </div>
                  
                  {/* Custom styled markdown container with proportional margin structure */}
                  <div className={`prose prose-invert max-w-none prose-headings:font-bold prose-headings:text-slate-100 prose-headings:tracking-tight prose-p:text-slate-300 prose-strong:text-blue-400 prose-strong:font-bold prose-li:text-slate-300 prose-ul:list-disc prose-ul:pl-5 ${fontSizeClass}`}>
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
    </div>
  );
}
