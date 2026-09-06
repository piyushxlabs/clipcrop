import { StreamEvent } from "../types/events";

/**
 * Authoritative mock SSE event trajectory matching AGENT_MASTER_PLAN.md Section 9.1
 * and tests/mocks/mock_tool_data.py for offline verification and component rendering.
 */
export const MOCK_STREAM_EVENTS: StreamEvent[] = [
  // Stage 1: Ingest & Validate
  {
    type: "data-stage-start",
    stage: "ingest_and_validate",
    label: "Validating video",
  },
  {
    type: "tool-input-available",
    toolCallId: "call_ingest_01",
    toolName: "decode_and_validate_source",
    input: { source_path: "uploads/input_talk.mp4" },
  },
  {
    type: "tool-output-available",
    toolCallId: "call_ingest_01",
    toolName: "decode_and_validate_source",
    output: {
      success: true,
      duration_seconds: 612.4,
      has_video_track: true,
      has_audio_track: true,
      width: 1920,
      height: 1080,
      fps: 29.97,
      output_file_path: "uploads/input_talk.mp4",
      error: null,
    },
  },
  {
    type: "data-state-update",
    field: "source_video",
    reducer: "immutable-after-init",
    value: {
      path: "uploads/input_talk.mp4",
      duration_seconds: 612.4,
      width: 1920,
      height: 1080,
      fps: 29.97,
      has_video_track: true,
      has_audio_track: true,
    },
  },

  // Stage 2: Transcribe & Segment
  {
    type: "data-stage-start",
    stage: "transcribe_and_segment",
    label: "Listening for speech",
  },
  {
    type: "tool-input-available",
    toolCallId: "call_transcribe_01",
    toolName: "transcribe_audio",
    input: { model_tier: "base.en" },
  },
  {
    type: "data-stage-progress",
    stage: "transcribe_and_segment",
    detail: "Transcribing speech using faster-whisper INT8 CPU…",
  },
  {
    type: "tool-output-available",
    toolCallId: "call_transcribe_01",
    toolName: "transcribe_audio",
    output: {
      success: true,
      segments: [
        { start_ms: 0, end_ms: 850, text: "And so my" },
        { start_ms: 900, end_ms: 2500, text: "journey began in video editing." },
        { start_ms: 3200, end_ms: 6800, text: "The challenge was finding the key moments in long form recordings." },
      ],
      language_detected: "en",
    },
  },
  {
    type: "data-state-update",
    field: "transcript_segments",
    reducer: "append-only",
    value: [
      { start_ms: 0, end_ms: 850, text: "And so my" },
      { start_ms: 900, end_ms: 2500, text: "journey began in video editing." },
      { start_ms: 3200, end_ms: 6800, text: "The challenge was finding the key moments in long form recordings." },
    ],
  },
  {
    type: "tool-output-available",
    toolCallId: "call_vad_01",
    toolName: "detect_speech_pauses",
    output: {
      success: true,
      speech_spans: [
        { start_seconds: 0.0, end_seconds: 11.0 },
        { start_seconds: 12.5, end_seconds: 25.0 },
      ],
      sampling_rate_used: 16000,
    },
  },
  {
    type: "data-state-update",
    field: "vad_segments",
    reducer: "append-only",
    value: [
      { start_seconds: 0.0, end_seconds: 11.0 },
      { start_seconds: 12.5, end_seconds: 25.0 },
    ],
  },

  // Stage 3: Score Candidates
  {
    type: "data-stage-start",
    stage: "score_candidates",
    label: "Ranking candidate segments",
  },
  {
    type: "data-state-update",
    field: "candidate_segments",
    reducer: "last-write-wins",
    value: [
      {
        segment_id: "seg_01",
        start_ms: 0,
        end_ms: 17700,
        score: 0.884,
        pause_pattern_score: 0.85,
        energy_peak_score: 0.92,
        speaking_rate_variance_score: 0.81,
        keyword_density_score: 0.95,
        rank: 1,
      },
      {
        segment_id: "seg_02",
        start_ms: 18000,
        end_ms: 32000,
        score: 0.621,
        pause_pattern_score: 0.60,
        energy_peak_score: 0.58,
        speaking_rate_variance_score: 0.65,
        keyword_density_score: 0.64,
        rank: 2,
      },
    ],
  },

  // Stage 4: Track Speaker Position (seg_01 and seg_02)
  {
    type: "data-stage-start",
    stage: "track_speaker_position",
    label: "Finding the speaker",
  },
  {
    type: "tool-output-available",
    toolCallId: "call_track_seg01",
    toolName: "track_speaker_position",
    output: {
      segment_id: "seg_01",
      success: true,
      per_frame_positions: [
        { timestamp_ms: 0, bounding_box: { origin_x: 126, origin_y: 100, width: 463, height: 463 }, detection_score: 0.97 },
        { timestamp_ms: 100, bounding_box: { origin_x: 130, origin_y: 102, width: 460, height: 460 }, detection_score: 0.95 },
      ],
      segment_confidence: 0.91,
    },
  },
  {
    type: "data-state-update",
    field: "tracking_results",
    reducer: "merge-by-key",
    key: "seg_01",
    value: {
      segment_id: "seg_01",
      success: true,
      per_frame_positions: [
        { timestamp_ms: 0, bounding_box: { origin_x: 126, origin_y: 100, width: 463, height: 463 }, detection_score: 0.97 },
        { timestamp_ms: 100, bounding_box: { origin_x: 130, origin_y: 102, width: 460, height: 460 }, detection_score: 0.95 },
      ],
      segment_confidence: 0.91,
    },
  },
  {
    type: "data-state-update",
    field: "tracking_results",
    reducer: "merge-by-key",
    key: "seg_02",
    value: {
      segment_id: "seg_02",
      success: true,
      per_frame_positions: [],
      segment_confidence: 0.42,
    },
  },

  // Stage 5: Confidence Gate Decisions
  {
    type: "data-stage-start",
    stage: "confidence_gate",
    label: "Evaluating tracking confidence",
  },
  {
    type: "data-state-update",
    field: "confidence_gate_results",
    reducer: "merge-by-key",
    key: "seg_01",
    value: {
      segment_id: "seg_01",
      tracking_confidence: 0.91,
      threshold_used: 0.65,
      decision: "render",
      reason: "Tracking confidence 0.91 meets threshold 0.65",
    },
  },
  {
    type: "data-state-update",
    field: "confidence_gate_results",
    reducer: "merge-by-key",
    key: "seg_02",
    value: {
      segment_id: "seg_02",
      tracking_confidence: 0.42,
      threshold_used: 0.65,
      decision: "skip",
      reason: "Tracking confidence 0.42 below threshold 0.65 (speaker out of frame)",
    },
  },
  {
    type: "data-state-update",
    field: "skipped_segments",
    reducer: "append-only",
    value: {
      segment_id: "seg_02",
      tracking_confidence: 0.42,
      threshold_used: 0.65,
      reason: "Tracking confidence 0.42 below threshold 0.65 (speaker out of frame)",
    },
  },

  // Stage 6: Smooth Crop Path (seg_01 only)
  {
    type: "data-stage-start",
    stage: "smooth_crop_path",
    label: "Smoothing the camera path",
  },
  {
    type: "tool-output-available",
    toolCallId: "call_smooth_seg01",
    toolName: "smooth_crop_path",
    output: {
      segment_id: "seg_01",
      success: true,
      crop_keyframes: [
        { timestamp_ms: 0, x: 210, y: 40, width: 608, height: 1080 },
        { timestamp_ms: 2000, x: 215, y: 40, width: 608, height: 1080 },
        { timestamp_ms: 5000, x: 240, y: 40, width: 608, height: 1080 },
        { timestamp_ms: 10000, x: 260, y: 40, width: 608, height: 1080 },
        { timestamp_ms: 15000, x: 230, y: 40, width: 608, height: 1080 },
        { timestamp_ms: 17700, x: 212, y: 40, width: 608, height: 1080 },
      ],
    },
  },
  {
    type: "data-state-update",
    field: "crop_paths",
    reducer: "merge-by-key",
    key: "seg_01",
    value: {
      segment_id: "seg_01",
      success: true,
      crop_keyframes: [
        { timestamp_ms: 0, x: 210, y: 40, width: 608, height: 1080 },
        { timestamp_ms: 2000, x: 215, y: 40, width: 608, height: 1080 },
        { timestamp_ms: 5000, x: 240, y: 40, width: 608, height: 1080 },
        { timestamp_ms: 10000, x: 260, y: 40, width: 608, height: 1080 },
        { timestamp_ms: 15000, x: 230, y: 40, width: 608, height: 1080 },
        { timestamp_ms: 17700, x: 212, y: 40, width: 608, height: 1080 },
      ],
    },
  },

  // Stage 7: Render & Export (seg_01)
  {
    type: "data-stage-start",
    stage: "render_and_export",
    label: "Rendering clips and exporting timeline data",
  },
  {
    type: "tool-output-available",
    toolCallId: "call_render_seg01",
    toolName: "render_vertical_clip",
    output: {
      success: true,
      output_file_path: "outputs/clip_seg01.mp4",
      duration_seconds: 17.7,
      file_size_bytes: 4823110,
    },
  },
  {
    type: "data-state-update",
    field: "rendered_clips",
    reducer: "append-only",
    value: {
      path: "outputs/clip_seg01.mp4",
      duration_seconds: 17.7,
      file_size_bytes: 4823110,
      segment_id: "seg_01",
      width: 1080,
      height: 1920,
      fps: 29.97,
      format: "mp4",
    },
  },
  {
    type: "tool-output-available",
    toolCallId: "call_export_seg01",
    toolName: "export_crop_path_data",
    output: {
      success: true,
      output_file_path: "outputs/clip_seg01.edl",
      keyframe_count: 42,
    },
  },
  {
    type: "data-state-update",
    field: "crop_path_exports",
    reducer: "append-only",
    value: {
      path: "outputs/clip_seg01.edl",
      segment_id: "seg_01",
      keyframe_count: 42,
      format: "edl",
    },
  },

  // Stage 8: Aggregate & Terminate
  {
    type: "data-stage-start",
    stage: "aggregate_and_terminate",
    label: "Finalizing summary and deliverables",
  },
  {
    type: "data-run-end",
    reason: "success",
    deliverables_count: 1,
    skipped_count: 1,
  },
];
