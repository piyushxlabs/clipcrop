/**
 * Typed Server-Sent Events (SSE) models and domain interfaces for ClipCrop.
 * Conforms to Vercel AI SDK v6 Data Stream wire format specifications
 * per INTERFACE_OBSERVABILITY_SYSTEM.md Section 2a and AGENT_MASTER_PLAN.md Section 7.
 */

export const STAGE_LABELS: Record<string, string> = {
  ingest_and_validate: "Validating video",
  transcribe_and_segment: "Listening for speech",
  score_candidates: "Ranking candidate segments",
  track_speaker_position: "Finding the speaker",
  confidence_gate: "Evaluating tracking confidence",
  smooth_crop_path: "Smoothing the camera path",
  render_and_export: "Rendering clips and exporting timeline data",
  aggregate_and_terminate: "Finalizing summary and deliverables",
};

export type PipelineStageId =
  | "ingest_and_validate"
  | "transcribe_and_segment"
  | "score_candidates"
  | "track_speaker_position"
  | "confidence_gate"
  | "smooth_crop_path"
  | "render_and_export"
  | "aggregate_and_terminate";

export interface DataStageStartEvent {
  type: "data-stage-start";
  stage: string;
  label: string;
}

export interface DataStageProgressEvent {
  type: "data-stage-progress";
  stage: string;
  detail: Record<string, unknown> | string;
}

export interface ToolInputAvailableEvent {
  type: "tool-input-available";
  toolCallId: string;
  toolName: string;
  input: Record<string, unknown>;
}

export interface ToolOutputAvailableEvent {
  type: "tool-output-available";
  toolCallId: string;
  toolName: string;
  output: Record<string, unknown>;
}

export interface DataStateUpdateEvent {
  type: "data-state-update";
  field: string;
  reducer:
    | "append-only"
    | "merge-by-key"
    | "last-write-wins"
    | "immutable-after-init"
    | "append_only"
    | "merge_by_key"
    | "last_write_wins"
    | "immutable_after_init";
  key?: string | null;
  value: unknown;
}

export interface ErrorEvent {
  type: "error";
  code: string;
  message: string;
  recoverable: boolean;
}

export interface DataRunEndEvent {
  type: "data-run-end";
  reason: "success" | "interrupted" | "error" | "no_deliverables";
  deliverables_count?: number | null;
  skipped_count?: number | null;
}

export type StreamEvent =
  | DataStageStartEvent
  | DataStageProgressEvent
  | ToolInputAvailableEvent
  | ToolOutputAvailableEvent
  | DataStateUpdateEvent
  | ErrorEvent
  | DataRunEndEvent;

// Domain Models

export interface FileRef {
  path: string;
  duration_seconds?: number | null;
  file_size_bytes?: number | null;
  width?: number | null;
  height?: number | null;
  fps?: number | null;
  has_video_track?: boolean | null;
  has_audio_track?: boolean | null;
  segment_id?: string | null;
  keyframe_count?: number | null;
  format?: string | null;
}

export interface TranscriptSegment {
  start_ms: number;
  end_ms: number;
  text: string;
}

export interface SpeechSpan {
  start_seconds: number;
  end_seconds: number;
}

export interface CandidateSegment {
  segment_id: string;
  start_ms: number;
  end_ms: number;
  score: number;
  pause_pattern_score: number;
  energy_peak_score: number;
  speaking_rate_variance_score: number;
  keyword_density_score: number;
  rank: number;
}

export interface BoundingBox {
  origin_x: number;
  origin_y: number;
  width: number;
  height: number;
}

export interface FramePosition {
  timestamp_ms: number;
  bounding_box: BoundingBox;
  detection_score: number;
}

export interface TrackingResult {
  segment_id: string;
  success: boolean;
  per_frame_positions: FramePosition[];
  segment_confidence: number;
  error?: string | null;
}

export interface GateDecision {
  segment_id: string;
  tracking_confidence: number;
  threshold_used: number;
  decision: "render" | "skip";
  reason: string;
}

export interface CropKeyframe {
  timestamp_ms: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface SmoothedPath {
  segment_id: string;
  success: boolean;
  crop_keyframes: CropKeyframe[];
  error?: string | null;
}

export interface SkipRecord {
  segment_id: string;
  tracking_confidence: number;
  threshold_used: number;
  reason: string;
  timestamp_ms?: number | null;
}

export interface ErrorRecord {
  stage: string;
  message: string;
  details: Record<string, unknown>;
  timestamp_ms?: number | null;
  recoverable: boolean;
}

export interface StageState {
  id: PipelineStageId;
  label: string;
  status: "pending" | "active" | "completed" | "failed" | "skipped";
  detail?: string | Record<string, unknown>;
  toolInputs: Array<{ toolName: string; input: Record<string, unknown> }>;
  toolOutputs: Array<{ toolName: string; output: Record<string, unknown> }>;
}

export interface PipelineState {
  sessionId: string | null;
  runStatus: "idle" | "uploading" | "running" | "completed" | "interrupted" | "failed";
  currentStage: PipelineStageId | null;
  sourceVideo: FileRef | null;
  transcriptSegments: TranscriptSegment[];
  vadSegments: SpeechSpan[];
  candidateSegments: CandidateSegment[];
  trackingResults: Record<string, TrackingResult>;
  confidenceGateResults: Record<string, GateDecision>;
  cropPaths: Record<string, SmoothedPath>;
  renderedClips: FileRef[];
  cropPathExports: FileRef[];
  skippedSegments: SkipRecord[];
  errorLogs: ErrorRecord[];
  stages: Record<PipelineStageId, StageState>;
  systemError: { code: string; message: string } | null;
  elapsedSeconds: number;
}
