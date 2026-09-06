import React, { useState } from "react";
import { TranscriptSegment } from "../types/events";

interface TranscriptViewProps {
  segments: TranscriptSegment[];
}

function formatMs(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  const milli = String(ms % 1000).padStart(3, "0");
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${milli}`;
}

export const TranscriptView: React.FC<TranscriptViewProps> = ({ segments }) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  if (!segments || segments.length === 0) {
    return (
      <div id="transcript-view-empty" className="p-3 bg-slate-950/40 rounded-lg border border-slate-800/40 text-xs text-slate-500 italic">
        No transcript available
      </div>
    );
  }

  const previewCount = 3;
  const displayed = isExpanded ? segments : segments.slice(0, previewCount);

  return (
    <div id="transcript-view" className="bg-slate-950/60 rounded-lg border border-slate-800/60 p-3.5 space-y-2">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center space-x-2">
          <span className="font-semibold text-slate-300">Speech Transcript</span>
          <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono text-[11px]">
            {segments.length} {segments.length === 1 ? "segment" : "segments"}
          </span>
        </div>
        {segments.length > previewCount && (
          <button
            id="transcript-toggle-expand"
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-xs font-medium text-indigo-400 hover:text-indigo-300 transition-colors cursor-pointer"
          >
            {isExpanded ? "Show Less" : `Show All (${segments.length})`}
          </button>
        )}
      </div>

      <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
        {displayed.map((seg, idx) => {
          const isSelected = selectedIdx === idx;
          return (
            <div
              key={`${seg.start_ms}-${idx}`}
              id={`transcript-segment-${idx}`}
              onClick={() => setSelectedIdx(isSelected ? null : idx)}
              className={`p-2 rounded-md transition-all text-xs cursor-pointer border ${
                isSelected
                  ? "bg-indigo-950/40 border-indigo-500/40 text-slate-100"
                  : "bg-slate-900/40 border-slate-800/40 hover:bg-slate-900 hover:border-slate-700/60 text-slate-300"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-[10px] text-slate-500">
                  {formatMs(seg.start_ms)} → {formatMs(seg.end_ms)}
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                  {((seg.end_ms - seg.start_ms) / 1000).toFixed(1)}s
                </span>
              </div>
              <p className="text-slate-200 leading-relaxed">{seg.text}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
