import React from "react";
import { LayoutDashboard, TrendingUp, BarChart3, Settings, Bot, ChartLine } from "lucide-react";
import { AppView } from "../types";

interface SidebarProps {
  currentView: AppView;
  onViewChange: (view: AppView) => void;
}

export function Sidebar({ currentView, onViewChange }: SidebarProps) {
  return (
    <aside className="w-64 flex-shrink-0 min-h-screen bg-slate-900 border-r border-slate-800 flex flex-col hidden md:flex">
      <div className="h-16 flex items-center px-6 border-b border-slate-800 cursor-pointer" onClick={() => onViewChange('dashboard')}>
        <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent tracking-tight">
          TRINITY
        </h1>
      </div>
      <nav className="flex-1 px-4 py-6 space-y-1">
        <NavItem id="dashboard" icon={<LayoutDashboard size={20} />} label="儀表板" active={currentView === 'dashboard'} onClick={() => onViewChange('dashboard')} />
        <NavItem id="markets" icon={<TrendingUp size={20} />} label="市場分析" active={currentView === 'markets'} onClick={() => onViewChange('markets')} />
        <NavItem id="strategies" icon={<BarChart3 size={20} />} label="策略模組" active={currentView === 'strategies'} onClick={() => onViewChange('strategies')} />
        <NavItem id="ai-analysis" icon={<Bot size={20} />} label="AI 深度分析" active={currentView === 'ai-analysis'} onClick={() => onViewChange('ai-analysis')} />
        <div className="pt-8 pb-2">
          <p className="px-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">系統</p>
        </div>
        <NavItem id="settings" icon={<Settings size={20} />} label="設定" active={currentView === 'settings'} onClick={() => onViewChange('settings')} />
      </nav>
      <div className="p-4 border-t border-slate-800 text-xs text-slate-500 text-center">
        v1.0.0-beta
      </div>
    </aside>
  );
}

function NavItem({ id, icon, label, active = false, onClick }: { id: string; icon: React.ReactNode; label: string; active?: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
        active 
          ? "bg-blue-500/10 text-blue-400" 
          : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
