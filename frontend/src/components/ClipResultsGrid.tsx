import React, { useEffect, useState } from "react";
import { FileRef, SmoothedPath, GateDecision, TrackingResult } from "../types/events";
import { CropPathChart } from "./CropPathChart";

interface ClipResultsGridProps {
  renderedClips: FileRef[];
  cropPathExports: FileRef[];
  cropPaths: Record<string, SmoothedPath>;
  confidenceGateResults?: Record<string, GateDecision>;
  trackingResults?: Record<string, TrackingResult>;
  onSubmitFeedback: (segmentId: string, rating: "up" | "down", note?: string) => void;
  apiBaseUrl?: string;
  runStatus?: string;
}

interface FeedbackState {
  rating: "up" | "down" | null;
  note: string;
  isSubmitted: boolean;
  isExpandedNote: boolean;
}

export const ClipResultsGrid: React.FC<ClipResultsGridProps> = ({
  renderedClips,
  cropPathExports,
  cropPaths,
  confidenceGateResults,
  trackingResults,
  onSubmitFeedback,
  apiBaseUrl = "",
  runStatus,
}) => {
  const [activeViewMode, setActiveViewMode] = useState<Record<string, "video" | "cropPath">>({});
  const [feedbackMap, setFeedbackMap] = useState<Record<string, FeedbackState>>({});
  const [metadataMap, setMetadataMap] = useState<Record<string, any>>({});
  const [copiedSegId, setCopiedSegId] = useState<string | null>(null);

  // Ensure pairing: only render clips that have corresponding crop path exports
  const pairedClips = renderedClips.filter((clip) => {
    if (!clip.segment_id) return true;
    return cropPathExports.some((exp) => exp.segment_id === clip.segment_id);
  });

  useEffect(() => {
    pairedClips.forEach((clip) => {
      const segId = clip.segment_id;
      if (!segId) return;
      const clipFilename = clip.path.split(/[/\\]/).pop() || "";
      const metaFilename = clipFilename.replace(/_vertical\.mp4$/i, "_metadata.json");
      fetch(`${apiBaseUrl}/outputs/${metaFilename}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data) {
            setMetadataMap((prev) => ({ ...prev, [segId]: data }));
          }
        })
        .catch(() => {});
    });
  }, [pairedClips, apiBaseUrl]);

  const handleCopyTitleAndTags = (segId: string, meta: any) => {
    const title = meta?.titles?.[0] || meta?.hook || "Check out this clip!";
    const tags = (meta?.hashtags || []).join(" ");
    const textToCopy = `${title}\n\n${tags}`;
    navigator.clipboard.writeText(textToCopy);
    setCopiedSegId(segId);
    setTimeout(() => setCopiedSegId(null), 2000);
  };

  if (pairedClips.length === 0) {
    if (runStatus === "completed") {
      return (
        <div id="no-clips-empty-state" className="p-6 bg-slate-900/60 backdrop-blur-md rounded-2xl border border-slate-800/80 text-center space-y-2 shadow-xl">
          <div className="w-10 h-10 mx-auto rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h4 className="text-sm font-semibold text-slate-200">
            Run Completed — All candidate segments skipped due to low tracking confidence.
          </h4>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Try adjusting threshold or uploading clear talking-head footage.
          </p>
        </div>
      );
    }
    return null;
  }

  const handleFeedbackRating = (segmentId: string, rating: "up" | "down") => {
    const prev = feedbackMap[segmentId] || { rating: null, note: "", isSubmitted: false, isExpandedNote: false };
    const updated: FeedbackState = {
      ...prev,
      rating,
      isExpandedNote: rating === "down" ? true : prev.isExpandedNote,
    };
    setFeedbackMap({ ...feedbackMap, [segmentId]: updated });
    onSubmitFeedback(segmentId, rating, updated.note);
  };

  const handleFeedbackNoteSubmit = (segmentId: string) => {
    const item = feedbackMap[segmentId];
    if (!item || !item.rating) return;
    onSubmitFeedback(segmentId, item.rating, item.note);
    setFeedbackMap({
      ...feedbackMap,
      [segmentId]: { ...item, isSubmitted: true },
    });
  };

  return (
    <div id="clip-results-grid" className="space-y-4">
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
              Generated Vertical Clips & NLE Deliverables
            </h3>
            <p className="text-xs text-slate-400">
              {pairedClips.length} {pairedClips.length === 1 ? "clip" : "clips"} rendered and paired with edit tracks
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {pairedClips.map((clip) => {
          const segId = clip.segment_id || "seg_default";
          const matchingExports = cropPathExports.filter((exp) => exp.segment_id === segId);
          const primaryExport = matchingExports[0];
          const pathData = cropPaths[segId];
          const viewMode = activeViewMode[segId] || "video";
          const feedback = feedbackMap[segId] || { rating: null, note: "", isSubmitted: false, isExpandedNote: false };

          const gate = confidenceGateResults?.[segId];
          const tracking = trackingResults?.[segId];
          const confidenceScore =
            (clip as unknown as { tracking_confidence?: number }).tracking_confidence ??
            gate?.tracking_confidence ??
            tracking?.segment_confidence ??
            1.0;

          const clipFilename = clip.path.split(/[/\\]/).pop() || "clip.mp4";
          const clipUrl = `${apiBaseUrl}/outputs/${clipFilename}`;
          const thumbUrl = `${apiBaseUrl}/outputs/${clipFilename.replace(/_vertical\.mp4$/i, "_thumbnail.jpg")}`;
          const meta = metadataMap[segId];
          const zipFilename = clipFilename.replace(/_vertical\.mp4$/i, "_complete_pack.zip");
          const zipUrl = `${apiBaseUrl}/outputs/${zipFilename}`;

          const durationStr = clip.duration_seconds ? `${clip.duration_seconds.toFixed(1)}s` : "—";
          const sizeStr = clip.file_size_bytes
            ? `${(clip.file_size_bytes / (1024 * 1024)).toFixed(1)} MB`
            : "—";

          return (
            <div
              key={segId}
              id={`clip-card-${segId}`}
              className="bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-800/80 overflow-hidden shadow-xl flex flex-col transition-all hover:border-slate-700"
            >
              {/* Card Header */}
              <div className="p-3 bg-slate-950/60 border-b border-slate-800/80 flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-mono font-bold text-slate-200 uppercase px-2 py-0.5 rounded bg-slate-800 border border-slate-700/60">
                    {segId}
                  </span>
                  <span className="text-[11px] font-mono text-slate-400">
                    {durationStr} • {sizeStr}
                  </span>
                </div>
                <div className="flex items-center space-x-1">
                  <button
                    type="button"
                    id={`toggle-view-${segId}`}
                    onClick={() =>
                      setActiveViewMode({
                        ...activeViewMode,
                        [segId]: viewMode === "video" ? "cropPath" : "video",
                      })
                    }
                    className="text-[10px] font-medium px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer"
                  >
                    {viewMode === "video" ? "View Crop Motion" : "View Video"}
                  </button>
                </div>
              </div>

              {/* 9:16 Video Player or Crop Motion Path */}
              <div className="relative bg-black flex items-center justify-center aspect-[9/16] w-full max-h-[460px] overflow-hidden">
                {viewMode === "video" ? (
                  <video
                    id={`video-player-${segId}`}
                    controls
                    playsInline
                    preload="metadata"
                    poster={thumbUrl}
                    className="w-full h-full object-contain"
                    src={clipUrl}
                  >
                    Your browser does not support the video tag.
                  </video>
                ) : (
                  <div className="w-full h-full p-4 flex flex-col justify-center bg-slate-950">
                    <CropPathChart keyframes={pathData?.crop_keyframes || []} segmentId={segId} />
                  </div>
                )}
              </div>

              {/* Action Buttons & Downloads */}
              <div className="p-4 space-y-3 bg-slate-900/90 flex-1 flex flex-col justify-between">
                <div className="space-y-2.5">
                  {/* Master ZIP Download Button */}
                  <a
                    id={`download-zip-${segId}`}
                    href={zipUrl}
                    download={zipFilename}
                    className="w-full flex items-center justify-center space-x-2 py-2.5 px-3 rounded-lg bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold shadow-lg shadow-emerald-950/40 border border-emerald-400/40 transition-all cursor-pointer"
                    title="Download complete creator pack containing vertical MP4, EDL, XML, JSON, SRT, thumbnail, and metadata"
                  >
                    <span>📦 Download Complete Creator Pack (.ZIP)</span>
                  </a>

                  {/* Viral Hook & SEO Metadata Box */}
                  {meta?.hook && (
                    <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-mono font-bold text-amber-400 uppercase tracking-wider">
                          ⚡ Viral Hook
                        </span>
                        <button
                          type="button"
                          id={`copy-meta-${segId}`}
                          onClick={() => handleCopyTitleAndTags(segId, meta)}
                          className="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer"
                        >
                          {copiedSegId === segId ? "✓ Copied!" : "📋 Copy Title & Tags"}
                        </button>
                      </div>
                      <p className="text-xs text-slate-200 italic font-medium">
                        "{meta.hook}"
                      </p>
                      <div className="flex flex-wrap gap-1 pt-0.5">
                        {(meta.hashtags || []).map((tag: string) => (
                          <span key={tag} className="text-[10px] font-mono text-indigo-400">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Secondary Individual Downloads */}
                  <div className="space-y-1.5 pt-1 border-t border-slate-800/60">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono text-slate-400 uppercase">
                        Individual Files:
                      </span>
                      <a
                        id={`download-clip-${segId}`}
                        href={clipUrl}
                        download={clipFilename}
                        className="text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 transition-colors cursor-pointer flex items-center space-x-1"
                      >
                        <span>Download .MP4</span>
                      </a>
                    </div>

                    {primaryExport && (
                      <div className="grid grid-cols-4 gap-1.5">
                        {["edl", "xml", "json", "srt"].map((fmt) => {
                          const baseFile = primaryExport.path.split(/[/\\]/).pop() || `${segId}.edl`;
                          const rootName = baseFile.replace(/\.(edl|xml|json|srt)$/i, "");
                          const formatFilename = `${rootName}.${fmt}`;
                          const formatUrl = `${apiBaseUrl}/outputs/${formatFilename}`;

                          return (
                            <a
                              key={fmt}
                              id={`download-${fmt}-${segId}`}
                              href={formatUrl}
                              download={formatFilename}
                              className="py-1 px-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] font-mono font-medium text-center border border-slate-700/60 transition-colors cursor-pointer"
                              title={`Download ${fmt.toUpperCase()} timeline / subtitles`}
                            >
                              .{fmt.toUpperCase()}
                            </a>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>

                {/* Thumbs up / down Feedback Controls (Section 7a) */}
                <div id={`feedback-controls-${segId}`} className="pt-2 border-t border-slate-800/80">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[11px] text-slate-400 font-medium">
                      Framing Quality:{" "}
                      <span className="text-emerald-400 font-mono font-semibold">
                        {(confidenceScore * 100).toFixed(0)}% (Optimal)
                      </span>
                    </span>
                    <div className="flex items-center space-x-1.5">
                      <button
                        type="button"
                        id={`feedback-up-${segId}`}
                        onClick={() => handleFeedbackRating(segId, "up")}
                        className={`p-1.5 rounded cursor-pointer transition-colors ${
                          feedback.rating === "up"
                            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                            : "bg-slate-800 text-slate-400 hover:text-slate-200"
                        }`}
                        title="Framing looks good"
                      >
                        <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        id={`feedback-down-${segId}`}
                        onClick={() => handleFeedbackRating(segId, "down")}
                        className={`p-1.5 rounded cursor-pointer transition-colors ${
                          feedback.rating === "down"
                            ? "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                            : "bg-slate-800 text-slate-400 hover:text-slate-200"
                        }`}
                        title="Framing needs improvement"
                      >
                        <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M18 9.5a1.5 1.5 0 11-3 0v-6a1.5 1.5 0 013 0v6zM14 9.667v-5.43a2 2 0 00-1.105-1.79l-.05-.025A4 4 0 0011.057 2H5.642a2 2 0 00-1.962 1.608l-1.2 6A2 2 0 004.44 12H8v4a2 2 0 002 2 1 1 0 001-1v-.667a4 4 0 01.8-2.4l1.4-1.866a4 4 0 00.8-2.4z" />
                        </svg>
                      </button>
                    </div>
                  </div>

                  {feedback.isExpandedNote && (
                    <div className="mt-2 space-y-1.5">
                      <input
                        type="text"
                        id={`feedback-note-${segId}`}
                        value={feedback.note}
                        maxLength={500}
                        onChange={(e) =>
                          setFeedbackMap({
                            ...feedbackMap,
                            [segId]: { ...feedback, note: e.target.value },
                          })
                        }
                        placeholder="Optional note (e.g., face cut off briefly)"
                        className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                      />
                      <div className="flex justify-end">
                        <button
                          type="button"
                          id={`feedback-submit-${segId}`}
                          onClick={() => handleFeedbackNoteSubmit(segId)}
                          className="px-2.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-medium cursor-pointer"
                        >
                          {feedback.isSubmitted ? "Saved" : "Save Note"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
