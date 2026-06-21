import React, { useState, useEffect, useRef } from 'react';
import { 
  Database, RefreshCw, Server, Shield, CheckCircle2, AlertCircle, Key, Eye, EyeOff, Save, 
  Upload, Calendar, ArrowRight, Table, FileText, Check, AlertTriangle, FileUp
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

export function SettingsView() {
  const [activeTab, setActiveTab] = useState<'general' | 'finmind' | 'tdcc'>('general');

  // API 金鑰與 Webhook
  const [webhookUrl, setWebhookUrl] = useState('');
  const [finmindApiKey, setFinmindApiKey] = useState('');
  const [longcatApiKey, setLongcatApiKey] = useState('');
  const [longcatBaseUrl, setLongcatBaseUrl] = useState('');
  const [longcatModel, setLongcatModel] = useState('');

  const [showFinmind, setShowFinmind] = useState(false);
  const [showLongcat, setShowLongcat] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');

  // 資料庫同步
  const [isUpdating, setIsUpdating] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>('載入中...');
  const [updateStatus, setUpdateStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [dbConnected, setDbConnected] = useState(false);

  // API 區塊折疊狀態
  const [isApiCollapsed, setIsApiCollapsed] = useState(true);

  // 實時爬取同步日誌跟狀態
  const [syncLogs, setSyncLogs] = useState<string[]>([]);
  const [syncRunning, setSyncRunning] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncStartTime, setSyncStartTime] = useState<string | null>(null);
  const syncLogsEndRef = useRef<HTMLDivElement>(null);

  // FinMind 歷史數據回補欄位
  const [backfillStockId, setBackfillStockId] = useState('2330');
  const [backfillStartDate, setBackfillStartDate] = useState('2026-01-01');
  const [backfillEndDate, setBackfillEndDate] = useState('');
  const [backfillPrice, setBackfillPrice] = useState(true);
  const [backfillInstitutional, setBackfillInstitutional] = useState(true);
  const [isBackfilling, setIsBackfilling] = useState(false);
  const [backfillLogs, setBackfillLogs] = useState<string[]>([]);
  const [backfillStatus, setBackfillStatus] = useState<'idle' | 'success' | 'error'>('idle');

  // TDCC 股權分散表上傳
  const [isDragging, setIsDragging] = useState(false);
  const [uploadingTdcc, setUploadingTdcc] = useState(false);
  const [autoFetchingTdcc, setAutoFetchingTdcc] = useState(false);
  const [tdccFile, setTdccFile] = useState<File | null>(null);
  const [tdccUploadedCount, setTdccUploadedCount] = useState<number | null>(null);
  const [tdccInsertedCount, setTdccInsertedCount] = useState<number | null>(null);
  const [tdccStatus, setTdccStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [tdccError, setTdccError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // 每當有新日誌，自動捲動到底部
  useEffect(() => {
    if (syncLogsEndRef.current) {
      syncLogsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [syncLogs]);

  useEffect(() => {
    fetchRealDatabaseStatus();
    fetchCurrentSettings();
    fetchSyncStatus(); // 初始抓取一下是否正有行程在同步
  }, []);

  // 定期輪詢爬蟲明細日誌的效應
  useEffect(() => {
    let intervalId: any = null;

    if (syncRunning) {
      intervalId = setInterval(async () => {
        const isStillRunning = await fetchSyncStatus();
        if (!isStillRunning) {
          clearInterval(intervalId);
          fetchRealDatabaseStatus(); // 完成後更新最後時間
        }
      }, 1500);
    } else {
      // 若尚未運行，可放著不做，或定時低頻率偵測
      intervalId = setInterval(() => {
        fetchSyncStatus();
      }, 8000);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [syncRunning]);

  const fetchSyncStatus = async (): Promise<boolean> => {
    try {
      const res = await fetch('/api/sync-status');
      if (res.ok) {
        const data = await res.json();
        setSyncRunning(data.running);
        setSyncLogs(data.logs || []);
        setSyncStartTime(data.startTime);
        setSyncError(data.error);
        return data.running as boolean;
      }
    } catch (e) {
      console.error('輪詢更新日誌錯誤碼:', e);
    }
    return false;
  };

  const fetchRealDatabaseStatus = async () => {
    try {
      const res = await fetch('/api/debug-status');
      if (!res.ok) throw new Error('後端無回應');
      const data = await res.json();
      setDbConnected(data.dbConnected || false);
      setLastUpdated(data.dbConnected ? 'SQLite 已連線 (taiwan_stock_unified.db)' : '後端未連線');
    } catch (error: any) {
      console.error('Fetch status error:', error);
      setDbConnected(false);
      setLastUpdated(`後端無回應: ${error.message || '未知錯誤'}`);
    }
  };

  const fetchCurrentSettings = async () => {
    try {
      const res = await fetch('/api/settings');
      if (res.ok) {
        const data = await res.json();
        setWebhookUrl(data.webhookUrl || '');
        setFinmindApiKey(data.finmindApiKey || '');
        setLongcatApiKey(data.longcatApiKey || '');
        setLongcatBaseUrl(data.longcatBaseUrl || '');
        setLongcatModel(data.longcatModel || '');
      }
    } catch (error) {
      console.error('Fetch settings error:', error);
    }
  };

  const handleManualUpdate = async () => {
    setIsUpdating(true);
    setUpdateStatus('idle');
    setSyncError(null);
    setSyncRunning(true); // 立即觸發輪詢
    
    try {
      const res = await fetch('/api/trigger-update', { method: 'POST' });
      if (!res.ok) {
        throw new Error('觸發服務器同步 API 失敗');
      }

      const data = await res.json();
      if (data.success) {
        setUpdateStatus('success');
        await fetchSyncStatus();
      } else {
        throw new Error(data.message || '背景爬蟲對接啟動失敗');
      }
    } catch (error: any) {
      console.error('Update failed:', error);
      setUpdateStatus('error');
      setSyncError(error.message || '網路呼叫異常');
      setSyncRunning(false);
    } finally {
      setIsUpdating(false);
      setTimeout(() => setUpdateStatus('idle'), 3000);
    }
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSaveStatus('idle');

    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          webhookUrl,
          finmindApiKey,
          longcatApiKey,
          longcatBaseUrl,
          longcatModel
        })
      });

      if (!res.ok) throw new Error('儲存設定失敗');
      
      setSaveStatus('success');
      await fetchRealDatabaseStatus();
    } catch (error) {
      console.error('Save settings failed:', error);
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
      setTimeout(() => setSaveStatus('idle'), 3000);
    }
  };

  // 處理 FinMind 回補
  const handleFinMindBackfill = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!backfillStockId.trim()) return;
    
    setIsBackfilling(true);
    setBackfillStatus('idle');
    setBackfillLogs(['[系統] 連線至回補引擎中...', '[系統] 正在發送 FinMind 回補請求...']);

    const types = [];
    if (backfillPrice) types.push('price');
    if (backfillInstitutional) types.push('institutional');

    try {
      const res = await fetch('/api/backfill-finmind', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          stockId: backfillStockId.trim(),
          startDate: backfillStartDate,
          endDate: backfillEndDate || undefined,
          types
        })
      });

      const data = await res.json();
      if (data.logs) {
        setBackfillLogs(data.logs);
      }

      if (data.success) {
        setBackfillStatus('success');
      } else {
        setBackfillStatus('error');
        if (data.error) {
          setBackfillLogs(prev => [...prev, `❌ 失敗原因: ${data.error}`]);
        }
      }
    } catch (error: any) {
      console.error('Backfill failed:', error);
      setBackfillStatus('error');
      setBackfillLogs(prev => [...prev, `❌ 發送請求失敗: ${error.message}`]);
    } finally {
      setIsBackfilling(false);
    }
  };

  // TDCC 拖曳與上傳處理
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith('.csv') || file.type === 'text/csv') {
        setTdccFile(file);
        setTdccStatus('idle');
        setTdccError(null);
      } else {
        setTdccError('請提供有效的 CSV 股權分散表檔案！');
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      setTdccFile(file);
      setTdccStatus('idle');
      setTdccError(null);
    }
  };

  const handleTdccUpload = async () => {
    if (!tdccFile) return;

    setUploadingTdcc(true);
    setTdccStatus('idle');
    setTdccError(null);

    try {
      const reader = new FileReader();
      reader.onload = async (event) => {
        const csvText = event.target?.result as string;
        try {
          const res = await fetch('/api/upload-tdcc', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ csvText })
          });

          const data = await res.json();
          if (res.ok && data.success) {
            setTdccUploadedCount(data.parsedCount);
            setTdccInsertedCount(data.insertedRecords);
            setTdccStatus('success');
            setTdccFile(null);
          } else {
            throw new Error(data.error || '解析 CSV 失敗');
          }
        } catch (postErr: any) {
          setTdccError(postErr.message || '上傳與解析檔案時發生錯誤');
          setTdccStatus('error');
        } finally {
          setUploadingTdcc(false);
        }
      };

      reader.onerror = () => {
        setTdccError('讀取本地檔案時失敗！');
        setTdccStatus('error');
        setUploadingTdcc(false);
      };

      reader.readAsText(tdccFile);
    } catch (err: any) {
      setTdccError(err.message || '檔案解析流程失敗');
      setTdccStatus('error');
      setUploadingTdcc(false);
    }
  };

  const handleTdccAutoFetch = async () => {
    setAutoFetchingTdcc(true);
    setTdccStatus('idle');
    setTdccError(null);
    try {
      const res = await fetch('/api/auto-download-tdcc', {
        method: 'POST'
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setTdccUploadedCount(data.parsedCount);
        setTdccInsertedCount(data.insertedRecords);
        setTdccStatus('success');
        setTdccFile(null); // Clear manual staging
      } else {
        throw new Error(data.error || '自動下載與同步失敗');
      }
    } catch (err: any) {
      setTdccError(err.message || '連線至自動下載端點時發生錯誤');
      setTdccStatus('error');
    } finally {
      setAutoFetchingTdcc(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 h-full">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight mb-1">系統設定與歷史數據回補</h2>
        <p className="text-slate-400 text-sm">此控制中心提供自訂 API 介面、FinMind 歷史行情回補與 TDCC 股權分散表本地 CSV 匯入服務</p>
      </div>

      {/* 精緻的分頁 Tabs */}
      <div className="flex border-b border-slate-800">
        <button
          onClick={() => setActiveTab('general')}
          className={`px-5 py-3 text-sm font-medium transition-all relative cursor-pointer ${
            activeTab === 'general' ? 'text-blue-400 border-b-2 border-blue-500' : 'text-slate-400 hover:text-white'
          }`}
        >
          API 與實時同步
        </button>
        <button
          onClick={() => setActiveTab('finmind')}
          className={`px-5 py-3 text-sm font-medium transition-all relative cursor-pointer ${
            activeTab === 'finmind' ? 'text-blue-400 border-b-2 border-blue-500' : 'text-slate-400 hover:text-white'
          }`}
        >
          FinMind 歷史數據回補
        </button>
        <button
          onClick={() => setActiveTab('tdcc')}
          className={`px-5 py-3 text-sm font-medium transition-all relative cursor-pointer ${
            activeTab === 'tdcc' ? 'text-blue-400 border-b-2 border-blue-500' : 'text-slate-400 hover:text-white'
          }`}
        >
          TDCC 集保股權匯入
        </button>
      </div>

      <div className="flex-1">
        <AnimatePresence mode="wait">
          {/* 1. API 與實時同步 TAB */}
          {activeTab === 'general' && (
            <motion.div
              key="general"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.15 }}
              className="grid grid-cols-1 lg:grid-cols-2 gap-6"
            >
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 bg-blue-500/10 rounded-lg">
                      <Database className="text-blue-400" size={24} />
                    </div>
                    <div>
                      <h3 className="text-lg font-medium text-white">實時日曆資料同步</h3>
                      <p className="text-sm text-slate-400">手動觸發最新交易日爬蟲與資料庫補登</p>
                    </div>
                  </div>
                  
                  <div className="bg-slate-950 rounded-xl border border-slate-800 p-5 mb-6">
                    <div className="flex flex-col justify-between mb-4">
                      <span className="text-slate-300 text-sm mb-2">最後更新時間</span>
                      <span className="text-slate-400 font-mono text-xs whitespace-pre-wrap">
                        {lastUpdated}
                      </span>
                    </div>
                    <div className="flex items-center justify-between mb-4">
                      <span className="text-slate-300 text-sm">資料庫連線狀態</span>
                      <span className={`flex items-center gap-1.5 font-medium text-sm ${dbConnected ? 'text-emerald-400' : 'text-rose-400'}`}>
                        <span className="relative flex h-2 w-2">
                          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${dbConnected ? 'bg-emerald-400' : 'bg-rose-400'} opacity-75`}></span>
                          <span className={`relative inline-flex rounded-full h-2 w-2 ${dbConnected ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
                        </span>
                        {dbConnected ? '已連線' : '未連線'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-300 text-sm">當前更新路徑</span>
                      <span className="text-slate-500 font-mono text-xs overflow-hidden text-ellipsis max-w-xs whitespace-nowrap" title={webhookUrl || '本地 SQLite 備源'}>
                        {webhookUrl || '本地預設 (SQLite Crawler)'}
                      </span>
                    </div>
                  </div>

                  {/* 實時爬取日誌明細終端 (Real-time sync logs terminal) */}
                  {(syncRunning || syncLogs.length > 0) && (
                    <div className="mb-6 flex flex-col">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                          <span className={`relative flex h-2 w-2 ${syncRunning ? 'block' : 'hidden'}`}>
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                          </span>
                          {syncRunning ? '實時爬取進行中 (日誌串流)' : '最近一次同步對接明細日誌'}
                        </span>
                        {syncLogs.length > 0 && (
                          <button 
                            type="button"
                            onClick={() => setSyncLogs([])}
                            className="text-[10px] text-indigo-400 hover:text-indigo-300 font-mono underline cursor-pointer"
                          >
                            清除日誌歷史
                          </button>
                        )}
                      </div>
                      <div className="h-48 bg-slate-950 border border-slate-800 rounded-lg p-3 font-mono text-[11px] text-slate-300 overflow-y-auto space-y-1 select-text scrollbar-thin scrollbar-thumb-slate-800">
                        {syncLogs.map((log, idx) => (
                          <div 
                            key={idx} 
                            className={
                              log.includes('[ERR]') || log.includes('[錯誤]') || log.includes('❌') ? 'text-rose-400 font-medium' :
                              log.includes('✅') || log.includes('成功') ? 'text-emerald-400 font-medium' :
                              log.includes('[警告]') || log.includes('WARN') ? 'text-amber-400' : 'text-slate-400'
                            }
                          >
                            {log}
                          </div>
                        ))}
                        <div ref={syncLogsEndRef} />
                      </div>
                    </div>
                  )}

                  {syncError && (
                    <div className="mb-6 p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-400 text-xs flex gap-2 items-start">
                      <AlertCircle size={15} className="shrink-0 mt-0.5" />
                      <span>執行核心更新時發生連線或執行阻礙: {syncError}</span>
                    </div>
                  )}
                </div>

                <div>
                  <button 
                    onClick={handleManualUpdate}
                    disabled={isUpdating || syncRunning}
                    className="w-full relative overflow-hidden group bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-medium py-3 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors focus:ring-2 focus:ring-blue-500/50 outline-none cursor-pointer"
                  >
                    {isUpdating || syncRunning ? (
                      <>
                        <RefreshCw size={18} className="animate-spin" />
                        <span>同步程序運算中... (外部 API / 寫入 SQLite)</span>
                      </>
                    ) : (
                      <>
                        <RefreshCw size={18} className="group-hover:rotate-180 transition-transform duration-500" />
                        <span>立即手動更新當前大盤行情</span>
                      </>
                    )}
                  </button>

                  <AnimatePresence>
                    {updateStatus === 'success' && (
                      <motion.div 
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        className="mt-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center gap-2 text-emerald-400 text-sm"
                      >
                        <CheckCircle2 size={16} />
                        資料同步指令成功發布，日誌將於上方即時串流！
                      </motion.div>
                    )}
                    {updateStatus === 'error' && (
                      <motion.div 
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        className="mt-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-center gap-2 text-rose-400 text-sm"
                      >
                        <AlertCircle size={16} />
                        更新指令發送失敗，請細閱上方異常訊息。
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>

              {/* 右側：API 金鑰與 Webhook 整合區塊 */}
              <form onSubmit={handleSaveSettings} className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col justify-between h-fit gap-6">
                <div>
                  <div 
                    onClick={() => setIsApiCollapsed(!isApiCollapsed)}
                    className="flex items-center justify-between cursor-pointer select-none group border-b border-slate-800/60 pb-4"
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-indigo-500/10 rounded-lg">
                        <Key className="text-indigo-400" size={24} />
                      </div>
                      <div>
                        <h3 className="text-lg font-medium text-white flex items-center gap-2">
                          雲端與 API 整合設定
                          <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono font-medium ${isApiCollapsed ? 'bg-slate-950 text-slate-400 border-slate-800' : 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20'}`}>
                            {isApiCollapsed ? '已折疊收合' : '編輯設定中'}
                          </span>
                        </h3>
                        <p className="text-sm text-slate-400">配置 Finmind / Longcat 金鑰及 Webhook URL</p>
                      </div>
                    </div>

                    <div className="text-slate-400 group-hover:text-white transition-colors pl-4 shrink-0">
                      {isApiCollapsed ? (
                        <span className="text-xs text-indigo-400 font-medium flex items-center gap-1 hover:underline">
                          展開欄位修正
                          <ArrowRight size={14} className="rotate-90 text-indigo-400" />
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400 font-medium flex items-center gap-1 hover:underline">
                          點此收合遮蔽
                          <ArrowRight size={14} className="-rotate-90" />
                        </span>
                      )}
                    </div>
                  </div>

                  <AnimatePresence initial={false}>
                    {!isApiCollapsed && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <div className="space-y-4 pt-6 mb-6">
                          {/* Webhook API */}
                          <div>
                            <label className="block text-sm font-medium text-slate-300 mb-1.5">資料更新 Webhook URL</label>
                            <div className="relative">
                              <Server className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                              <input 
                                type="text"
                                value={webhookUrl}
                                onChange={(e) => setWebhookUrl(e.target.value)}
                                placeholder="https://your-server.com/api/update"
                                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-sm text-slate-300 focus:outline-none focus:border-indigo-500 transition-colors"
                              />
                            </div>
                            <p className="text-[11px] text-slate-500 mt-1">留空將採用伺服器本地 SQLite 與 Supabase 連線執行爬蟲</p>
                          </div>

                          {/* Finmind API Key */}
                          <div>
                            <label className="block text-sm font-medium text-slate-300 mb-1.5">Finmind API Key (金鑰)</label>
                            <div className="relative">
                              <Shield className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                              <input 
                                type={showFinmind ? "text" : "password"} 
                                value={finmindApiKey}
                                onChange={(e) => setFinmindApiKey(e.target.value)}
                                placeholder="請輸入 Finmind 金鑰"
                                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-10 py-2 text-sm text-slate-300 focus:outline-none focus:border-indigo-500 transition-colors"
                              />
                              <button
                                type="button"
                                onClick={() => setShowFinmind(!showFinmind)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                              >
                                {showFinmind ? <EyeOff size={16} /> : <Eye size={16} />}
                              </button>
                            </div>
                          </div>

                          {/* Longcat API Key */}
                          <div>
                            <label className="block text-sm font-medium text-slate-300 mb-1.5">Longcat API Key (金鑰)</label>
                            <div className="relative">
                              <Shield className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                              <input
                                type={showLongcat ? "text" : "password"}
                                value={longcatApiKey}
                                onChange={(e) => setLongcatApiKey(e.target.value)}
                                placeholder="請輸入 Longcat 金鑰"
                                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-10 py-2 text-sm text-slate-300 focus:outline-none focus:border-indigo-500 transition-colors"
                              />
                              <button
                                type="button"
                                onClick={() => setShowLongcat(!showLongcat)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                              >
                                {showLongcat ? <EyeOff size={16} /> : <Eye size={16} />}
                              </button>
                            </div>
                          </div>

                          {/* Longcat Base URL */}
                          <div>
                            <label className="block text-sm font-medium text-slate-300 mb-1.5">Longcat Base URL</label>
                            <div className="relative">
                              <Server className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                              <input
                                type="text"
                                value={longcatBaseUrl}
                                onChange={(e) => setLongcatBaseUrl(e.target.value)}
                                placeholder="https://api.longcat.chat/openai/v1"
                                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-sm text-slate-300 focus:outline-none focus:border-indigo-500 transition-colors"
                              />
                            </div>
                          </div>

                          {/* Longcat Model */}
                          <div>
                            <label className="block text-sm font-medium text-slate-300 mb-1.5">Longcat Model</label>
                            <div className="relative">
                              <Server className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                              <input
                                type="text"
                                value={longcatModel}
                                onChange={(e) => setLongcatModel(e.target.value)}
                                placeholder="LongCat-2.0-Preview"
                                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-sm text-slate-300 focus:outline-none focus:border-indigo-500 transition-colors"
                              />
                            </div>
                          </div>
                        </div>

                        <div>
                          <button 
                            type="submit"
                            disabled={isSaving}
                            className="w-full relative overflow-hidden group bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-medium py-3 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors focus:ring-2 focus:ring-indigo-500/50 outline-none cursor-pointer"
                          >
                            {isSaving ? (
                              <>
                                <RefreshCw size={18} className="animate-spin" />
                                <span>設定儲存中...</span>
                              </>
                            ) : (
                              <>
                                <Save size={18} />
                                <span>儲存金鑰與環境設定</span>
                              </>
                            )}
                          </button>

                          <AnimatePresence>
                            {saveStatus === 'success' && (
                              <motion.div 
                                initial={{ opacity: 0, y: -10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.95 }}
                                className="mt-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center gap-2 text-emerald-400 text-sm"
                              >
                                <CheckCircle2 size={16} />
                                設定已成功儲存並同步至系統工作環境！
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {isApiCollapsed && (
                    <div 
                      onClick={() => setIsApiCollapsed(false)}
                      className="mt-6 p-4 bg-indigo-500/[0.03] hover:bg-indigo-500/[0.07] border border-indigo-500/10 hover:border-indigo-500/20 rounded-xl text-center cursor-pointer transition-all duration-200 text-xs text-indigo-400 font-medium"
                    >
                      🔒 雲端與 API 整合設定已安全折疊遮蔽。<br/>
                      <span className="text-slate-400 text-[11px] block mt-1.5 hover:underline">點選此處或右上角「展開位修正」以顯示並編輯設定</span>
                    </div>
                  )}
                </div>
              </form>
            </motion.div>
          )}

          {/* 2. FINMIND 歷史數據回補 TAB */}
          {activeTab === 'finmind' && (
            <motion.div
              key="finmind"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.15 }}
              className="grid grid-cols-1 lg:grid-cols-3 gap-6"
            >
              {/* 回補表單控制區 */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 lg:col-span-1 flex flex-col justify-between">
                <form onSubmit={handleFinMindBackfill} className="space-y-4">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="p-2 bg-emerald-500/10 rounded-lg">
                      <Calendar className="text-emerald-400" size={24} />
                    </div>
                    <div>
                      <h3 className="text-lg font-medium text-white">FinMind 回補設定</h3>
                      <p className="text-xs text-slate-400">設定股號與日期區間下載歷史明細</p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">股票代號 (Stock ID 或 批次清單)</label>
                    <input 
                      type="text"
                      required
                      value={backfillStockId}
                      onChange={(e) => setBackfillStockId(e.target.value)}
                      placeholder="例如 2330, 2317, 2454 批次，或填 ALL_META"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 font-mono"
                    />
                    <p className="text-[10px] text-slate-400 mt-1 leading-relaxed">
                      💡 支援<strong>批次輸入</strong>！您可以填寫多個股號用半角或全形逗號（如 <span className="text-emerald-400 font-mono">2330,2317,2454</span>）或空格隔開，即可一鍵自動背景連續回補！
                    </p>
                    
                    <div className="mt-3 space-y-1.5">
                      <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500 block">⚡ 一鍵快捷填寫組合：</span>
                      <div className="flex flex-wrap gap-1.5">
                        <button
                          type="button"
                          onClick={() => setBackfillStockId("2330, 2317, 2454, 2303, 2603")}
                          className="text-[10px] bg-slate-800 hover:bg-slate-700 hover:text-white text-slate-300 px-2 py-1 rounded border border-slate-700/60 transition-colors cursor-pointer"
                        >
                          📋 熱門五檔 (2330,2317...)
                        </button>
                        <button
                          type="button"
                          onClick={() => setBackfillStockId("2330, 2454")}
                          className="text-[10px] bg-slate-800 hover:bg-slate-700 hover:text-white text-slate-300 px-2 py-1 rounded border border-slate-700/60 transition-colors cursor-pointer"
                        >
                          📋 半導體雙雄 (2330,2454)
                        </button>
                        <button
                          type="button"
                          onClick={() => setBackfillStockId("9904, 2603, 2330, 2317, 2454, 2303, 2609, 3037, 2379, 2382, 3231, 2301")}
                          className="text-[10px] bg-slate-800 hover:bg-slate-700 hover:text-white text-slate-300 px-2 py-1 rounded border border-slate-700/60 transition-colors cursor-pointer"
                        >
                          📋 核心觀察十二檔
                        </button>
                        <button
                          type="button"
                          onClick={() => setBackfillStockId("ALL_META")}
                          className="text-[10px] bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded border border-emerald-500/20 font-medium transition-colors cursor-pointer"
                        >
                          🚀 全體自動回補 (ALL_META)
                        </button>
                      </div>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">開始日期 (Start Date)</label>
                    <input 
                      type="date"
                      required
                      value={backfillStartDate}
                      onChange={(e) => setBackfillStartDate(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">結束日期 (留空預設到今天)</label>
                    <input 
                      type="date"
                      value={backfillEndDate}
                      onChange={(e) => setBackfillEndDate(e.target.value)}
                      placeholder="YYYY-MM-DD"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                    />
                  </div>

                  <div className="space-y-2.5 pt-2">
                    <label className="block text-sm font-medium text-slate-300">資料集選擇</label>
                    
                    <label className="flex items-center gap-2 cursor-pointer text-sm text-slate-300">
                      <input 
                        type="checkbox"
                        checked={backfillPrice}
                        onChange={(e) => setBackfillPrice(e.target.checked)}
                        className="rounded border-slate-800 text-emerald-500 bg-slate-950 focus:ring-emerald-500"
                      />
                      <span>歷史日 K 收盤行情 (TaiwanStockPrice)</span>
                    </label>

                    <label className="flex items-center gap-2 cursor-pointer text-sm text-slate-300">
                      <input 
                        type="checkbox"
                        checked={backfillInstitutional}
                        onChange={(e) => setBackfillInstitutional(e.target.checked)}
                        className="rounded border-slate-800 text-emerald-500 bg-slate-950 focus:ring-emerald-500"
                      />
                      <span>三大法人各類進出 (TaiwanStockInstitutional)</span>
                    </label>
                  </div>

                  <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg flex items-start gap-2 text-amber-400 text-xs mt-2 leading-relaxed">
                    <AlertTriangle size={15} className="shrink-0 mt-0.5" />
                    <span>回補速度與權限受控於您的 Finmind API Key 設定。如未填寫 Key，速度將可能受限。</span>
                  </div>
                </form>

                <div className="pt-6">
                  <button
                    onClick={handleFinMindBackfill}
                    disabled={isBackfilling || (!backfillPrice && !backfillInstitutional)}
                    className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-medium rounded-lg flex items-center justify-center gap-2 cursor-pointer transition-colors"
                  >
                    {isBackfilling ? (
                      <>
                        <RefreshCw size={18} className="animate-spin" />
                        <span>FinMind 歷史回補中...</span>
                      </>
                    ) : (
                      <>
                        <ArrowRight size={18} />
                        <span>執行 FinMind 歷史對接補帳</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* 右側展示控制輸出紀錄 */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 lg:col-span-2 flex flex-col justify-between h-[480px]">
                <div className="flex flex-col h-full w-full">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-medium text-white uppercase tracking-wider">回補日誌與輸出控制台</h3>
                    <span className="text-[10px] bg-slate-950 text-slate-400 px-2 py-0.5 rounded font-mono border border-slate-800">
                      TERMINAL_LOG
                    </span>
                  </div>

                  <div className="flex-1 bg-slate-950 border border-slate-800 rounded-lg p-4 font-mono text-xs text-slate-400 overflow-y-auto space-y-1.5 h-full select-text">
                    {backfillLogs.length === 0 ? (
                      <div className="text-slate-600 italic h-full flex items-center justify-center">
                        等待設定並按下「執行歷史對接補帳」...
                      </div>
                    ) : (
                      backfillLogs.map((log, idx) => (
                        <div key={idx} className={
                          log.startsWith('❌') ? 'text-rose-400' :
                          log.startsWith('✅') ? 'text-emerald-400' :
                          log.startsWith('⚠️') ? 'text-amber-400' :
                          log.startsWith('📅') ? 'text-blue-400' : 'text-slate-300'
                        }>
                          {log}
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className="mt-4">
                  <AnimatePresence>
                    {backfillStatus === 'success' && (
                      <motion.div 
                        initial={{ opacity: 0, scale: 0.98 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center gap-2 text-emerald-400 text-sm"
                      >
                        <CheckCircle2 size={16} />
                        歷史回補流程順利完成！大盤、個股與法人視窗皆已更新。
                      </motion.div>
                    )}
                    {backfillStatus === 'error' && (
                      <motion.div 
                        initial={{ opacity: 0, scale: 0.98 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-center gap-2 text-rose-400 text-sm"
                      >
                        <AlertCircle size={16} />
                        對接回補任務異常終止！請細閱終端輸出的錯誤細節。
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            </motion.div>
          )}

          {/* 3. TDCC 集保戶股權分散表 TAB */}
          {activeTab === 'tdcc' && (
            <motion.div
              key="tdcc"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.15 }}
              className="grid grid-cols-1 lg:grid-cols-3 gap-6"
            >
              {/* 上傳與拖曳主要區域 */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 lg:col-span-2 flex flex-col justify-between gap-6">
                <div>
                  <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 bg-blue-500/10 rounded-lg">
                      <FileUp className="text-blue-400" size={24} />
                    </div>
                    <div>
                      <h3 className="text-lg font-medium text-white">TDCC 集保股權匯入</h3>
                      <p className="text-sm text-slate-400">支援拖曳或上傳自集保下載的股權分散表官方 CSV 明細</p>
                    </div>
                  </div>

                  {/* 拖曳感應面板 */}
                  <div 
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center gap-4 transition-all cursor-pointer min-h-[240px] ${
                      isDragging 
                        ? 'border-blue-500 bg-blue-500/5' 
                        : tdccFile 
                          ? 'border-emerald-500/50 bg-emerald-500/[0.02]' 
                          : 'border-slate-800 hover:border-slate-700 bg-slate-950/40 hover:bg-slate-950/70'
                    }`}
                  >
                    <input 
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileSelect}
                      accept=".csv"
                      className="hidden"
                    />

                    {tdccFile ? (
                      <>
                        <div className="p-4 bg-emerald-500/10 rounded-full text-emerald-400 select-none">
                          <FileText size={48} />
                        </div>
                        <div className="text-center">
                          <p className="text-sm font-medium text-white truncate max-w-sm">{tdccFile.name}</p>
                          <p className="text-xs text-slate-500 font-mono mt-1">{(tdccFile.size / 1024 / 1024).toFixed(2)} MB</p>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-full font-medium">
                          <Check size={12} />
                          檔案已就緒
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="p-4 bg-slate-900 rounded-full text-slate-400">
                          <Upload size={36} />
                        </div>
                        <div className="text-center">
                          <p className="text-sm font-medium text-slate-300">點擊選擇檔案，或直接將官方集保 CSV 拖入此區域</p>
                          <p className="text-xs text-slate-500 mt-2 leading-relaxed max-w-md">
                            支援集保官網之「集保戶股權分散表」檔案明細，此格式包含：<br/>
                            <span className="font-mono bg-slate-950 px-1 py-0.5 rounded text-slate-400">資料日期,證券代號,持股分級,人數,股數,占比例%</span> 等欄位。
                          </p>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex flex-col gap-3">
                  <div className="flex gap-4">
                    {tdccFile && (
                      <button
                        onClick={() => {
                          setTdccFile(null);
                          setTdccStatus('idle');
                          setTdccError(null);
                        }}
                        disabled={uploadingTdcc || autoFetchingTdcc}
                        className="px-4 py-3 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 rounded-lg text-sm font-medium transition-colors cursor-pointer"
                      >
                        清除檔案
                      </button>
                    )}
                    <button
                      onClick={handleTdccUpload}
                      disabled={!tdccFile || uploadingTdcc || autoFetchingTdcc}
                      className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-medium rounded-lg flex items-center justify-center gap-2 cursor-pointer transition-colors"
                    >
                      {uploadingTdcc ? (
                        <>
                          <RefreshCw size={18} className="animate-spin" />
                          <span>正解析並寫入中... 請稍候</span>
                        </>
                      ) : (
                        <>
                          <Save size={18} />
                          <span>上傳本地檔案並匯入/同步</span>
                        </>
                      )}
                    </button>
                  </div>

                  <div className="border-t border-slate-800/80 my-1 pt-3">
                    <button
                      onClick={handleTdccAutoFetch}
                      disabled={uploadingTdcc || autoFetchingTdcc}
                      className="w-full py-3 bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 disabled:from-slate-800 disabled:to-slate-800 disabled:text-slate-500 text-white font-semibold rounded-lg flex items-center justify-center gap-2 cursor-pointer transition-all border border-emerald-500/10 shadow-sm"
                    >
                      {autoFetchingTdcc ? (
                        <>
                          <RefreshCw size={18} className="animate-spin" />
                          <span>正在從集保結算所自動下載最新資料並同步 Supabase...</span>
                        </>
                      ) : (
                        <>
                          <RefreshCw size={18} />
                          <span>一鍵自動線上抓取最新集保分散表並同步 Supabase</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* 說明與結果視覺 */}
              <div className="space-y-6 lg:col-span-1">
                {/* 核心批次說明卡 */}
                <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-xl p-5 leading-relaxed text-indigo-300">
                  <h4 className="text-sm font-semibold text-white mb-2.5 flex items-center gap-1.5">
                    💡 對接常識：一鍵更新「全市場」
                  </h4>
                  <p className="text-xs leading-relaxed space-y-2 select-text">
                    <strong>您知道嗎？集保官方 CSV 是不分股票的！</strong>
                    <br/><br/>
                    從集保結算所（TDCC）官網下載的任何一週「集保戶股權分散表」CSV，<strong>本身即是一個單一、幾十 MB 的大集合，內含「台積電、聯發科、鴻海、長榮及全台所有上市櫃個股」在該週的所有持有結構比例！</strong>
                    <br/><br/>
                    因此，您<strong>完全不需要</strong>為每檔個股分別上傳。您只需<strong>每週上傳這「一檔」官方檔案</strong>，系統就會自動對接、批量解析並完整回補資料庫中所有追蹤個股的最新持股籌碼！
                  </p>
                </div>

                {/* 說明卡 */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 leading-relaxed">
                  <h4 className="text-sm font-medium text-white mb-3">為什麼需要手動上傳？</h4>
                  <p className="text-xs text-slate-400 leading-relaxed space-y-2">
                    集保開源（OpenData）伺服器針對伺服器抓取設有十分嚴格的 IP 國家驗證與阻擋機制。
                    <br/><br/>
                    通過網頁上傳這款 CSV 檔案，是<strong>最安全、能百分之百對齊最新大戶與散戶異動資料</strong>的穩定方案。
                    <br/><br/>
                    <strong>大戶與散戶定義：</strong><br/>
                    系統自動歸納<strong>持股 40 萬股以上</strong>（第 12 級持股分級或更高）為大戶；歸納<strong>持股 2 萬股以下</strong>（第 5 級持股分級或更低）為散戶。
                  </p>
                </div>

                {/* 結果顯示 */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
                  <h4 className="text-sm font-medium text-white mb-4">分析與寫入狀態</h4>
                  
                  {tdccStatus === 'idle' && !tdccError && (
                    <div className="text-xs text-slate-500 italic py-6 text-center">
                      等待上傳 CSV 檔案以展開主動安全分析...
                    </div>
                  )}

                  {tdccError && (
                    <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-start gap-2 text-rose-400 text-xs">
                      <AlertCircle size={15} className="shrink-0 mt-0.5" />
                      <span>{tdccError}</span>
                    </div>
                  )}

                  {tdccStatus === 'success' && (
                    <div className="space-y-4">
                      <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center gap-2 text-emerald-400 text-sm">
                        <CheckCircle2 size={16} />
                        <span>資料格式校驗成功，對接主資料庫成功！</span>
                      </div>
                      
                      <div className="space-y-3 bg-slate-950 border border-slate-800 rounded-lg p-4 font-mono text-xs text-slate-400">
                        <div className="flex justify-between">
                          <span>解析原始明細數</span>
                          <span className="text-white">{tdccUploadedCount} 條</span>
                        </div>
                        <div className="flex justify-between border-t border-slate-800/60 pt-2">
                          <span>SQLite 映射覆蓋數</span>
                          <span className="text-emerald-400">{tdccInsertedCount} 筆交易週指標</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* 唯讀雲端整合狀態 */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Shield className="text-slate-400" size={20} />
          <h4 className="text-sm font-medium text-white">唯讀系統基礎資訊</h4>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="bg-slate-950 p-4 border border-slate-800 rounded-lg">
            <span className="block text-[11px] font-medium text-slate-500 uppercase tracking-wider mb-1">Supabase URL</span>
            <span className="text-xs text-slate-400 font-mono truncate block" title={import.meta.env.VITE_SUPABASE_URL || '未設定'}>
              {import.meta.env.VITE_SUPABASE_URL || '未設定'}
            </span>
          </div>
          <div className="bg-slate-950 p-4 border border-slate-800 rounded-lg">
            <span className="block text-[11px] font-medium text-slate-500 uppercase tracking-wider mb-1">Supabase Anon Key</span>
            <span className="text-xs text-slate-400 font-mono block">
              {import.meta.env.VITE_SUPABASE_ANON_KEY ? '●●●●●●●● (已載入)' : '未設定'}
            </span>
          </div>
          <div className="bg-slate-950 p-4 border border-slate-800 rounded-lg">
            <span className="block text-[11px] font-medium text-slate-500 uppercase tracking-wider mb-1">資料來源</span>
            <span className="text-xs text-slate-400 font-mono block">TWSE 台灣證券交易所 API & FinMind 歷史明細 & TDCC</span>
          </div>
        </div>
      </div>
    </div>
  );
}
