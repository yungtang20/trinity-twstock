$files = @(
    @{
        Path = "D:\twse\twse-app\src\components\ui\LoadingSpinner.tsx"
        Content = @'
import React from "react";

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  message?: string;
  className?: string;
}

export function LoadingSpinner({ size = "md", message, className = "" }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: "w-4 h-4",
    md: "w-8 h-8",
    lg: "w-12 h-12",
  };

  return (
    <div className={`flex flex-col items-center justify-center gap-2 ${className}`}>
      <div className={`${sizeClasses[size]} border-2 border-slate-600 border-t-cyan-400 rounded-full animate-spin`} />
      {message && <span className="text-xs text-slate-400">{message}</span>}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`bg-slate-800 rounded animate-pulse ${className}`} />;
}

export function SkeletonCard() {
  return (
    <div className="bg-slate-900 rounded-xl p-4 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div className="bg-slate-900 rounded-xl p-4">
      <div className="flex items-end justify-between h-[200px] gap-1">
        {Array.from({ length: 20 }).map((_, i) => (
          <Skeleton key={i} className="flex-1" style={{ height: "40%" }} />
        ))}
      </div>
    </div>
  );
}
'@
    },
    @{
        Path = "D:\twse\twse-app\src\components\ui\ErrorAlert.tsx"
        Content = @'
import React, { useState } from "react";
import { X, AlertTriangle, AlertCircle, Info } from "lucide-react";

interface ErrorAlertProps {
  type?: "error" | "warning" | "info";
  title?: string;
  message: string;
  dismissible?: boolean;
  onDismiss?: () => void;
  action?: { label: string; onClick: () => void };
}

export function ErrorAlert({
  type = "error",
  title,
  message,
  dismissible = true,
  onDismiss,
  action,
}: ErrorAlertProps) {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  const handleDismiss = () => {
    setVisible(false);
    onDismiss?.();
  };

  const icons = {
    error: <AlertTriangle size={16} />,
    warning: <AlertCircle size={16} />,
    info: <Info size={16} />,
  };

  const colors = {
    error: "bg-red-950/40 border-red-900/60 text-red-300",
    warning: "bg-amber-950/40 border-amber-900/60 text-amber-300",
    info: "bg-blue-950/40 border-blue-900/60 text-blue-300",
  };

  return (
    <div className={`rounded-xl p-4 flex items-start gap-3 border ${colors[type]}`}>
      <span className="shrink-0 mt-0.5">{icons[type]}</span>
      <div className="flex-1 min-w-0">
        {title && <div className="font-semibold text-sm mb-1">{title}</div>}
        <div className="text-sm">{message}</div>
        {action && (
          <button
            onClick={action.onClick}
            className="mt-2 px-3 py-1 bg-white/10 hover:bg-white/20 rounded-lg text-xs font-medium transition-colors"
          >
            {action.label}
          </button>
        )}
      </div>
      {dismissible && (
        <button onClick={handleDismiss} className="shrink-0 p-1 hover:bg-white/10 rounded">
          <X size={14} />
        </button>
      )}
    </div>
  );
}
'@
    },
    @{
        Path = "D:\twse\twse-app\src\components\ui\index.ts"
        Content = @'
export { LoadingSpinner, Skeleton, SkeletonCard, ChartSkeleton } from "./LoadingSpinner";
export { ErrorAlert } from "./ErrorAlert";
'@
    }
)

foreach ($file in $files) {
    $dir = Split-Path $file.Path -Parent
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $file.Content | Out-File -FilePath $file.Path -Encoding UTF8
    Write-Host "Created: $($file.Path)"
}
