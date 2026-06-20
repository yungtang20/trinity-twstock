import React, { useState, useEffect } from 'react';
import { fetchTwseStats, fetchOtcStats } from "../../lib/api";
import { AlertCircle, RefreshCw } from "lucide-react";

export function DashboardView() {
  const [tseStats, setTseStats] = useState({
    index: 0, change: 0, changePercent: 0,
    amount: 0, limitUp: 0, up: 0, flat: 0, down: 0, limitDown: 0,
    success: false, error: ''
  });
  
  const [otcStats, setOtcStats] = useState({
    index: 0, change: 0, changePercent: 0,
    amount: 0, limitUp: 0, up: 0, flat: 0, down: 0, limitDown: 0,
    success: false, error: ''
  });
  
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [taipeiTime, setTaipeiTime] = useState<Date>(() => {
    return new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Taipei" }));
  });

  const loadData = async () => {
    setIsRefreshing(true);
    try {
      const [twse, otc] = await Promise.all([
        fetchTwseStats(),
        fetchOtcStats()
      ]);

      if (twse && twse.success) {
        setTseStats({ ...twse as any, success: true });
      } else {
        setTseStats(prev => ({ ...prev, success: false, error: twse?.error || '無法取得加權指數數據' }));
      }

      if (otc && otc.success) {
        setOtcStats({ ...otc as any, success: true });
      } else {
        setOtcStats(prev => ({ ...prev, success: false, error: otc?.error || '無法取得櫃買指數數據' }));
      }

    } catch (e: any) {
      console.error('Fetch dashboard error:', e);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
    // Update system time every second
    const timer = setInterval(() => {
      setTaipeiTime(new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Taipei" })));
    }, 1000);

    return () => {
      clearInterval(timer);
    };
  }, []);

  const formatTaipeiTime = (date: Date) => {
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    const hh = String(date.getHours()).padStart(2, '0');
    const min = String(date.getMinutes()).padStart(2, '0');
    const ss = String(date.getSeconds()).padStart(2, '0');
    const dayNames = ['日', '一', '二', '三', '四', '五', '六'];
    const d = dayNames[date.getDay()];
    return `${yyyy}-${mm}-${dd} (${d}) ${hh}:${min}:${ss}`;
  };

  const getMarketStatus = (date: Date) => {
    const day = date.getDay();
    if (day === 0 || day === 6) {
      return false; // Weekend closed
    }
    const hh = date.getHours();
    const min = date.getMinutes();
    const curMin = hh * 60 + min;
    // Taiwan Stock Market is open Mon-Fri from 09:00 AM (540 mins) to 01:30 PM (810 mins)
    return curMin >= 540 && curMin <= 810;
  };

  const isOpen = getMarketStatus(taipeiTime);
  const timeString = formatTaipeiTime(taipeiTime);

  const renderMarketCard = (title: string, data: typeof tseStats) => {
    const isUp = data.change > 0;
    const isDown = data.change < 0;
    const colorClass = isUp ? 'text-rose-500' : (isDown ? 'text-emerald-500' : 'text-slate-400');
    const sign = data.change > 0 ? '+' : '';
    
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col gap-4 relative overflow-hidden">
        {!data.success && (
          <div className="absolute top-0 right-0 bg-red-500/10 text-red-400 text-xs px-3 py-1 rounded-bl-lg border-l border-b border-red-500/20 font-medium">
            使用暫存或連接異常
          </div>
        )}
        <div className="flex flex-col gap-1 border-b border-slate-800 pb-3">
          <div className="flex items-baseline justify-between flex-wrap gap-2">
            <h2 className="text-lg sm:text-xl font-bold text-white flex items-baseline">
              {title}
              <span className="font-mono text-2xl sm:text-3.5xl ml-2 text-slate-100">
                {data.index ? data.index.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '---'}
              </span>
            </h2>
            <span className={`text-base font-bold ${colorClass}`}>
              ({sign}{data.change.toFixed(2)}、{sign}{data.changePercent.toFixed(2)}%)
            </span>
          </div>
        </div>
        
        <div className="text-sm font-medium text-slate-350 flex items-center justify-between">
          <span className="text-slate-400">總成交金額：</span>
          <span className="font-mono text-lg text-white font-semibold flex items-baseline">
            {data.amount ? data.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '---'} <span className="text-xs text-slate-450 ml-1">億元</span>
          </span>
        </div>
        
        <div className="grid grid-cols-5 gap-2 mt-2">
          <div className="flex flex-col bg-slate-850/45 rounded-lg p-2.5 text-center border border-slate-800/60">
            <span className="text-[10px] sm:text-xs text-slate-400 mb-1">漲停</span>
            <span className="text-sm sm:text-lg font-bold text-rose-500">{data.limitUp}</span>
          </div>
          <div className="flex flex-col bg-slate-850/45 rounded-lg p-2.5 text-center border border-slate-800/60">
            <span className="text-[10px] sm:text-xs text-slate-400 mb-1">上漲</span>
            <span className="text-sm sm:text-lg font-bold text-rose-400">{data.up}</span>
          </div>
          <div className="flex flex-col bg-slate-850/45 rounded-lg p-2.5 text-center border border-slate-755/50">
            <span className="text-[10px] sm:text-xs text-slate-400 mb-1">平盤</span>
            <span className="text-sm sm:text-lg font-bold text-slate-300">{data.flat}</span>
          </div>
          <div className="flex flex-col bg-slate-850/45 rounded-lg p-2.5 text-center border border-slate-800/60">
            <span className="text-[10px] sm:text-xs text-slate-400 mb-1">下跌</span>
            <span className="text-sm sm:text-lg font-bold text-emerald-400">{data.down}</span>
          </div>
          <div className="flex flex-col bg-slate-850/45 rounded-lg p-2.5 text-center border border-slate-800/60">
            <span className="text-[10px] sm:text-xs text-slate-400 mb-1">跌停</span>
            <span className="text-sm sm:text-lg font-bold text-emerald-500">{data.limitDown}</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto px-1">
      {/* 市場概況 Header Section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold text-white tracking-tight">市場概況</h1>
            <button 
              onClick={loadData}
              disabled={isRefreshing}
              className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
              title="重新整理數據"
            >
              <RefreshCw size={15} className={isRefreshing ? "animate-spin" : ""} />
            </button>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            連線官方 OpenAPI (Node.js 轉發，解決跨域 CORS 問題) 顯示即時大盤摘要。
          </p>
        </div>
        
        {/* 市場狀態與系統時間 */}
        <div className="flex flex-wrap items-center gap-4 text-sm bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5">
          <div className="flex items-center gap-2">
            <span className="text-slate-400 font-medium font-sans">市場狀態：</span>
            {isOpen ? (
              <span className="text-emerald-400 font-semibold flex items-center gap-1.5 animate-pulse">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                開盤中
              </span>
            ) : (
              <span className="text-slate-400 font-semibold flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-slate-500"></span>
                已收盤
              </span>
            )}
          </div>
          
          <div className="hidden sm:block h-4 w-[1px] bg-slate-800" />
          
          <div className="flex items-center gap-2 text-slate-400 text-xs sm:text-sm">
            <span>系統時間 (台北時間)：</span>
            <span className="font-mono text-slate-200 font-bold tracking-tight">{timeString}</span>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-24 text-slate-400 bg-slate-900 border border-slate-850 rounded-xl flex flex-col items-center justify-center gap-3">
          <RefreshCw className="animate-spin text-indigo-400" size={32} />
          <span>正在過濾與連線官方 API 數據中，請稍候...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {renderMarketCard("加權指數", tseStats)}
          {renderMarketCard("櫃買指數", otcStats)}
        </div>
      )}

    </div>
  );
}
