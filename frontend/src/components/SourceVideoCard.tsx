import React from "react";
import { FileRef } from "../types/events";

interface SourceVideoCardProps {
  source: FileRef | null;
}

export const SourceVideoCard: React.FC<SourceVideoCardProps> = ({ source }) => {
  if (!source) return null;

  const durationStr = source.duration_seconds
    ? `${Math.floor(source.duration_seconds / 60)}m ${Math.floor(source.duration_seconds % 60)}s`
    : "Unknown";

  const resolutionStr =
    source.width && source.height ? `${source.width} × ${source.height}` : "Unknown";

  const fpsStr = source.fps ? `${source.fps.toFixed(2)} fps` : null;

  // Clean filename for display (hide internal local absolute path)
  const displayName = source.path.split(/[/\\]/).pop() || "source_video.mp4";

  return (
    <div
      id="source-video-card"
      className="bg-slate-900/80 backdrop-blur-md border border-slate-800/80 rounded-xl p-4 shadow-lg transition-all hover:border-slate-700/80"
    >
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/60 mb-3">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Source Video</h4>
            <p className="text-sm font-medium text-slate-200 truncate max-w-xs sm:max-w-md font-mono" title={displayName}>
              {displayName}
            </p>
          </div>
        </div>
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />
          Validated
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="bg-slate-950/50 rounded-lg p-2.5 border border-slate-800/40">
          <span className="text-slate-500 block mb-0.5">Duration</span>
          <span className="text-slate-200 font-semibold font-mono">{durationStr}</span>
        </div>
        <div className="bg-slate-950/50 rounded-lg p-2.5 border border-slate-800/40">
          <span className="text-slate-500 block mb-0.5">Resolution</span>
          <span className="text-slate-200 font-semibold font-mono">{resolutionStr}</span>
        </div>
        <div className="bg-slate-950/50 rounded-lg p-2.5 border border-slate-800/40">
          <span className="text-slate-500 block mb-0.5">Framerate</span>
          <span className="text-slate-200 font-semibold font-mono">{fpsStr || "—"}</span>
        </div>
        <div className="bg-slate-950/50 rounded-lg p-2.5 border border-slate-800/40">
          <span className="text-slate-500 block mb-0.5">Tracks</span>
          <div className="flex items-center space-x-2 text-slate-200 font-medium">
            <span className={source.has_video_track ? "text-indigo-400" : "text-slate-600"} title="Video Track">
              VIDEO
            </span>
            <span className="text-slate-700">/</span>
            <span className={source.has_audio_track ? "text-cyan-400" : "text-slate-600"} title="Audio Track">
              AUDIO
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
