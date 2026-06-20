import React, { useMemo, useState } from 'react';
import {
  ComposedChart, BarChart, LineChart, Line, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, ComposedChart as RechartsComposedChart,
  ReferenceLine, Cell
} from 'recharts';
import { PriceData, calcMA, calcMACD, calcRSI, calcKD } from '../lib/indicators';

interface KlineChartProps {
  data: PriceData[];
}

type TabType = 'kline' | 'macd' | 'rsi' | 'kd';

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const d = payload[0].payload;
    const isUp = d.close >= d.open;
    const change = d.close - d.open;
    const changePct = (change / d.open) * 100;
    return (
      <div className="bg-slate-950/95 border border-slate-800 p-3 rounded-lg shadow-2xl font-mono text-xs text-slate-300 space-y-1.5 min-w-[200px] backdrop-blur-sm">
        <div className="text-slate-400 font-bold border-b border-slate-800 pb-1 mb-1">{d.date}</div>
        <div className="space-y-0.5">
          <div className="flex justify-between">
            <span className="text-slate-500">開盤:</span>
            <span className="text-slate-200 font-bold">{d.open.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">最高:</span>
            <span className="text-red-400 font-bold">{d.high.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">最低:</span>
            <span className="text-emerald-400 font-bold">{d.low.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">收盤:</span>
            <span className={isUp ? "text-red-400 font-bold" : "text-emerald-400 font-bold"}>
              {d.close.toFixed(2)}
            </span>
          </div>
          <div className="flex justify-between border-t border-slate-850 pt-1 mt-1">
            <span className="text-slate-500">漲跌:</span>
            <span className={change >= 0 ? "text-red-400 font-bold" : "text-emerald-400 font-bold"}>
              {change >= 0 ? `+${change.toFixed(2)}` : change.toFixed(2)} ({changePct >= 0 ? `+${changePct.toFixed(2)}%` : `${changePct.toFixed(2)}%`})
            </span>
          </div>
          <div className="flex justify-between pt-0.5">
            <span className="text-slate-500">成交量:</span>
            <span className="text-slate-100 font-semibold">{d.volume.toLocaleString()} 張</span>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

export function KlineChart({ data }: KlineChartProps) {
  const [activeTab, setActiveTab] = useState<TabType>('kline');
  const [maPeriods, setMaPeriods] = useState<number[]>([5, 20, 60]);

  const closes = useMemo(() => data.map(d => d.close), [data]);

  const maData = useMemo(() => {
    return {
      ma5: maPeriods.includes(5) ? calcMA(closes, 5) : [],
      ma20: maPeriods.includes(20) ? calcMA(closes, 20) : [],
      ma60: maPeriods.includes(60) ? calcMA(closes, 60) : [],
    };
  }, [closes, maPeriods]);

  const macdData = useMemo(() => calcMACD(closes), [closes]);
  const rsiData = useMemo(() => calcRSI(closes), [closes]);
  const kdData = useMemo(() => calcKD(data), [data]);

  const volumeMax = useMemo(() => Math.max(...data.map(d => d.volume), 1), [data]);

  const chartData = useMemo(() => {
    return data.map((d, i) => {
      const isUp = d.close >= d.open;
      const color = isUp ? '#ef4444' : '#22c55e';
      const upper = Math.max(d.open, d.close);
      const lower = Math.min(d.open, d.close);
      return {
        date: d.date,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
        volume: d.volume,
        color,
        upper,
        lower,
        // 利用 Range Bar 概念：[lower, upper] 代表開關價的實體高度
        boxRange: [lower, upper],
        // [low, high] 代表上下影線的完整高低價高度
        wickRange: [d.low, d.high],
        ma5: maData.ma5[i],
        ma20: maData.ma20[i],
        ma60: maData.ma60[i],
        dif: macdData.dif[i],
        dea: macdData.dea[i >= 26 ? i - 26 : -1],
        macd: macdData.macd[i],
        rsi: rsiData[i],
        k: kdData.k[i],
        d: kdData.d[i],
        isUp,
      };
    });
  }, [data, maData, macdData, rsiData, kdData]);

  const tabs: { key: TabType; label: string }[] = [
    { key: 'kline', label: 'K 線' },
    { key: 'macd', label: 'MACD' },
    { key: 'rsi', label: 'RSI' },
    { key: 'kd', label: 'KD' },
  ];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg shadow-black/40">
      {/* Tabs */}
      <div className="flex border-b border-slate-800 bg-slate-950/30">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2.5 text-xs font-medium transition-colors ${
              activeTab === tab.key
                ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-950/20'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
        {activeTab === 'kline' && (
          <div className="ml-auto flex items-center gap-1 px-3">
            {[5, 20, 60].map(p => (
              <button
                key={p}
                onClick={() => setMaPeriods(prev => prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p].sort((a,b) => a-b))}
                className={`px-2 py-1 text-[10px] rounded transition-all font-mono ${
                  maPeriods.includes(p)
                    ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                MA{p}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Chart Area */}
      <div className="p-3" style={{ height: activeTab === 'kline' ? 380 : 280 }}>
        {activeTab === 'kline' && (
          <div className="h-full flex flex-col justify-between">
            {/* Price + MA Chart (True Candlestick with customized layout) */}
            <div style={{ height: '70%', minHeight: '220px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <RechartsComposedChart 
                  data={chartData} 
                  margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                  barGap="-100%" // 重要技巧：使得影線和K線對焦在同一個 X 點垂直重合
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.6} />
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
                  <YAxis domain={['auto', 'auto']} tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
                  <Tooltip content={<CustomTooltip />} />

                  {/* 1. 繪製上下影線 (Wicks) - 高低價的細棒 */}
                  <Bar dataKey="wickRange" barSize={1.5}>
                    {chartData.map((entry, index) => (
                      <Cell key={`wick-${index}`} fill={entry.color} />
                    ))}
                  </Bar>

                  {/* 2. 繪製 K 線實體 (Candle Boxes) - 開收價的粗棒 */}
                  <Bar dataKey="boxRange" barSize={10}>
                    {chartData.map((entry, index) => (
                      <Cell key={`box-${index}`} fill={entry.color} stroke={entry.color} />
                    ))}
                  </Bar>

                  {/* 3. 繪製 移動平均線 (MA Lines) */}
                  {maPeriods.includes(5) && <Line type="monotone" dataKey="ma5" stroke="#f43f5e" dot={false} strokeWidth={1.5} name="MA5" />}
                  {maPeriods.includes(20) && <Line type="monotone" dataKey="ma20" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="MA20" />}
                  {maPeriods.includes(60) && <Line type="monotone" dataKey="ma60" stroke="#3b82f6" dot={false} strokeWidth={1.5} name="MA60" />}
                </RechartsComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Volume Chart (Colored Volume bars matched with price change) */}
            <div style={{ height: '26%', minHeight: '80px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.4} />
                  <XAxis dataKey="date" tick={false} tickLine={false} axisLine={false} />
                  <YAxis domain={[0, 'auto']} tick={{ fill: '#64748b', fontSize: 9 }} tickLine={false} axisLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="volume">
                    {chartData.map((entry, index) => (
                      <Cell key={`vol-cell-${index}`} fill={entry.color} opacity={0.65} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {activeTab === 'macd' && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#f1f5f9', fontSize: '12px' }} />
              <Bar dataKey="macd" fill="#64748b" opacity={0.7} />
              <Line type="monotone" dataKey="dif" stroke="#06b6d4" dot={false} strokeWidth={1.5} name="DIF" />
              <Line type="monotone" dataKey="dea" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="DEA" />
              <ReferenceLine y={0} stroke="#334155" strokeDasharray="3 3" />
            </BarChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'rsi' && (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#f1f5f9', fontSize: '12px' }} />
              <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="3 3" label={{ value: '超買 70', fill: '#ef4444', fontSize: 10 }} />
              <ReferenceLine y={30} stroke="#22c55e" strokeDasharray="3 3" label={{ value: '超賣 30', fill: '#22c55e', fontSize: 10 }} />
              <Line type="monotone" dataKey="rsi" stroke="#06b6d4" dot={false} strokeWidth={2} name="RSI" />
            </LineChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'kd' && (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
              <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#f1f5f9', fontSize: '12px' }} />
              <ReferenceLine y={80} stroke="#ef4444" strokeDasharray="3 3" label={{ value: '80', fill: '#ef4444', fontSize: 10 }} />
              <ReferenceLine y={20} stroke="#22c55e" strokeDasharray="3 3" label={{ value: '20', fill: '#22c55e', fontSize: 10 }} />
              <Line type="monotone" dataKey="k" stroke="#06b6d4" dot={false} strokeWidth={2} name="K" />
              <Line type="monotone" dataKey="d" stroke="#f59e0b" dot={false} strokeWidth={2} name="D" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}