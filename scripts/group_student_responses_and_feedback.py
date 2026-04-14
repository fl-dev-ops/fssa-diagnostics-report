#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = ROOT / "data" / "analysis"


PROBLEM_THEMES: dict[int, list[str]] = {
    1: ["answer not captured/submitted", "transcript/text not shown"],
    2: ["conversation unclear from transcription"],
    3: ["transcript/text not shown", "latency/slow response", "exit/end control unclear"],
    4: ["answer not captured/submitted", "question skipped/auto-advance"],
    5: ["transcript/text not shown", "layout/positioning issue", "feature request: English learning/grammar support"],
    6: ["connection/agent join failure"],
    7: ["text rendering/random characters"],
    8: ["connection/agent join delay", "question skipped/auto-advance"],
    9: ["speech recognition/transcript inaccurate", "audio not recorded", "latency/slow response", "headphone/device continuity issue"],
    10: ["connection/agent join failure", "speech recognition/transcript inaccurate", "transcript/text not shown"],
    11: ["speech recognition/transcript inaccurate", "language detection issue"],
    12: ["feedback unclear from transcription"],
    13: ["mobile/laptop compatibility issue"],
    14: ["feedback unclear from transcription"],
    15: ["speech recognition/transcript inaccurate", "audio not recorded", "latency/slow response", "audio volume issue", "keyboard icon/confusing control"],
    16: ["feedback unclear from transcription"],
    17: ["question skipped/auto-advance", "live subtitle/transcript preview missing"],
    18: ["session auto-exit", "connection/reattempt failure", "latency/waiting"],
    19: ["live subtitle/transcript preview missing", "delete/undo control missing", "exit/end control unclear"],
    20: ["answer not captured/submitted", "latency/slow response", "transcript/text not shown"],
    21: ["audio clarity issue", "mic/recording quality issue"],
    22: ["speech recognition/transcript inaccurate", "message bubble not visible", "live transcript preview missing", "delete/stop control missing"],
    23: ["response not understanding student", "conversation repetitive/fixed"],
    24: ["speech recognition/transcript inaccurate", "agent startup delay", "positive: preferred-name prompt"],
    25: ["answer not captured/submitted"],
    26: ["mic interaction difficult"],
    27: ["speech recognition/transcript inaccurate", "audio break/voice break", "live caption missing", "layout width issue"],
    28: ["pause/delete control missing", "speech recognition/transcript inaccurate"],
    29: ["speech recognition/transcript inaccurate"],
    30: ["speech recognition/transcript inaccurate", "audio not heard/captured", "stop/send flow missing", "delete control missing", "positive: UI neat/simple"],
    31: ["layout/card sizing issue"],
    32: ["layout/card sizing issue", "live transcript preview missing", "delete control missing"],
    33: ["speech recognition/transcript inaccurate", "word framing/wording issue", "positive: questions clear/simple"],
    34: ["positive: reflective experience"],
    35: ["speech recognition/transcript inaccurate"],
    36: ["latency/loading", "session auto-finished before start", "unable to attend"],
    37: ["question skipped/auto-advance", "reply ignored"],
    38: ["speech recognition/transcript inaccurate", "answer not captured correctly"],
    39: ["positive: friendly communication", "session ended before student finished", "positive: text display useful", "positive: fast reply"],
}


def shorten(text: str, limit: int = 220) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    pair_df = pd.read_csv(ANALYSIS_DIR / "session_pair_relevance.csv")
    wa_df = pd.read_csv(ANALYSIS_DIR / "whatsapp_feedback_tagged.csv")

    intent_summary_rows: list[dict[str, object]] = []
    for intent, group in pair_df.groupby("intent", dropna=False):
        samples = group["student_text"].fillna("").astype(str)
        unique_samples: list[str] = []
        seen: set[str] = set()
        for sample in samples:
            normalized = " ".join(sample.split()).lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_samples.append(shorten(sample))
            if len(unique_samples) == 5:
                break

        intent_summary_rows.append(
            {
                "intent": intent,
                "student_turn_count": len(group),
                "unique_sample_responses": " | ".join(unique_samples),
            }
        )

    pd.DataFrame(intent_summary_rows).sort_values(
        ["student_turn_count", "intent"], ascending=[False, True]
    ).to_csv(ANALYSIS_DIR / "student_responses_by_intent.csv", index=False)

    wa_df["problem_themes"] = wa_df["row_id"].map(PROBLEM_THEMES).apply(
        lambda items: " | ".join(items or [])
    )
    wa_df.to_csv(ANALYSIS_DIR / "whatsapp_feedback_with_problem_themes.csv", index=False)

    theme_rows: list[dict[str, object]] = []
    all_themes = sorted(
        {
            theme
            for items in PROBLEM_THEMES.values()
            for theme in items
        }
    )
    for theme in all_themes:
        matches = wa_df[
            wa_df["row_id"].map(lambda row_id: theme in PROBLEM_THEMES.get(int(row_id), []))
        ].copy()
        example_lines = []
        for _, row in matches.head(5).iterrows():
            example_lines.append(f"{row['sender_name']}: {shorten(row['response'])}")
        theme_rows.append(
            {
                "problem_theme": theme,
                "feedback_count": len(matches),
                "buckets": " | ".join(sorted(matches["manual_bucket"].dropna().astype(str).unique())),
                "example_feedbacks": " || ".join(example_lines),
            }
        )

    pd.DataFrame(theme_rows).sort_values(
        ["feedback_count", "problem_theme"], ascending=[False, True]
    ).to_csv(ANALYSIS_DIR / "unique_student_problem_list.csv", index=False)

    summary_lines = [
        "# Student Responses Grouped By Intent And Problem",
        "",
        "## Transcript-side intent groups",
        "",
    ]

    intent_summary_df = pd.read_csv(ANALYSIS_DIR / "student_responses_by_intent.csv")
    for _, row in intent_summary_df.iterrows():
        summary_lines.append(f"- `{row['intent']}`: `{int(row['student_turn_count'])}` student turns")
        summary_lines.append(f"  Samples: {row['unique_sample_responses']}")

    summary_lines.extend(
        [
            "",
            "## Unique problem themes from WhatsApp feedback",
            "",
        ]
    )

    theme_df = pd.read_csv(ANALYSIS_DIR / "unique_student_problem_list.csv")
    for _, row in theme_df.iterrows():
        summary_lines.append(f"- `{row['problem_theme']}`: `{int(row['feedback_count'])}` feedback entries")
        summary_lines.append(f"  Examples: {row['example_feedbacks']}")

    (ANALYSIS_DIR / "student_intent_and_problem_summary.md").write_text(
        "\n".join(summary_lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
