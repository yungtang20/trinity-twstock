import { useState, useEffect } from 'react';
import { fetchPredictionAnalysis, type PredictionAnalysis } from '../../lib/api';

interface PredictionPanelProps {
  stockId: string;
}

export function PredictionPanel({ stockId }: PredictionPanelProps) {
  const [data, setData] = useState<PredictionAnalysis | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!stockId) return;
    setLoading(true);
    fetchPredictionAnalysis(stockId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [stockId]);

  return (
    <div className="bg-slate-950/50 border border-slate-800 rounded-xl p-4 sm:p-5 hover:border-slate-700/80 transition-all font-mono text-xs sm:text-[13px]">
      <h3 className="text-sm sm:text-base font-bold text-white mb-4 flex items-center gap-2 border-b border-slate-800 pb-2">
        <span className="font-mono text-cyan-400 select-none">4 ⚡</span>
        AI 預估 (Prediction)
      </h3>

      {loading && <div className="text-slate-500 text-center py-4 text-xs">計算中...</div>}
      {!loading && !data && <div className="text-slate-500 text-center py-4 text-xs">無資料</div>}

      {data && (
      <div className="space-y-4">
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-850">
          <div className="flex items-center justify-between mb-2">
            <span className="text-slate-400 font-bold">🧠 AI 判斷</span>
            <span className={`text-sm font-bold ${data.aiStrength === '看多' ? 'text-emerald-400' : 'text-rose-400'}`}>
              {data.aiStrength}
            </span>
          </div>
          <div className="space-y-1 text-slate-300">
            <div className="flex justify-between">
              <span className="text-slate-400">主模型核心 (Kronos)</span>
              <span className="font-bold text-rose-400">OFFLINE (離線)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">備援運算機制</span>
              <span className="font-bold text-amber-400 text-xs font-sans">特徵擬合運算 (Active)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">信心分數</span>
              <span className="font-bold text-white">{(data.aiScore * 100).toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">波動度</span>
              <span className="font-bold text-white">{data.volatility}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">平均報酬</span>
              <span className={`font-bold ${data.avgReturn >= 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                {data.avgReturn >= 0 ? '+' : ''}{data.avgReturn}%
              </span>
            </div>
          </div>
          <div className="mt-2 text-xs text-slate-500 bg-slate-900/60 p-2 rounded border border-slate-800">
            <span className="text-cyan-400">分析:</span> {data.aiReason}
          </div>
        </div>

        <div className="bg-slate-950 p-3 rounded-lg border border-slate-850">
          <div className="text-slate-400 font-bold mb-2">📈 預測路徑 (T+1 ~ T+5)</div>
          <div className="grid grid-cols-5 gap-2">
            {data.predictions.map((p) => (
              <div key={p.day} className="bg-slate-900/50 rounded-lg p-2 text-center border border-slate-800/60">
                <div className="text-slate-500 text-[10px]">{p.day}</div>
                <div className="text-white font-bold text-xs">{p.price.toFixed(2)}</div>
                <div className={`text-[10px] font-semibold ${p.pct >= 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                  {p.pct >= 0 ? '+' : ''}{p.pct}%
                </div>
              </div>
            ))}
          </div>
          <div className="mt-2 text-[10px] text-slate-500 text-center">
            {data.aiOffset}
          </div>
        </div>
      </div>
      )}
    </div>
  );
}