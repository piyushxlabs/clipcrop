import React, { useState } from "react";
import {
  PipelineStageId,
  StageState,
  FileRef,
  TranscriptSegment,
  SpeechSpan,
  CandidateSegment,
  GateDecision,
  TrackingResult,
} from "../types/events";
import { SourceVideoCard } from "./SourceVideoCard";
import { TranscriptView } from "./TranscriptView";
import { VadTimeline } from "./VadTimeline";
import { CandidateRankingTable } from "./CandidateRankingTable";
import { ConfidenceBadge } from "./ConfidenceBadge";

interface StageTimelineProps {
  stages: Record<PipelineStageId, StageState>;
  currentStage: PipelineStageId | null;
  elapsedSeconds: number;
  runStatus?: string;
  sourceVideo: FileRef | null;
  transcriptSegments: TranscriptSegment[];
  vadSegments: SpeechSpan[];
  candidateSegments: CandidateSegment[];
  confidenceGateResults: Record<string, GateDecision>;
  trackingResults: Record<string, TrackingResult>;
}

const STAGE_ORDER: PipelineStageId[] = [
  "ingest_and_validate",
  "transcribe_and_segment",
  "score_candidates",
  "track_speaker_position",
  "confidence_gate",
  "smooth_crop_path",
  "render_and_export",
  "aggregate_and_terminate",
];

