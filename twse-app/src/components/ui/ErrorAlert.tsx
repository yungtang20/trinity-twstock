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
