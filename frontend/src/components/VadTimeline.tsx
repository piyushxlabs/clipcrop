import React, { useState } from "react";
import { SpeechSpan } from "../types/events";

interface VadTimelineProps {
  spans: SpeechSpan[];
  totalDurationSeconds?: number | null;
}

export const VadTimeline: React.FC<VadTimelineProps> = ({ spans, totalDurationSeconds }) => {
  const [hoveredSpan, setHoveredSpan] = useState<SpeechSpan | null>(null);

  if (!spans || spans.length === 0) {
    return (
      <div id="vad-timeline-empty" className="p-3 bg-slate-950/40 rounded-lg border border-slate-800/40 text-xs">
        <div className="h-4 w-full bg-slate-800/50 rounded flex items-center justify-center text-[10px] text-slate-500 font-mono">
          NO SPEECH DETECTED
        </div>
        <p className="text-[11px] text-slate-500 italic mt-1.5">
          No voice activity detected in audio track.
        </p>
      </div>
    );
  }

  // Calculate total duration from spans or source video duration
  const maxSpanEnd = spans.reduce((max, s) => Math.max(max, s.end_seconds), 0);
  const duration = totalDurationSeconds && totalDurationSeconds > 0 ? totalDurationSeconds : Math.max(maxSpanEnd, 1.0);

  const totalSpeechDuration = spans.reduce((acc, s) => acc + (s.end_seconds - s.start_seconds), 0);
  const speechRatio = ((totalSpeechDuration / duration) * 100).toFixed(0);

  return (
    <div id="vad-timeline" className="bg-slate-950/60 rounded-lg border border-slate-800/60 p-3.5 space-y-2.5">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center space-x-2">
          <span className="font-semibold text-slate-300">Speech & Pause Map (VAD)</span>
          <span className="px-2 py-0.5 rounded-full bg-cyan-950/50 border border-cyan-800/40 text-cyan-400 font-mono text-[11px]">
            {spans.length} speech spans ({speechRatio}% active)
          </span>
        </div>
        {hoveredSpan && (
          <span className="font-mono text-[11px] text-cyan-300 bg-cyan-950/70 px-2 py-0.5 rounded border border-cyan-800/60">
            {hoveredSpan.start_seconds.toFixed(1)}s → {hoveredSpan.end_seconds.toFixed(1)}s ({(hoveredSpan.end_seconds - hoveredSpan.start_seconds).toFixed(1)}s)
          </span>
        )}
      </div>

      {/* Horizontal timeline bar */}
      <div className="relative w-full h-7 bg-slate-900 rounded-md overflow-hidden border border-slate-800 flex items-center">
        {/* Background pause track */}
        <div className="absolute inset-0 bg-slate-900/90" />

        {/* Speech filled spans */}
        {spans.map((span, idx) => {
          const leftPercent = Math.min(100, Math.max(0, (span.start_seconds / duration) * 100));
          const widthPercent = Math.min(100 - leftPercent, Math.max(0.5, ((span.end_seconds - span.start_seconds) / duration) * 100));

          return (
            <div
              key={`${span.start_seconds}-${idx}`}
              id={`vad-span-${idx}`}
              onMouseEnter={() => setHoveredSpan(span)}
              onMouseLeave={() => setHoveredSpan(null)}
              style={{ left: `${leftPercent}%`, width: `${widthPercent}%` }}
              className="absolute top-1 bottom-1 rounded-sm bg-gradient-to-r from-cyan-500 to-indigo-500 hover:from-cyan-400 hover:to-indigo-400 opacity-85 hover:opacity-100 transition-opacity cursor-pointer shadow-sm shadow-cyan-500/20"
              title={`Speech: ${span.start_seconds.toFixed(1)}s - ${span.end_seconds.toFixed(1)}s`}
            />
          );
        })}
      </div>

      <div className="flex justify-between text-[10px] font-mono text-slate-500 px-0.5">
        <span>0.0s</span>
        <span>{(duration / 2).toFixed(1)}s</span>
        <span>{duration.toFixed(1)}s</span>
      </div>
    </div>
  );
};
