import React, { useState } from "react";
import { usePipelineStream } from "./sse/usePipelineStream";
import { MOCK_STREAM_EVENTS } from "./sse/mockEvents";
import { UploadZone } from "./components/UploadZone";
import { StageTimeline } from "./components/StageTimeline";
import { ClipResultsGrid } from "./components/ClipResultsGrid";
import { SystemMessageBanner } from "./components/SystemMessageBanner";

export const App: React.FC = () => {
  const {
    state,
    handleEvent,
    connectToStream,
    cancelRun,
    submitFeedback,
    resetState,
  } = usePipelineStream();

  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleStartRun = async (
    file: File,
    confidenceThreshold?: number,
    timeBudget?: number
  ) => {
    setIsUploading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append("file", file);
    if (confidenceThreshold !== undefined) {
      formData.append("confidence_threshold", confidenceThreshold.toString());
    }
    if (timeBudget !== undefined) {
      formData.append("time_budget_seconds", timeBudget.toString());
    }

    try {
      const response = await fetch("/runs", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Upload failed with status ${response.status}`);
      }

      const data = await response.json();
      setIsUploading(false);
      // Connect to SSE stream
      connectToStream(data.run_id);
    } catch (err: unknown) {
      setIsUploading(false);
      const msg = err instanceof Error ? err.message : "Failed to initiate run session";
      setUploadError(msg);
    }
  };

  // Replay mock events for instant testing and verification
  const handleLoadMockFixture = () => {
    resetState();
    let delay = 100;
    for (const evt of MOCK_STREAM_EVENTS) {
      setTimeout(() => {
        handleEvent(evt);
      }, delay);
      delay += 80;
    }
  };

  const isRunning = state.runStatus === "running";
  const isFinished = ["completed", "interrupted", "failed"].includes(state.runStatus);
  const hasClips = state.renderedClips.length > 0;
  const skippedCount = state.skippedSegments.length;

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500 selection:text-white">
      {/* Top Header */}
      <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center shadow-md shadow-indigo-600/30">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-base font-bold text-white tracking-tight">ClipCrop</h1>
                <span className="text-[10px] font-mono px-2 py-0.2 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                  v0.1.0 LTS
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-medium hidden sm:block">
                Deterministic 9:16 Video Re-framing Engine
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {/* Status Indicator */}
            {state.runStatus !== "idle" && (
              <span
                id="run-status-badge"
                className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold font-mono border ${
                  isRunning
                    ? "bg-indigo-500/10 text-indigo-400 border-indigo-500/30 animate-pulse"
                    : state.runStatus === "completed"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    : state.runStatus === "failed"
                    ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                    : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full mr-2 ${
                    isRunning
                      ? "bg-indigo-400"
                      : state.runStatus === "completed"
                      ? "bg-emerald-400"
                      : state.runStatus === "failed"
                      ? "bg-rose-400"
                      : "bg-amber-400"
                  }`}
                />
                {state.runStatus.toUpperCase()}
              </span>
            )}

            {/* Emergency Stop / Cancel Button */}
            {isRunning && (
              <button
                type="button"
                id="emergency-cancel-btn"
                onClick={() => cancelRun()}
                className="px-3.5 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-400 border border-rose-500/40 text-xs font-semibold shadow-sm transition-all cursor-pointer flex items-center space-x-1.5"
                title="Halt execution and discard in-flight segment"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                </svg>
                <span>Cancel</span>
              </button>
            )}

            {/* Verification Mock Loader */}
            {state.runStatus === "idle" && (
              <button
                type="button"
                id="load-mock-fixture-btn"
                onClick={handleLoadMockFixture}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono font-medium border border-slate-700/80 transition-colors cursor-pointer"
                title="Simulate complete run using Section 9.1 mock data"
              >
                Load Mock Fixture
              </button>
            )}

            {/* Start New Run / Reset Button */}
            {isFinished && (
              <button
                type="button"
                id="new-run-btn"
                onClick={resetState}
                className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors cursor-pointer"
              >
                New Run
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Upload Error Display */}
        {uploadError && (
          <div
            id="upload-error-alert"
            className="p-4 bg-rose-950/60 border border-rose-500/50 rounded-xl text-xs text-rose-300 flex items-center justify-between"
          >
            <span>{uploadError}</span>
            <button
              type="button"
              onClick={() => setUploadError(null)}
              className="text-rose-400 hover:text-rose-200 font-bold ml-4 cursor-pointer"
            >
              ✕
            </button>
          </div>
        )}

        {/* System Failure Banner */}
        {state.systemError && (
          <SystemMessageBanner error={state.systemError} onReset={resetState} />
        )}

        {/* Idle State: Upload Zone */}
        {state.runStatus === "idle" && (
          <div className="space-y-6">
            <UploadZone onStartRun={handleStartRun} isUploading={isUploading} />

            {/* Feature Highlights Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              <div className="p-4 bg-slate-900/40 rounded-xl border border-slate-800/60 space-y-1.5">
                <div className="w-7 h-7 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400 mb-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <h4 className="text-xs font-bold text-slate-200">100% Offline & Private</h4>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  CPU-only local execution. Zero network calls, zero biometric template extraction.
                </p>
              </div>

              <div className="p-4 bg-slate-900/40 rounded-xl border border-slate-800/60 space-y-1.5">
                <div className="w-7 h-7 rounded-lg bg-cyan-500/10 flex items-center justify-center text-cyan-400 mb-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <h4 className="text-xs font-bold text-slate-200">Confidence Gated</h4>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Deterministic routing: skips low-confidence framing instead of hallucinating camera moves.
                </p>
              </div>

              <div className="p-4 bg-slate-900/40 rounded-xl border border-slate-800/60 space-y-1.5">
                <div className="w-7 h-7 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400 mb-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                  </svg>
                </div>
                <h4 className="text-xs font-bold text-slate-200">Paired NLE Deliverables</h4>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Delivers 9:16 vertical MP4 video paired with standard CMX 3600 EDL, XML, and JSON timelines.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Active or Completed Run View */}
        {state.runStatus !== "idle" && (
          <div className="space-y-6 animate-fade-in">
            {/* Graceful Degradation Summary Banner */}
            {isFinished && (
              <div
                id="run-summary-banner"
                className="p-4 bg-slate-900/70 backdrop-blur-md rounded-xl border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div className="flex items-center space-x-2">
                  <span className="font-semibold text-slate-200">Run Summary:</span>
                  <span className="text-slate-300">
                    {hasClips ? `${state.renderedClips.length} vertical clips produced` : "0 clips produced"}
                    {skippedCount > 0 ? ` (${skippedCount} skipped for low tracking confidence)` : ""}
                  </span>
                </div>
                <span className="font-mono text-slate-400 text-[11px]">
                  Total elapsed time: {state.elapsedSeconds}s
                </span>
              </div>
            )}

            {/* Generated Clip Deliverables Grid */}
            <ClipResultsGrid
              renderedClips={state.renderedClips}
              cropPathExports={state.cropPathExports}
              cropPaths={state.cropPaths}
              confidenceGateResults={state.confidenceGateResults}
              trackingResults={state.trackingResults}
              onSubmitFeedback={submitFeedback}
              runStatus={state.runStatus}
            />

            {/* 8-Stage Execution Timeline */}
            <StageTimeline
              stages={state.stages}
              currentStage={state.currentStage}
              elapsedSeconds={state.elapsedSeconds}
              runStatus={state.runStatus}
              sourceVideo={state.sourceVideo}
              transcriptSegments={state.transcriptSegments}
              vadSegments={state.vadSegments}
              candidateSegments={state.candidateSegments}
              confidenceGateResults={state.confidenceGateResults}
              trackingResults={state.trackingResults}
            />
          </div>
        )}
      </main>

      {/* Minimal Footer */}
      <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-600 font-mono">
        ClipCrop • Local CPU Video Re-framing Engine • BIPA / CUBI Biometric Privacy Safe Harbor Compliant
      </footer>
    </div>
  );
};
