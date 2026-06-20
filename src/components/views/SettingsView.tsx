import React, { useState, useEffect } from 'react';
import { Database, RefreshCw, Server, Shield, CheckCircle2, AlertCircle, Key, Eye, EyeOff, Save } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

export function SettingsView() {
  const [isUpdating, setIsUpdating] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>('載入中...');
  const [updateStatus, setUpdateStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [dbConnected, setDbConnected] = useState(false);

  // API 金鑰與 Webhook 改用可動態設定的本機/後端狀態
  const [webhookUrl, setWebhookUrl] = useState('');
  const [finmindApiKey, setFinmindApiKey] = useState('');
  const [longcatApiKey, setLongcatApiKey] = useState('');
  
  const [showFinmind, setShowFinmind] = useState(false);
  const [showLongcat, setShowLongcat] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');

  // 一併自後端載入實體資料庫狀態與當前儲存的 API 設定
  useEffect(() => {
    fetchRealDatabaseStatus();
    fetchCurrentSettings();
  }, []);

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
      }
    } catch (error) {
      console.error('Fetch settings error:', error);
    }
  };

  const handleManualUpdate = async () => {
    setIsUpdating(true);
    setUpdateStatus('idle');
    
    try {
      const res = await fetch('/api/trigger-update', { method: 'POST' });
      if (!res.ok) {
        throw new Error('Webhook failed');
      }

      await fetchRealDatabaseStatus();
      setUpdateStatus('success');
    } catch (error) {
      console.error('Update failed:', error);
      setUpdateStatus('error');
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
          longcatApiKey
        })
      });

      if (!res.ok) throw new Error('儲存設定失敗');
      
      setSaveStatus('success');
      // 重新整理資料庫與最新的環境資訊
      await fetchRealDatabaseStatus();
    } catch (error) {
      console.error('Save settings failed:', error);
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
      setTimeout(() => setSaveStatus('idle'), 3000);
    }
  };

  return (
    <div className="flex flex-col gap-8 h-full">
      <div>
        <h2 className="text-2xl font-bold text-white tracking-tight mb-1">系統設定</h2>
        <p className="text-slate-400 text-sm">全域設定、金鑰與第三方 API 整合介面</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 左側：資料同步區塊 */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-blue-500/10 rounded-lg">
                <Database className="text-blue-400" size={24} />
              </div>
              <div>
                <h3 className="text-lg font-medium text-white">資料同步管理</h3>
                <p className="text-sm text-slate-400">手動觸發爬蟲與資料庫更新</p>
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
          </div>

          <div>
            <button 
              onClick={handleManualUpdate}
              disabled={isUpdating}
              className="w-full relative overflow-hidden group bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-medium py-3 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors focus:ring-2 focus:ring-blue-500/50 outline-none cursor-pointer"
            >
              {isUpdating ? (
                <>
                  <RefreshCw size={18} className="animate-spin" />
                  <span>資料同步中...</span>
                </>
              ) : (
                <>
                  <RefreshCw size={18} className="group-hover:rotate-180 transition-transform duration-500" />
                  <span>立即手動觸發更新</span>
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
                  資料更新指令觸發成功，將於背景同步爬取！
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
                  更新指令發送失敗，請檢查 API 伺服器狀態。
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* 右側：API 金鑰與 Webhook 整合區塊 */}
        <form onSubmit={handleSaveSettings} className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-indigo-500/10 rounded-lg">
                <Key className="text-indigo-400" size={24} />
              </div>
              <div>
                <h3 className="text-lg font-medium text-white">雲端與 API 整合設定</h3>
                <p className="text-sm text-slate-400">配置 Finmind / Longcat 金鑰及 Webhook URL</p>
              </div>
            </div>
            
            <div className="space-y-4 mb-6">
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
                  <span>儲存金鑰設定</span>
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
              {saveStatus === 'error' && (
                <motion.div 
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="mt-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-center gap-2 text-rose-400 text-sm"
                >
                  <AlertCircle size={16} />
                  設定儲存失敗，請檢查系統後端是否運作正常。
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </form>
      </div>

      {/* 下方的唯讀雲端整合狀態 */}
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
            <span className="text-xs text-slate-400 font-mono truncate block">
              {import.meta.env.VITE_SUPABASE_ANON_KEY ? '●●●●●●●● (已載入)' : '未設定'}
            </span>
          </div>
          <div className="bg-slate-950 p-4 border border-slate-800 rounded-lg">
            <span className="block text-[11px] font-medium text-slate-500 uppercase tracking-wider mb-1">資料來源</span>
            <span className="text-xs text-slate-400 font-mono block">TWSE 台灣證券交易所 API & Crawler</span>
          </div>
        </div>
      </div>
    </div>
  );
}
