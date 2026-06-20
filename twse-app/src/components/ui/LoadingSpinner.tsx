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
