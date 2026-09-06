import React, { useState, useRef } from "react";

interface UploadZoneProps {
  onStartRun: (file: File, confidenceThreshold?: number, timeBudget?: number) => void;
  isUploading: boolean;
}

const ALLOWED_EXTENSIONS = [".mp4", ".mov", ".mkv", ".webm", ".avi"];

export const UploadZone: React.FC<UploadZoneProps> = ({ onStartRun, isUploading }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.65);
  const [timeBudget, setTimeBudget] = useState<number>(90);
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);
  const [formatError, setFormatError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const validateAndSetFile = (file: File) => {
    setFormatError(null);
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setFormatError(
        `Unsupported file format (${ext}). Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`
      );
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || isUploading) return;
    onStartRun(selectedFile, confidenceThreshold, timeBudget);
  };

  return (
    <div
      id="upload-zone-container"
      className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-slate-800/80 p-6 shadow-xl space-y-5"
    >
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-slate-100">Upload Source Video</h3>
          <p className="text-xs text-slate-400">
            Convert long-form talking-head video into 9:16 vertical clips with smooth camera motion
          </p>
        </div>
        <span className="text-[11px] font-mono text-indigo-400 bg-indigo-950/60 border border-indigo-800/50 px-2.5 py-1 rounded-full">
          $0.00 • Local CPU
        </span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Drop Zone */}
        <div
          id="drop-zone"
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragOver(true);
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all flex flex-col items-center justify-center space-y-3 ${
            isDragOver
              ? "border-indigo-400 bg-indigo-950/20"
              : selectedFile
              ? "border-emerald-500/50 bg-emerald-950/10"
              : "border-slate-700/80 hover:border-slate-600 bg-slate-950/40"
          }`}
        >
          <input
            ref={fileInputRef}
            id="video-file-input"
            type="file"
            accept={ALLOWED_EXTENSIONS.join(",")}
            onChange={handleFileChange}
            className="hidden"
          />

          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center ${
              selectedFile
                ? "bg-emerald-500/20 text-emerald-400"
                : "bg-indigo-500/10 text-indigo-400"
            }`}
          >
            {selectedFile ? (
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            )}
          </div>

          {selectedFile ? (
            <div className="space-y-1">
              <p className="text-sm font-semibold text-slate-200 font-mono">
                {selectedFile.name}
              </p>
              <p className="text-xs text-slate-400 font-mono">
                {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Ready for processing
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              <p className="text-sm font-medium text-slate-300">
                Drag & drop video here, or <span className="text-indigo-400 underline underline-offset-2 font-semibold">browse file</span>
              </p>
              <p className="text-xs text-slate-500">
                Supported formats: MP4, MOV, MKV, WebM, AVI
              </p>
            </div>
          )}
        </div>

        {formatError && (
          <p id="upload-format-error" className="text-xs text-rose-400 font-medium">
            {formatError}
          </p>
        )}

        {/* Advanced Settings Toggle */}
        <div className="pt-1">
          <button
            type="button"
            id="toggle-advanced-settings"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-xs text-slate-400 hover:text-slate-200 font-medium flex items-center space-x-1 cursor-pointer transition-colors"
          >
            <span>{showAdvanced ? "▼" : "▶"} Advanced Runtime Tuning</span>
          </button>

          {showAdvanced && (
            <div className="mt-3 p-3 bg-slate-950/60 rounded-xl border border-slate-800 grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
              <div className="space-y-1">
                <div className="flex justify-between text-slate-400">
                  <span>Confidence Threshold:</span>
                  <span className="text-indigo-400 font-bold">{confidenceThreshold.toFixed(2)}</span>
                </div>
                <input
                  id="confidence-threshold-slider"
                  type="range"
                  min="0.4"
                  max="0.95"
                  step="0.05"
                  value={confidenceThreshold}
                  onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                  className="w-full accent-indigo-500 cursor-pointer"
                />
                <span className="text-[10px] text-slate-500">
                  Cutoff for Stage 5 binary render/skip gate
                </span>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-slate-400">
                  <span>Time Budget:</span>
                  <span className="text-indigo-400 font-bold">{timeBudget}s</span>
                </div>
                <input
                  id="time-budget-slider"
                  type="range"
                  min="30"
                  max="180"
                  step="10"
                  value={timeBudget}
                  onChange={(e) => setTimeBudget(parseInt(e.target.value, 10))}
                  className="w-full accent-indigo-500 cursor-pointer"
                />
                <span className="text-[10px] text-slate-500">
                  Run-wide circuit breaker ceiling
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Submit Button */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            id="start-reframing-btn"
            disabled={!selectedFile || isUploading}
            className={`w-full sm:w-auto px-6 py-2.5 rounded-xl font-semibold text-xs shadow-lg transition-all flex items-center justify-center space-x-2 ${
              !selectedFile || isUploading
                ? "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50"
                : "bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white shadow-indigo-600/25 cursor-pointer"
            }`}
          >
            {isUploading ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Initializing Pipeline…</span>
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>Start Video Re-framing</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
