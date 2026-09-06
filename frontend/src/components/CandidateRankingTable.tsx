import React, { useState } from "react";
import { CandidateSegment } from "../types/events";

interface CandidateRankingTableProps {
  candidates: CandidateSegment[];
  onSelectCandidate?: (segmentId: string) => void;
  selectedSegmentId?: string | null;
}

function formatDurationMs(ms: number): string {
  const sec = (ms / 1000).toFixed(1);
  return `${sec}s`;
}

function formatRange(startMs: number, endMs: number): string {
  const startSec = (startMs / 1000).toFixed(1);
  const endSec = (endMs / 1000).toFixed(1);
  return `${startSec}s – ${endSec}s`;
}

export const CandidateRankingTable: React.FC<CandidateRankingTableProps> = ({
  candidates,
  onSelectCandidate,
  selectedSegmentId,
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (!candidates || candidates.length === 0) {
    return null;
  }

  const sorted = [...candidates].sort((a, b) => a.rank - b.rank);

  return (
    <div id="candidate-ranking-table" className="bg-slate-900/70 backdrop-blur-md rounded-xl border border-slate-800/80 p-4 shadow-lg space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="w-7 h-7 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          </div>
          <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Ranked Candidate Segments
          </h4>
        </div>
        <span className="text-xs font-mono text-slate-400 bg-slate-800/80 px-2.5 py-0.5 rounded-full border border-slate-700/60">
          {candidates.length} candidates
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-800 text-slate-500 uppercase text-[10px] font-mono tracking-wider">
              <th className="py-2 px-3">Rank</th>
              <th className="py-2 px-3">Segment ID</th>
              <th className="py-2 px-3">Time Range</th>
              <th className="py-2 px-3">Duration</th>
              <th className="py-2 px-3 text-right">Composite Score</th>
              <th className="py-2 px-3 text-center">Breakdown</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {sorted.map((cand) => {
              const isExpanded = expandedId === cand.segment_id;
              const isSelected = selectedSegmentId === cand.segment_id;

              return (
                <React.Fragment key={cand.segment_id}>
                  <tr
                    id={`candidate-row-${cand.segment_id}`}
                    onClick={() => onSelectCandidate?.(cand.segment_id)}
                    className={`transition-colors cursor-pointer ${
                      isSelected
                        ? "bg-indigo-950/40 text-indigo-200"
                        : "hover:bg-slate-800/40 text-slate-300"
                    }`}
                  >
                    <td className="py-2.5 px-3 font-semibold text-indigo-400">
                      #{cand.rank}
                    </td>
                    <td className="py-2.5 px-3 font-medium text-slate-200">
                      {cand.segment_id}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">
                      {formatRange(cand.start_ms, cand.end_ms)}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">
                      {formatDurationMs(cand.end_ms - cand.start_ms)}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <span className="font-bold text-slate-100 bg-slate-800 px-2 py-0.5 rounded border border-slate-700/50">
                        {cand.score.toFixed(3)}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <button
                        type="button"
                        id={`candidate-expand-${cand.segment_id}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setExpandedId(isExpanded ? null : cand.segment_id);
                        }}
                        className="text-[11px] text-indigo-400 hover:text-indigo-300 font-sans cursor-pointer underline underline-offset-2"
                      >
                        {isExpanded ? "Hide" : "Inspect"}
                      </button>
                    </td>
                  </tr>

                  {/* Factor breakdown row */}
                  {isExpanded && (
                    <tr id={`candidate-breakdown-${cand.segment_id}`} className="bg-slate-950/80">
                      <td colSpan={6} className="p-3 font-sans">
                        <div className="space-y-2 border-l-2 border-indigo-500 pl-3 py-1">
                          <div className="text-[11px] font-semibold text-slate-300">
                            Heuristic Component Scores Breakdown:
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                            <div className="bg-slate-900 p-2 rounded border border-slate-800">
                              <span className="text-slate-500 block text-[10px]">Pause Pattern</span>
                              <span className="text-cyan-400 font-semibold">{cand.pause_pattern_score.toFixed(3)}</span>
                            </div>
                            <div className="bg-slate-900 p-2 rounded border border-slate-800">
                              <span className="text-slate-500 block text-[10px]">Energy Peak</span>
                              <span className="text-amber-400 font-semibold">{cand.energy_peak_score.toFixed(3)}</span>
                            </div>
                            <div className="bg-slate-900 p-2 rounded border border-slate-800">
                              <span className="text-slate-500 block text-[10px]">Speech Rate Var</span>
                              <span className="text-emerald-400 font-semibold">{cand.speaking_rate_variance_score.toFixed(3)}</span>
                            </div>
                            <div className="bg-slate-900 p-2 rounded border border-slate-800">
                              <span className="text-slate-500 block text-[10px]">Keyword Density</span>
                              <span className="text-violet-400 font-semibold">{cand.keyword_density_score.toFixed(3)}</span>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
