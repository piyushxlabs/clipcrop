import React, { useState } from "react";
import { GateDecision } from "../types/events";

interface ConfidenceBadgeProps {
  decision: GateDecision | null | undefined;
  segmentId?: string;
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ decision, segmentId }) => {
  const [showTooltip, setShowTooltip] = useState<boolean>(false);

  if (!decision) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-slate-500">
        Evaluating…
      </span>
    );
  }

  const isRender = decision.decision === "render";
  const badgeId = `confidence-badge-${segmentId || decision.segment_id}`;

  return (
    <div className="relative inline-block" onMouseEnter={() => setShowTooltip(true)} onMouseLeave={() => setShowTooltip(false)}>
      <button
        type="button"
        id={badgeId}
        onClick={() => setShowTooltip(!showTooltip)}
        className={`inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold cursor-pointer border transition-all ${
          isRender
            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20"
            : "bg-amber-500/10 text-amber-400 border-amber-500/30 hover:bg-amber-500/20"
        }`}
      >
        <span
          className={`w-1.5 h-1.5 rounded-full ${isRender ? "bg-emerald-400" : "bg-amber-400"}`}
        />
        <span>{isRender ? "Rendering" : "Skipped"}</span>
        <span className="text-[10px] font-mono opacity-80 pl-0.5">
          ({(decision.tracking_confidence * 100).toFixed(0)}%)
        </span>
      </button>

      {showTooltip && (
        <div
          id={`${badgeId}-tooltip`}
          className="absolute z-30 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 bg-slate-900 border border-slate-700 rounded-lg shadow-xl text-xs text-slate-200 pointer-events-none"
        >
          <div className="font-semibold text-slate-100 flex items-center justify-between pb-1 border-b border-slate-800 mb-1.5">
            <span>Confidence Gate</span>
            <span className={`text-[10px] uppercase px-1.5 py-0.2 rounded font-mono ${isRender ? "text-emerald-400 bg-emerald-950" : "text-amber-400 bg-amber-950"}`}>
              {decision.decision}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-1 font-mono text-[11px] mb-1.5">
            <div>
              <span className="text-slate-400 block text-[10px]">Confidence:</span>
              <span className="text-slate-100 font-bold">{decision.tracking_confidence.toFixed(3)}</span>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px]">Threshold:</span>
              <span className="text-slate-100 font-bold">{decision.threshold_used.toFixed(3)}</span>
            </div>
          </div>
          <p className="text-[11px] text-slate-400 leading-tight">
            {decision.reason}
          </p>
          <div className="w-2 h-2 bg-slate-900 border-r border-b border-slate-700 rotate-45 absolute -bottom-1 left-1/2 -translate-x-1/2" />
        </div>
      )}
    </div>
  );
};
