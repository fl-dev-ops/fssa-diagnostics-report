#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = ROOT / "data" / "analysis"
EXPORT_SPLIT_DIR = ROOT / "data" / "exports" / "2026-04-10T09-48_export_split"
INPUT_CSV = ANALYSIS_DIR / "user_sessions_feedback.csv"
OUTPUT_CSV = ANALYSIS_DIR / "shareable_student_sessions_full.csv"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def json_text(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False)


def transcript_to_text(transcript: Any) -> str:
    if not isinstance(transcript, dict):
        return ""

    messages = transcript.get("messages") or []
    lines: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = clean_text(message.get("role")) or "unknown"
        text = clean_text(message.get("text"))
        timestamp = clean_text(message.get("timestamp"))
        if not text:
            continue
        prefix = f"[{timestamp}] " if timestamp else ""
        lines.append(f"{prefix}{role}: {text}")
    return "\n".join(lines)


def main() -> None:
    df = pd.read_csv(INPUT_CSV)

    transcript_json_texts: list[str] = []
    transcript_texts: list[str] = []
    report_json_texts: list[str] = []
    meta_json_texts: list[str] = []

    for _, row in df.iterrows():
        session_id = clean_text(row["session_id"])
        session_dir = EXPORT_SPLIT_DIR / session_id

        transcript_json = load_json(session_dir / "transcript.json")
        report_json = load_json(session_dir / "report.json")
        meta_json = load_json(session_dir / "meta.json")

        transcript_json_texts.append(json_text(transcript_json))
        transcript_texts.append(transcript_to_text(transcript_json))
        report_json_texts.append(json_text(report_json))
        meta_json_texts.append(json_text(meta_json))

    export_df = df.copy()
    export_df.insert(export_df.columns.get_loc("session_id"), "meta_json", meta_json_texts)
    export_df["transcript_text"] = transcript_texts
    export_df["transcript_json"] = transcript_json_texts
    export_df["report_json"] = report_json_texts

    ordered_columns = [
        "user_id",
        "name",
        "email",
        "phone_number",
        "preferred_name",
        "institution",
        "degree",
        "stream",
        "year_of_study",
        "coach",
        "meta_json",
        "session_id",
        "session_status",
        "report_status",
        "session_bucket",
        "report_generated",
        "completed_session",
        "started_at_iso",
        "ended_at_iso",
        "duration_seconds",
        "has_name",
        "has_email",
        "has_phone_number",
        "has_preferred_name",
        "has_institution",
        "has_degree",
        "has_stream",
        "has_year_of_study",
        "has_coach",
        "all_profile_fields_present",
        "transcript_text",
        "transcript_json",
        "report_json",
        "whatsapp_feedback_count",
        "whatsapp_sender_names",
        "whatsapp_groups",
        "whatsapp_primary_buckets",
        "whatsapp_feedback",
    ]

    export_df[ordered_columns].to_csv(OUTPUT_CSV, index=False)
    print(f"Wrote {len(export_df)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
