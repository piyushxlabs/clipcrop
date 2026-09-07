import { useState, useCallback, useRef, useEffect } from "react";
import {
  StreamEvent,
  PipelineState,
  PipelineStageId,
  StageState,
  STAGE_LABELS,
  FileRef,
  CandidateSegment,
  GateDecision,
  TrackingResult,
  SmoothedPath,
  SkipRecord,
  ErrorRecord,
  TranscriptSegment,
  SpeechSpan,
} from "../types/events";

const ORDERED_STAGES: PipelineStageId[] = [
  "ingest_and_validate",
  "transcribe_and_segment",
  "score_candidates",
  "track_speaker_position",
  "confidence_gate",
  "smooth_crop_path",
  "render_and_export",
  "aggregate_and_terminate",
];

export function createInitialStages(): Record<PipelineStageId, StageState> {
  const stages: Partial<Record<PipelineStageId, StageState>> = {};
  for (const id of ORDERED_STAGES) {
    stages[id] = {
      id,
      label: STAGE_LABELS[id] || id,
      status: "pending",
      toolInputs: [],
      toolOutputs: [],
    };
  }
  return stages as Record<PipelineStageId, StageState>;
}

export function createInitialState(sessionId: string | null = null): PipelineState {
  return {
    sessionId,
    runStatus: sessionId ? "running" : "idle",
    currentStage: null,
    sourceVideo: null,
    transcriptSegments: [],
    vadSegments: [],
    candidateSegments: [],
    trackingResults: {},
    confidenceGateResults: {},
    cropPaths: {},
    renderedClips: [],
    cropPathExports: [],
    skippedSegments: [],
    errorLogs: [],
    stages: createInitialStages(),
    systemError: null,
    elapsedSeconds: 0,
  };
}

