"""100% Local Viral Title, Hook & SEO Engine.

Heuristic extraction of viral social media hooks, 3 title variants,
and categorical hashtags from clip transcripts. Zero cloud API calls.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


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


def generate_clip_metadata(
    segment_id: str,
    transcript_text: str,
    duration_seconds: float,
    energy_score: float = 0.8,
    output_path: str | Path | None = None,
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

    # 1. Hook Extraction: Look for question or punchy opening clause
    hook = sentences[0]
    for s in sentences[:3]:
        s_lower = s.lower()
        if any(trigger in s_lower for trigger in ["give me", "what if", "how to", "why", "never", "always", "the secret", "stop"]):
            hook = s
            break
        if len(s.split()) <= 10:
            hook = s
            break

    # Clean hook of trailing punct
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
