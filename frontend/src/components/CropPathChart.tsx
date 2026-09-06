import React, { useState } from "react";
import { CropKeyframe } from "../types/events";

interface CropPathChartProps {
  keyframes: CropKeyframe[];
  segmentId?: string;
  sourceWidth?: number;
  sourceHeight?: number;
}

export const CropPathChart: React.FC<CropPathChartProps> = ({
  keyframes,
  segmentId,
  sourceWidth = 1920,
  sourceHeight: _sourceHeight = 1080,
}) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (!keyframes || keyframes.length === 0) {
    return (
      <div id={`crop-path-chart-empty-${segmentId}`} className="p-3 bg-slate-950/40 rounded-lg text-xs text-slate-500 italic">
        No crop keyframe data available.
      </div>
    );
  }

  // SVG dimensions
  const svgWidth = 320;
  const svgHeight = 120;
  const padX = 25;
  const padY = 20;
  const plotWidth = svgWidth - padX * 2;
  const plotHeight = svgHeight - padY * 2;

  const minTime = keyframes[0].timestamp_ms;
  const maxTime = Math.max(keyframes[keyframes.length - 1].timestamp_ms, minTime + 1);
  const timeSpan = maxTime - minTime;

  // Max bounds for x (crop pan is along x axis in 16:9 -> 9:16)
  const maxX = sourceWidth - (keyframes[0]?.width || 608);

  const points = keyframes.map((kf, i) => {
    const normX = timeSpan > 0 ? (kf.timestamp_ms - minTime) / timeSpan : 0;
    const normY = maxX > 0 ? kf.x / maxX : 0.5;

    const px = padX + normX * plotWidth;
    const py = padY + normY * plotHeight;
    return { px, py, kf, i };
  });

  const pathD = points.reduce((acc, pt, i) => {
    return `${acc} ${i === 0 ? "M" : "L"} ${pt.px.toFixed(1)} ${pt.py.toFixed(1)}`;
  }, "");

  return (
    <div
      id={`crop-path-chart-${segmentId}`}
      className="bg-slate-950/70 rounded-lg border border-slate-800/80 p-3 space-y-2"
    >
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-slate-300">Camera Pan Motion Trajectory</span>
        <span className="font-mono text-[11px] text-indigo-400 bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-900/40">
          {keyframes.length} keyframes
        </span>
      </div>

      <div className="relative flex justify-center">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-28 overflow-visible"
        >
          {/* Subtle grid lines */}
          <line x1={padX} y1={padY} x2={padX + plotWidth} y2={padY} stroke="#334155" strokeDasharray="3,3" strokeWidth="0.8" />
          <line x1={padX} y1={padY + plotHeight / 2} x2={padX + plotWidth} y2={padY + plotHeight / 2} stroke="#334155" strokeDasharray="3,3" strokeWidth="0.8" />
          <line x1={padX} y1={padY + plotHeight} x2={padX + plotWidth} y2={padY + plotHeight} stroke="#334155" strokeDasharray="3,3" strokeWidth="0.8" />

          {/* Trajectory smooth line */}
          <path
            d={pathD}
            fill="none"
            stroke="url(#gradient-line)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Keyframe nodes */}
          {points.map((pt) => (
            <circle
              key={pt.i}
              cx={pt.px}
              cy={pt.py}
              r={hoveredIndex === pt.i ? 4 : 2.5}
              className={`transition-all cursor-pointer ${
                hoveredIndex === pt.i
                  ? "fill-white stroke-indigo-500 stroke-2"
                  : "fill-indigo-400"
              }`}
              onMouseEnter={() => setHoveredIndex(pt.i)}
              onMouseLeave={() => setHoveredIndex(null)}
            />
          ))}

          <defs>
            <linearGradient id="gradient-line" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#06b6d4" />
              <stop offset="100%" stopColor="#818cf8" />
            </linearGradient>
          </defs>
        </svg>
      </div>

      <div className="flex justify-between text-[10px] font-mono text-slate-500">
        <span>Left Pan (x: 0)</span>
        {hoveredIndex !== null && points[hoveredIndex] ? (
          <span className="text-indigo-300 font-semibold">
            {((points[hoveredIndex].kf.timestamp_ms - minTime) / 1000).toFixed(1)}s: x={points[hoveredIndex].kf.x}px
          </span>
        ) : (
          <span>Center</span>
        )}
        <span>Right Pan (x: {sourceWidth - 608}px)</span>
      </div>
    </div>
  );
};