export function usePipelineStream() {
  const [state, setState] = useState<PipelineState>(() => createInitialState());
  const abortControllerRef = useRef<AbortController | null>(null);
  const timerRef = useRef<number | null>(null);

  // Stop running timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleEvent = useCallback((event: StreamEvent) => {
    setState((prev) => {
      const next = { ...prev };

      switch (event.type) {
        case "data-stage-start": {
          const stageId = event.stage as PipelineStageId;
          next.currentStage = stageId;
          const nextStages = { ...next.stages };

          // Mark previous stages as completed if they were active or pending
          let found = false;
          for (const sId of ORDERED_STAGES) {
            if (sId === stageId) {
              found = true;
              nextStages[sId] = {
                ...nextStages[sId],
                status: "active",
                label: event.label || STAGE_LABELS[sId] || sId,
              };
            } else if (!found && nextStages[sId].status === "active") {
              nextStages[sId] = {
                ...nextStages[sId],
                status: "completed",
              };
            }
          }
          next.stages = nextStages;
          break;
        }

        case "data-stage-progress": {
          const stageId = event.stage as PipelineStageId;
          if (next.stages[stageId]) {
            next.stages = {
              ...next.stages,
              [stageId]: {
                ...next.stages[stageId],
                detail: event.detail,
              },
            };
          }
          break;
        }

        case "tool-input-available": {
          // Find matching stage or current stage
          const current = next.currentStage;
          if (current && next.stages[current]) {
            next.stages = {
              ...next.stages,
              [current]: {
                ...next.stages[current],
                toolInputs: [
                  ...next.stages[current].toolInputs,
                  { toolName: event.toolName, input: event.input },
                ],
              },
            };
          }
          break;
        }

        case "tool-output-available": {
          const current = next.currentStage;
          if (current && next.stages[current]) {
            next.stages = {
              ...next.stages,
              [current]: {
                ...next.stages[current],
                toolOutputs: [
                  ...next.stages[current].toolOutputs,
                  { toolName: event.toolName, output: event.output },
                ],
              },
            };
          }

          // Special mapping for decode_and_validate_source output
          if (event.toolName === "decode_and_validate_source" && event.output?.success) {
            next.sourceVideo = {
              path: String(event.output.output_file_path || event.output.path || "source.mp4"),
              duration_seconds: (event.output.duration_seconds as number) ?? null,
              width: (event.output.width as number) ?? null,
              height: (event.output.height as number) ?? null,
              fps: (event.output.fps as number) ?? null,
              has_video_track: Boolean(event.output.has_video_track),
              has_audio_track: Boolean(event.output.has_audio_track),
            };
          }
          break;
        }

        case "data-state-update": {
          const field = event.field;
          const val = event.value;

          if (field === "source_video") {
            next.sourceVideo = val as FileRef;
          } else if (field === "transcript_segments") {
            next.transcriptSegments = Array.isArray(val)
              ? (val as TranscriptSegment[])
              : [...next.transcriptSegments, val as TranscriptSegment];
          } else if (field === "vad_segments") {
            next.vadSegments = Array.isArray(val)
              ? (val as SpeechSpan[])
              : [...next.vadSegments, val as SpeechSpan];
          } else if (field === "candidate_segments") {
            next.candidateSegments = Array.isArray(val) ? (val as CandidateSegment[]) : [];
          } else if (field === "confidence_gate_results") {
            const key = event.key || (val as GateDecision)?.segment_id;
            if (key) {
              next.confidenceGateResults = {
                ...next.confidenceGateResults,
                [key]: val as GateDecision,
              };
            }
          } else if (field === "tracking_results") {
            const key = event.key || (val as TrackingResult)?.segment_id;
            if (key) {
              next.trackingResults = {
                ...next.trackingResults,
                [key]: val as TrackingResult,
              };
            }
          } else if (field === "crop_paths") {
            const key = event.key || (val as SmoothedPath)?.segment_id;
            if (key) {
              next.cropPaths = {
                ...next.cropPaths,
                [key]: val as SmoothedPath,
              };
            }
          } else if (field === "rendered_clips") {
            const item = val as FileRef;
            if (!next.renderedClips.some((c) => c.path === item.path)) {
              next.renderedClips = [...next.renderedClips, item];
            }
          } else if (field === "crop_path_exports") {
            const item = val as FileRef;
            if (!next.cropPathExports.some((c) => c.path === item.path)) {
              next.cropPathExports = [...next.cropPathExports, item];
            }
          } else if (field === "skipped_segments") {
            next.skippedSegments = [...next.skippedSegments, val as SkipRecord];
          } else if (field === "error_logs") {
            next.errorLogs = [...next.errorLogs, val as ErrorRecord];
          }
          break;
        }

        case "error": {
          next.systemError = { code: event.code, message: event.message };
          next.runStatus = "failed";
          if (next.currentStage && next.stages[next.currentStage]) {
            next.stages = {
              ...next.stages,
              [next.currentStage]: {
                ...next.stages[next.currentStage],
                status: "failed",
              },
            };
          }
          break;
        }

        case "data-run-end": {
          const status =
            event.reason === "interrupted"
              ? "interrupted"
              : event.reason === "error"
              ? "failed"
              : "completed";
          next.runStatus = status;
          next.currentStage = null;

          const nextStages = { ...next.stages };
          if (status === "completed") {
            // Explicitly mark all pipeline stages as completed
            for (const sId of ORDERED_STAGES) {
              if (nextStages[sId]) {
                nextStages[sId] = {
                  ...nextStages[sId],
                  status: nextStages[sId].status === "failed" ? "failed" : "completed",
                };
              }
            }
          } else if (prev.currentStage && nextStages[prev.currentStage]) {
            nextStages[prev.currentStage] = {
              ...nextStages[prev.currentStage],
              status: status === "failed" ? "failed" : "completed",
            };
          }
          next.stages = nextStages;
          break;
        }
      }

      return next;
    });
  }, []);

  const connectToStream = useCallback(
    async (runId: string, apiBaseUrl: string = "") => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      setState(createInitialState(runId));

      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
      }
      timerRef.current = window.setInterval(() => {
        setState((prev) => {
          if (prev.runStatus === "running") {
            return { ...prev, elapsedSeconds: prev.elapsedSeconds + 1 };
          }
          return prev;
        });
      }, 1000);

      const streamUrl = `${apiBaseUrl}/runs/${runId}/stream`;

      try {
        const response = await fetch(streamUrl, {
          signal: abortController.signal,
          headers: {
            Accept: "text/event-stream",
          },
        });

        if (!response.ok || !response.body) {
          throw new Error(`Failed to connect to stream: ${response.status} ${response.statusText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          // Keep incomplete line in buffer
          buffer = lines.pop() || "";

          for (const block of lines) {
            const trimmed = block.trim();
            if (!trimmed) continue;

            // Handle potential multi-line data blocks
            for (const line of trimmed.split("\n")) {
              if (line.startsWith("data: ")) {
                try {
                  const jsonStr = line.slice(6).trim();
                  const parsed = JSON.parse(jsonStr) as StreamEvent;
                  handleEvent(parsed);
                } catch (e) {
                  console.warn("Error parsing SSE event json:", line, e);
                }
              }
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
        console.error("Stream connection error:", err);
        setState((prev) => {
          if (prev.runStatus === "running") {
            return {
              ...prev,
              runStatus: "interrupted",
              systemError: {
                code: "stream_interrupted",
                message: "Connection to pipeline server was lost. Please re-upload or retry.",
              },
            };
          }
          return prev;
        });
      } finally {
        if (timerRef.current !== null) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }
      }
    },
    [handleEvent]
  );

  const cancelRun = useCallback(async (apiBaseUrl: string = "") => {
    setState((prev) => {
      if (!prev.sessionId) return prev;
      const runId = prev.sessionId;
      fetch(`${apiBaseUrl}/runs/${runId}/cancel`, { method: "POST" }).catch((e) =>
        console.error("Failed to cancel run:", e)
      );
      return { ...prev, runStatus: "interrupted" };
    });
  }, []);

  const submitFeedback = useCallback(
    async (segmentId: string, rating: "up" | "down", note?: string, apiBaseUrl: string = "") => {
      if (!state.sessionId) return;
      try {
        await fetch(`${apiBaseUrl}/runs/${state.sessionId}/feedback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            segment_id: segmentId,
            rating,
            note: note || undefined,
          }),
        });
      } catch (e) {
        console.error("Failed to submit feedback:", e);
      }
    },
    [state.sessionId]
  );

  const resetState = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setState(createInitialState());
  }, []);

  return {
    state,
    handleEvent,
    connectToStream,
    cancelRun,
    submitFeedback,
    resetState,
  };
}
