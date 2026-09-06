import React from "react";

interface SystemMessageBannerProps {
  error: { code: string; message: string } | null;
  onReset?: () => void;
}

const ERROR_DESCRIPTIONS: Record<string, { title: string; actionLabel: string }> = {
  invalid_source: {
    title: "Media Validation Failed",
    actionLabel: "Upload a different video",
  },
  zero_candidates: {
    title: "No Candidate Segments",
    actionLabel: "Try another video with clearer speech",
  },
  time_budget_exhausted: {
    title: "Time Budget Reached",
    actionLabel: "Review completed clips or re-run",
  },
  stream_interrupted: {
    title: "Connection Interrupted",
    actionLabel: "Reconnect or re-upload",
  },
};

export const SystemMessageBanner: React.FC<SystemMessageBannerProps> = ({ error, onReset }) => {
  if (!error) return null;

  const info = ERROR_DESCRIPTIONS[error.code] || {
    title: "Pipeline Execution Error",
    actionLabel: "Upload a different file",
  };

  return (
    <div
      id="system-message-banner"
      className="bg-rose-950/40 border border-rose-500/50 rounded-2xl p-5 shadow-2xl backdrop-blur-md space-y-3 animate-fade-in"
    >
      <div className="flex items-start space-x-3.5">
        <div className="w-9 h-9 rounded-xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400 shrink-0">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div className="space-y-1 flex-1">
          <div className="flex items-center space-x-2">
            <h3 className="text-sm font-bold text-rose-200 uppercase tracking-wider">
              {info.title}
            </h3>
            <span className="font-mono text-[11px] text-rose-400 bg-rose-900/50 px-2 py-0.2 rounded border border-rose-700/50">
              {error.code}
            </span>
          </div>
          <p className="text-xs text-rose-300 leading-relaxed">
            {error.message}
          </p>
        </div>
      </div>

      {onReset && (
        <div className="pt-2 border-t border-rose-900/40 flex justify-end">
          <button
            type="button"
            id="system-banner-reset-btn"
            onClick={onReset}
            className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold shadow-md shadow-rose-600/30 transition-all cursor-pointer"
          >
            {info.actionLabel}
          </button>
        </div>
      )}
    </div>
  );
};