export const StageTimeline: React.FC<StageTimelineProps> = ({
  stages,
  currentStage,
  elapsedSeconds,
  runStatus,
  sourceVideo,
  transcriptSegments,
  vadSegments,
  candidateSegments,
  confidenceGateResults,
  trackingResults,
}) => {
  const [expandedStages, setExpandedStages] = useState<Record<string, boolean>>({});

  const toggleStageExpand = (stageId: string) => {
    setExpandedStages((prev) => ({
      ...prev,
      [stageId]: !prev[stageId],
    }));
  };

  const isFinished = ["completed", "failed", "interrupted"].includes(runStatus || "");

  return (
    <div id="stage-timeline" className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-slate-800/80 p-5 shadow-xl space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
              Pipeline Execution Sequence
            </h3>
            <p className="text-xs text-slate-400">Deterministic 8-stage video reframing workflow</p>
          </div>
        </div>
        {currentStage && !isFinished && (
          <div className="flex items-center space-x-2 text-xs font-mono text-indigo-400 bg-indigo-950/40 px-3 py-1 rounded-full border border-indigo-900/50">
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping" />
            <span>Active • {elapsedSeconds}s</span>
          </div>
        )}
      </div>

      <div className="relative space-y-3 before:absolute before:left-4 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
        {STAGE_ORDER.map((stageId, index) => {
          const stage = stages[stageId];
          const isCompleted =
            (runStatus === "completed" && stage?.status !== "failed") ||
            stage?.status === "completed";
          const isFailed = stage?.status === "failed";
          const isActive =
            !isFinished && !isCompleted && (currentStage === stageId || stage?.status === "active");
          const isExpanded = !!expandedStages[stageId];

          return (
            <div
              key={stageId}
              id={`stage-row-${stageId}`}
              className={`relative pl-10 rounded-xl transition-all ${
                isActive
                  ? "bg-indigo-950/20 border border-indigo-500/30 p-3"
                  : isCompleted
                  ? "bg-slate-900/30 border border-slate-800/40 p-3"
                  : isFailed
                  ? "bg-rose-950/20 border border-rose-500/30 p-3"
                  : "opacity-60 p-2.5"
              }`}
            >
              {/* Status Circle Node */}
              <div
                className={`absolute left-2.5 top-3.5 -translate-x-1/2 w-5 h-5 rounded-full flex items-center justify-center border text-[10px] font-bold z-10 ${
                  isCompleted
                    ? "bg-emerald-500 border-emerald-400 text-slate-950"
                    : isActive
                    ? "bg-indigo-600 border-indigo-400 text-white shadow-md shadow-indigo-500/50 animate-pulse"
                    : isFailed
                    ? "bg-rose-500 border-rose-400 text-white"
                    : "bg-slate-900 border-slate-700 text-slate-500"
                }`}
              >
                {isCompleted ? (
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                ) : isFailed ? (
                  "✕"
                ) : (
                  index + 1
                )}
              </div>

              {/* Stage Header */}
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center space-x-2">
                    <h4
                      className={`text-xs font-semibold ${
                        isActive
                          ? "text-indigo-300"
                          : isCompleted
                          ? "text-slate-200"
                          : isFailed
                          ? "text-rose-300"
                          : "text-slate-500"
                      }`}
                    >
                      Stage {index + 1}: {stage?.label || stageId}
                    </h4>
                    {isActive && (
                      <span className="text-[10px] uppercase font-mono px-2 py-0.2 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                        In Progress
                      </span>
                    )}
                  </div>
                  {stage?.detail && (
                    <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                      {typeof stage.detail === "string" ? stage.detail : JSON.stringify(stage.detail)}
                    </p>
                  )}
                </div>

                <div className="flex items-center space-x-2">
                  {/* Inspect Details Button */}
                  {(stage?.toolInputs?.length > 0 || stage?.toolOutputs?.length > 0) && (
                    <button
                      type="button"
                      id={`stage-expand-${stageId}`}
                      onClick={() => toggleStageExpand(stageId)}
                      className="text-[11px] text-slate-400 hover:text-slate-200 font-mono transition-colors cursor-pointer"
                    >
                      {isExpanded ? "Hide Details" : "Details"}
                    </button>
                  )}
                </div>
              </div>

              {/* Generative UI Components inline with respective stages */}
              {stageId === "ingest_and_validate" && sourceVideo && (
                <div className="mt-3">
                  <SourceVideoCard source={sourceVideo} />
                </div>
              )}

              {stageId === "transcribe_and_segment" && (
                <div className="mt-3 space-y-3">
                  {transcriptSegments.length > 0 && <TranscriptView segments={transcriptSegments} />}
                  {vadSegments.length > 0 && (
                    <VadTimeline spans={vadSegments} totalDurationSeconds={sourceVideo?.duration_seconds} />
                  )}
                </div>
              )}

              {stageId === "score_candidates" && candidateSegments.length > 0 && (
                <div className="mt-3">
                  <CandidateRankingTable candidates={candidateSegments} />
                </div>
              )}

              {/* Per-segment Tracking & Gate outcomes */}
              {stageId === "track_speaker_position" && Object.keys(trackingResults).length > 0 && (
                <div className="mt-3 space-y-1.5">
                  <div className="text-[11px] font-semibold text-slate-400">
                    Speaker Detection Tracking:
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(trackingResults).map(([segId, track]) => (
                      <div
                        key={segId}
                        className="flex items-center space-x-2 bg-slate-950/60 p-1.5 px-2.5 rounded-lg border border-slate-800 text-xs font-mono"
                      >
                        <span className="font-medium text-indigo-400">{segId}:</span>
                        <span className="text-slate-300">
                          {track.per_frame_positions?.length || 0} frames tracked
                        </span>
                        <span className="text-[11px] text-slate-500">
                          ({(track.segment_confidence * 100).toFixed(0)}%)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {stageId === "confidence_gate" && Object.keys(confidenceGateResults).length > 0 && (
                <div className="mt-3 space-y-2">
                  <div className="text-[11px] font-semibold text-slate-400">
                    Segment Confidence Decisions:
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(confidenceGateResults).map(([segId, decision]) => (
                      <div
                        key={segId}
                        className="flex items-center space-x-2 bg-slate-950/60 p-1.5 px-2.5 rounded-lg border border-slate-800"
                      >
                        <span className="text-xs font-mono font-medium text-slate-300">{segId}:</span>
                        <ConfidenceBadge decision={decision} segmentId={segId} />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Expandable Tool Input & Output Drawers */}
              {isExpanded && (
                <div
                  id={`stage-details-${stageId}`}
                  className="mt-3 p-3 bg-slate-950/80 rounded-lg border border-slate-800/80 space-y-2 text-xs font-mono"
                >
                  {stage.toolInputs.map((item, idx) => (
                    <div key={`input-${idx}`} className="space-y-1">
                      <span className="text-indigo-400 text-[10px] uppercase font-bold">
                        Tool Input [{item.toolName}]:
                      </span>
                      <pre className="p-2 rounded bg-slate-900 border border-slate-800 text-[11px] text-slate-300 overflow-x-auto max-h-32">
                        {JSON.stringify(item.input, null, 2)}
                      </pre>
                    </div>
                  ))}

                  {stage.toolOutputs.map((item, idx) => (
                    <div key={`output-${idx}`} className="space-y-1">
                      <span className="text-emerald-400 text-[10px] uppercase font-bold">
                        Tool Output [{item.toolName}]:
                      </span>
                      <pre className="p-2 rounded bg-slate-900 border border-slate-800 text-[11px] text-slate-300 overflow-x-auto max-h-32">
                        {JSON.stringify(item.output, null, 2)}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
