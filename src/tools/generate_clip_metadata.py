"""100% Local Viral Title, Hook & SEO Engine.

Heuristic & Local LLM (Ollama Qwen 2.5) extraction of viral social media hooks,
3 title variants, and categorical hashtags from clip transcripts. Zero cloud API calls.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any
import urllib.request


def _extract_key_topic(text: str) -> str:
    """Extract primary subject noun/concept from transcript using heuristic keyword analysis."""
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "up", "about", "into", "through", "after",
        "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "can", "could", "will", "would", "should", "shall",
        "this", "that", "these", "those", "it", "its", "you", "your", "we", "our",
        "i", "my", "me", "he", "she", "they", "them", "what", "which", "who",
    }
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    filtered = [w for w in words if w not in stop_words]
    if filtered:
        # Most frequent or longest prominent word
        freq: dict[str, int] = {}
        for w in filtered:
            freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: (x[1], len(x[0])), reverse=True)
        return sorted_words[0][0].title()
    return "This"


def _query_ollama_metadata(
    transcript: str,
    timeout: float = 4.0,
    endpoint: str = "http://127.0.0.1:11434",
) -> dict[str, Any] | None:
    """Query local Ollama instance running Qwen 2.5 for viral metadata.

    Falls back gracefully if Ollama is unreachable, times out, or returns invalid JSON.
    """
    if not transcript or not transcript.strip():
        return None

    # Priority model: qwen2.5:3b, then qwen2.5:7b
    models_to_try = ["qwen2.5:3b", "qwen2.5:7b"]

    prompt = (
        "You are an expert short-form viral video editor. Analyze this clip transcript:\n"
        f'"{transcript.strip()}"\n\n'
        "Generate a JSON object with:\n"
        '1. "hook": One punchy, curiosity-inducing opening hook sentence (max 10 words, do NOT use generic greetings like "Hey everyone").\n'
        '2. "titles": Array of 3 high-CTR viral titles.\n'
        '3. "hashtags": Array of 5 relevant viral hashtags starting with #.\n\n'
        "Respond strictly with valid JSON only."
    )

    for model_name in models_to_try:
        try:
            req_data = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
                "keep_alive": -1,
            }
            req = urllib.request.Request(
                f"{endpoint}/api/chat",
                data=json.dumps(req_data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as res:
                if res.status != 200:
                    continue
                body = json.loads(res.read().decode("utf-8"))
                content = body.get("message", {}).get("content", "").strip()
                if not content:
                    continue
                # Strip optional markdown code fences
                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
                    content = re.sub(r"\s*```$", "", content)
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    continue

                hook = str(parsed.get("hook", "")).strip()
                raw_titles = parsed.get("titles", [])
                raw_hashtags = parsed.get("hashtags", [])

                if not hook or not isinstance(raw_titles, list) or not raw_titles:
                    continue

                titles = [str(t).strip() for t in raw_titles if str(t).strip()][:3]
                hashtags = [
                    f"#{str(h).strip().lstrip('#')}"
                    for h in raw_hashtags
                    if str(h).strip()
                ][:5]

                return {
                    "hook": hook,
                    "titles": titles if titles else None,
                    "hashtags": hashtags if hashtags else None,
                }
        except Exception:
            continue

    return None


def generate_clip_metadata(
    segment_id: str,
    transcript_text: str,
    duration_seconds: float,
    energy_score: float = 0.8,
    output_path: str | Path | None = None,
    use_ollama: bool = True,
) -> dict[str, Any]:
    """Generate viral hooks, titles, and hashtags from segment transcript."""
    cleaned_text = transcript_text.strip()
    sentences = [
        s.strip()
        for s in re.split(r"[.?!]+", cleaned_text)
        if s.strip()
    ]

    if not sentences:
        sentences = [cleaned_text or "Check this out"]

    # 1. Heuristic Hook Extraction
    hook = sentences[0]
    for s in sentences[:3]:
        s_lower = s.lower()
        if any(trigger in s_lower for trigger in ["give me", "what if", "how to", "why", "never", "always", "the secret", "stop"]):
            hook = s
            break
        if len(s.split()) <= 10:
            hook = s
            break

    hook_clean = hook.strip(" .,-")

    # 2. Key Subject
    topic = _extract_key_topic(cleaned_text)

    # 3. Three Viral Titles
    curiosity_title = f"The Truth About {topic} Nobody Tells You"
    hook_title = f'"{hook_clean}"'
    punchline_sentence = sentences[-1].strip(" .,-") if len(sentences) > 1 else sentences[0].strip(" .,-")
    action_title = f"Why You Need To {punchline_sentence}" if len(punchline_sentence.split()) <= 8 else punchline_sentence

    titles = [
        curiosity_title,
        hook_title,
        action_title,
    ]

    # 4. 5 Categorical Hashtags based on content
    base_hashtags = ["#Shorts", "#Viral", "#Podcast", "#Mindset", "#Tips"]
    text_lower = cleaned_text.lower()
    if any(k in text_lower for k in ["tech", "code", "ai", "software", "system"]):
        base_hashtags[3] = "#Technology"
        base_hashtags[4] = "#AI"
    elif any(k in text_lower for k in ["business", "money", "growth", "founder"]):
        base_hashtags[3] = "#Business"
        base_hashtags[4] = "#Productivity"
    elif any(k in text_lower for k in ["health", "workout", "fitness", "food"]):
        base_hashtags[3] = "#Fitness"
        base_hashtags[4] = "#Health"

    # 5. Intelligent Local Ollama (Qwen 2.5) Enhancement with Safe Fallback
    if use_ollama:
        try:
            ollama_data = _query_ollama_metadata(cleaned_text, timeout=4.0)
            if ollama_data:
                if ollama_data.get("hook"):
                    hook_clean = ollama_data["hook"]
                if ollama_data.get("titles"):
                    titles = ollama_data["titles"]
                if ollama_data.get("hashtags"):
                    base_hashtags = ollama_data["hashtags"]
        except Exception:
            pass

    payload: dict[str, Any] = {
        "segment_id": segment_id,
        "duration_seconds": round(duration_seconds, 2),
        "energy_score": round(energy_score, 2),
        "hook": hook_clean,
        "titles": titles,
        "hashtags": base_hashtags,
        "transcript": cleaned_text,
    }

    if output_path:
        try:
            p = Path(output_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    return payload

