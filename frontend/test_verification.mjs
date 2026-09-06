import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log("=== STEP 17 VERIFICATION: Interface Layer & Generative UI Components ===");

// 1. Verify all required files exist
const requiredFiles = [
  "src/types/events.ts",
  "src/sse/usePipelineStream.ts",
  "src/sse/mockEvents.ts",
  "src/components/SourceVideoCard.tsx",
  "src/components/TranscriptView.tsx",
  "src/components/VadTimeline.tsx",
  "src/components/CandidateRankingTable.tsx",
  "src/components/ConfidenceBadge.tsx",
  "src/components/CropPathChart.tsx",
  "src/components/ClipResultsGrid.tsx",
  "src/components/StageTimeline.tsx",
  "src/components/SystemMessageBanner.tsx",
  "src/components/UploadZone.tsx",
  "src/App.tsx",
  "src/index.css",
  "src/main.tsx",
  "index.html",
  "vite.config.ts",
  "tsconfig.json",
  "dist/index.html",
  "dist/assets",
];

let allExist = true;
for (const relPath of requiredFiles) {
  const fullPath = path.join(__dirname, relPath);
  if (!fs.existsSync(fullPath)) {
    console.error(`❌ Missing file: ${relPath}`);
    allExist = false;
  } else {
    console.log(`✅ File exists: ${relPath}`);
  }
}

if (!allExist) {
  console.error("Test failed: some files are missing!");
  process.exit(1);
}

// 2. Verify UI Non-Goals compliance (per docs/INTERFACE_OBSERVABILITY_SYSTEM.md Section 10)
const srcDir = path.join(__dirname, "src");
function scanFiles(dir) {
  let files = [];
  for (const item of fs.readdirSync(dir)) {
    const p = path.join(dir, item);
    if (fs.statSync(p).isDirectory()) {
      files = files.concat(scanFiles(p));
    } else if (p.endsWith(".tsx") || p.endsWith(".ts")) {
      files.push(p);
    }
  }
  return files;
}

const allSrcFiles = scanFiles(srcDir);
const nonGoalPatterns = [
  { name: "Chat UI / Prompt Thread", regex: /ChatInput|ChatMessageList|ConversationHistory/i },
  { name: "Model Thinking Tokens", regex: /thinking_tokens|reasoning_tokens|model_thought/i },
  { name: "HITL Approval Gate Modal", regex: /ApprovalModal|HumanInTheLoopModal|ApproveRejectModal/i },
  { name: "Individual Clip Retry Button", regex: /retryClip|regenerateClip|retry_segment/i },
  { name: "Continuous Quality Score Meter", regex: /qualityMeter|continuousScoreGauge/i },
];

let violationsFound = false;
for (const file of allSrcFiles) {
  const content = fs.readFileSync(file, "utf8");
  for (const ng of nonGoalPatterns) {
    if (ng.regex.test(content)) {
      console.error(`❌ UI Non-Goal Violation in ${path.relative(__dirname, file)}: Found ${ng.name}`);
      violationsFound = true;
    }
  }
}

if (violationsFound) {
  console.error("Test failed: UI Non-Goal violations found!");
  process.exit(1);
}
console.log("✅ All UI Non-Goals verified: Zero chat threads, thinking tokens, HITL approval modals, or clip retry buttons.");

// 3. Verify Mock Stream Events structure
const mockEventsContent = fs.readFileSync(path.join(__dirname, "src/sse/mockEvents.ts"), "utf8");
const expectedEventTypes = [
  "data-stage-start",
  "tool-input-available",
  "tool-output-available",
  "data-state-update",
  "data-run-end"
];

for (const evtType of expectedEventTypes) {
  if (!mockEventsContent.includes(evtType)) {
    console.error(`❌ Missing event type ${evtType} in mockEvents.ts`);
    process.exit(1);
  }
}
console.log("✅ Mock events contain all required Vercel AI SDK v6 wire format event types.");

// 4. Verify all 7 Generative UI Components from Section 4a are present
const components = [
  "SourceVideoCard",
  "TranscriptView",
  "VadTimeline",
  "CandidateRankingTable",
  "ConfidenceBadge",
  "CropPathChart",
  "ClipResultsGrid"
];

for (const comp of components) {
  const compPath = path.join(__dirname, `src/components/${comp}.tsx`);
  const content = fs.readFileSync(compPath, "utf8");
  if (!content.includes(`export const ${comp}`)) {
    console.error(`❌ Component ${comp} is not exported properly.`);
    process.exit(1);
  }
  console.log(`✅ Section 4a Generative Component verified: ${comp}`);
}

console.log("\n🎉 ALL STEP 17 VERIFICATION CHECKS PASSED SUCCESSFULLY!");
