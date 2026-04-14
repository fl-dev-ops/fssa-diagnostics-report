#!/usr/bin/env python3

from __future__ import annotations

import csv
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ANALYSIS_DIR = DATA_DIR / "analysis"
WHATSAPP_CSV = DATA_DIR / "whatsapp" / "whatsapp_feedback.csv"


WHATSAPP_TAGS: dict[int, str] = {
    1: "Technical",
    2: "Conversational",
    3: "UI/UX",
    4: "Technical",
    5: "Technical",
    6: "Technical",
    7: "UI/UX",
    8: "Technical",
    9: "Technical",
    10: "Technical",
    11: "Technical",
    12: "UI/UX",
    13: "Technical",
    14: "Technical",
    15: "Technical",
    16: "Technical",
    17: "UI/UX",
    18: "Technical",
    19: "UI/UX",
    20: "Technical",
    21: "Technical",
    22: "Technical",
    23: "Conversational",
    24: "Conversational",
    25: "Technical",
    26: "Technical",
    27: "Technical",
    28: "UI/UX",
    29: "Technical",
    30: "UI/UX",
    31: "UI/UX",
    32: "UI/UX",
    33: "Technical",
    34: "UI/UX",
    35: "Technical",
    36: "Technical",
    37: "Technical",
    38: "Technical",
    39: "Conversational",
}


@dataclass
class PairAssessment:
    intent: str
    relevance: str
    reason: str


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_phone(value: Any) -> str:
    digits = "".join(ch for ch in clean_text(value) if ch.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    return digits


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", clean_text(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def name_tokens(value: Any) -> set[str]:
    text = unicodedata.normalize("NFKD", clean_text(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) >= 3 and not token.isdigit()
    }


def contains_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def classify_intent(student_text: str) -> str:
    text = clean_text(student_text).lower()
    if not text:
        return "unclear"

    if contains_any(
        text,
        [
            "dream company",
            "company",
            "google",
            "amazon",
            "tcs",
            "infosys",
            "zoho",
            "wipro",
            "microsoft",
        ],
    ):
        return "dream company"

    if contains_any(text, ["backup", "second option", "alternative", "otherwise"]):
        return "backup plan"

    if contains_any(
        text,
        [
            "senior",
            "friend told",
            "my friend",
            "my brother",
            "my sister",
            "my cousin",
            "my father",
            "my mother",
            "teacher",
            "faculty",
            "mentor",
        ],
    ):
        return "senior reference"

    if contains_any(
        text,
        [
            "day in life",
            "day in the life",
            "day to day",
            "daily work",
            "every day",
            "routine",
            "what they do",
        ],
    ):
        return "day in life"

    if contains_any(
        text,
        [
            "job description",
            "jd",
            "responsibilit",
            "requirement",
            "eligibility",
            "qualificat",
            "salary",
            "package",
        ],
    ):
        return "JD awareness"

    if contains_any(
        text,
        [
            "skill",
            "skills",
            "tool",
            "tools",
            "python",
            "java",
            "mern",
            "react",
            "frontend",
            "backend",
            "full stack",
            "coding",
            "project",
            "develop",
            "sql",
            "excel",
        ],
    ):
        return "tools/skills"

    if contains_any(
        text,
        [
            "job",
            "role",
            "developer",
            "engineer",
            "tester",
            "analyst",
            "design",
            "hr",
            "interview",
            "prepare for",
            "want to become",
            "want to work as",
            "aspire",
        ],
    ):
        return "aspiring job"

    return "unclear"


def assess_relevance(student_text: str, agent_text: str) -> PairAssessment:
    intent = classify_intent(student_text)
    response = clean_text(agent_text).lower()
    student = clean_text(student_text).lower()

    if not response:
        return PairAssessment(intent, "Not Relevant", "No agent response after the student turn.")

    if intent == "unclear":
        if contains_any(
            response,
            ["tell me more", "can you explain", "could you share", "what do you mean", "can you tell me"],
        ):
            return PairAssessment(intent, "Relevant", "Sana asks a clarifying follow-up to an unclear student input.")
        return PairAssessment(intent, "Partially Relevant", "The student intent is unclear, so the follow-up is hard to judge precisely.")

    intent_keywords = {
        "aspiring job": ["job", "role", "prepare", "interview", "work", "become"],
        "dream company": ["company", "there", "workplace", "organization", "why that company"],
        "backup plan": ["backup", "alternative", "second option", "otherwise"],
        "senior reference": ["who told", "senior", "friend", "mentor", "inspired", "heard"],
        "day in life": ["day", "daily", "routine", "work on", "every day", "tasks"],
        "JD awareness": ["job description", "responsibil", "requirement", "salary", "package"],
        "tools/skills": ["skill", "tool", "stack", "technology", "learn", "project", "use"],
    }

    matched_keywords = [
        keyword for keyword in intent_keywords[intent] if keyword in response
    ]

    student_terms = {
        token
        for token in re.findall(r"[a-z0-9]+", student)
        if len(token) >= 4 and token not in {"that", "this", "with", "from", "have", "want"}
    }
    response_terms = {
        token
        for token in re.findall(r"[a-z0-9]+", response)
        if len(token) >= 4 and token not in {"that", "this", "with", "from", "have", "want"}
    }
    overlap = student_terms & response_terms

    if matched_keywords or len(overlap) >= 2:
        return PairAssessment(intent, "Relevant", "Sana follows the same topic raised by the student.")

    if contains_any(
        response,
        ["tell me more", "can you share", "what about", "why", "how", "could you", "would you"],
    ):
        return PairAssessment(intent, "Partially Relevant", "Sana follows up conversationally but the reply is only loosely tied to the student's topic.")

    return PairAssessment(intent, "Not Relevant", "Sana shifts away from the student's topic instead of addressing it directly.")


def match_whatsapp_feedback(sessions_df: pd.DataFrame, whatsapp_df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    matched_indices: set[int] = set()

    for _, row in sessions_df.drop_duplicates(subset=["user_id"]).iterrows():
        phone = normalize_phone(row["phone_number"])
        display = normalize_name(row["name"])
        preferred = normalize_name(row["preferred_name"])
        tokens = name_tokens(row["name"]) | name_tokens(row["preferred_name"])

        matches: list[pd.Series] = []
        for idx, wa in whatsapp_df.iterrows():
            is_match = False
            if phone and phone == wa["normalized_phone"]:
                is_match = True
            elif preferred and preferred == wa["normalized_sender_name"]:
                is_match = True
            elif display and display == wa["normalized_sender_name"]:
                is_match = True
            elif tokens and len(tokens & wa["sender_tokens"]) >= 2:
                is_match = True

            if is_match:
                matches.append(wa)
                matched_indices.add(idx)

        records.append(
            {
                "user_id": row["user_id"],
                "whatsapp_sender_names": " | ".join(sorted({clean_text(m['sender_name']) for m in matches})),
                "whatsapp_groups": " | ".join(
                    sorted(
                        {
                            part.strip()
                            for m in matches
                            for part in clean_text(m["groups"]).split("|")
                            if part.strip()
                        }
                    )
                ),
                "whatsapp_feedback": "\n\n".join(clean_text(m["response"]) for m in matches if clean_text(m["response"])),
                "whatsapp_primary_buckets": " | ".join(sorted({clean_text(m["manual_bucket"]) for m in matches if clean_text(m["manual_bucket"])})),
                "whatsapp_feedback_count": len(matches),
            }
        )

    matched_users_df = pd.DataFrame(records)
    unmatched = whatsapp_df.loc[~whatsapp_df.index.isin(matched_indices)].copy()
    unmatched.to_csv(ANALYSIS_DIR / "whatsapp_feedback_unmatched.csv", index=False)
    return matched_users_df


def build_pair_rows(transcript: dict[str, Any], session_row: pd.Series) -> list[dict[str, Any]]:
    messages = transcript.get("messages") or []
    rows: list[dict[str, Any]] = []

    for index, message in enumerate(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue

        student_text = clean_text(message.get("text"))
        agent_text = ""
        agent_timestamp = ""
        for next_message in messages[index + 1 :]:
            if isinstance(next_message, dict) and next_message.get("role") == "agent":
                agent_text = clean_text(next_message.get("text"))
                agent_timestamp = clean_text(next_message.get("timestamp"))
                break

        assessment = assess_relevance(student_text, agent_text)
        rows.append(
            {
                "session_id": session_row["session_id"],
                "user_id": session_row["user_id"],
                "name": session_row["name"],
                "email": session_row["email"],
                "session_status": session_row["session_status"],
                "report_status": session_row["report_status"],
                "student_timestamp": clean_text(message.get("timestamp")),
                "student_text": student_text,
                "agent_timestamp": agent_timestamp,
                "agent_text": agent_text,
                "intent": assessment.intent,
                "relevance": assessment.relevance,
                "reason": assessment.reason,
            }
        )

    return rows


def main() -> None:
    load_dotenv(ROOT / ".env")
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    query = """
    SELECT
        s.id AS session_id,
        s.status AS session_status,
        s."startedAt" AS started_at,
        s."endedAt" AS ended_at,
        s.transcript,
        u.id AS user_id,
        u.name,
        u.email,
        u."phoneNumber" AS phone_number,
        p."preferredName" AS preferred_name,
        p.institution,
        p.degree,
        p.stream,
        p."yearOfStudy" AS year_of_study,
        p.coach,
        r.status AS report_status,
        r."reportJson" AS report_json
    FROM pre_diagnostic_session s
    JOIN "user" u ON s."userId" = u.id
    LEFT JOIN profile p ON p."userId" = u.id
    LEFT JOIN pre_diagnostic_session_report r ON r."sessionId" = s.id
    ORDER BY s."startedAt" ASC
    """
    sessions_df = pd.read_sql_query(query, conn)
    conn.close()

    sessions_df["started_at"] = pd.to_datetime(sessions_df["started_at"], utc=True, errors="coerce")
    sessions_df["ended_at"] = pd.to_datetime(sessions_df["ended_at"], utc=True, errors="coerce")
    sessions_df["duration_seconds"] = (
        sessions_df["ended_at"] - sessions_df["started_at"]
    ).dt.total_seconds()
    sessions_df["session_bucket"] = sessions_df["session_status"].map(
        {
            "REPORT_READY": "completed_with_report",
            "COMPLETED": "completed_no_report",
            "STARTED": "dropped_midway",
        }
    ).fillna("other")

    for column in [
        "name",
        "email",
        "phone_number",
        "preferred_name",
        "institution",
        "degree",
        "stream",
        "coach",
    ]:
        sessions_df[f"has_{column}"] = sessions_df[column].apply(lambda value: bool(clean_text(value)))
    sessions_df["has_year_of_study"] = sessions_df["year_of_study"].notna()
    sessions_df["all_profile_fields_present"] = (
        sessions_df[
            [
                "has_name",
                "has_email",
                "has_phone_number",
                "has_preferred_name",
                "has_institution",
                "has_degree",
                "has_stream",
                "has_year_of_study",
                "has_coach",
            ]
        ]
        .all(axis=1)
    )

    whatsapp_df = pd.read_csv(WHATSAPP_CSV).fillna("")
    whatsapp_df["row_id"] = range(1, len(whatsapp_df) + 1)
    whatsapp_df["manual_bucket"] = whatsapp_df["row_id"].map(WHATSAPP_TAGS).fillna("Technical")
    whatsapp_df["normalized_phone"] = whatsapp_df["phone_number"].apply(normalize_phone)
    whatsapp_df["normalized_sender_name"] = whatsapp_df["sender_name"].apply(normalize_name)
    whatsapp_df["sender_tokens"] = whatsapp_df["sender_name"].apply(name_tokens)
    whatsapp_df.to_csv(ANALYSIS_DIR / "whatsapp_feedback_tagged.csv", index=False)

    matched_feedback_df = match_whatsapp_feedback(sessions_df, whatsapp_df)
    sessions_df = sessions_df.merge(matched_feedback_df, on="user_id", how="left")

    sessions_df["report_generated"] = sessions_df["report_status"].eq("READY")
    sessions_df["completed_session"] = sessions_df["session_status"].isin(["REPORT_READY", "COMPLETED"])
    sessions_df["started_at_iso"] = sessions_df["started_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    sessions_df["ended_at_iso"] = sessions_df["ended_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    session_export_columns = [
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
        "whatsapp_feedback_count",
        "whatsapp_sender_names",
        "whatsapp_groups",
        "whatsapp_primary_buckets",
        "whatsapp_feedback",
    ]
    sessions_df[session_export_columns].to_csv(
        ANALYSIS_DIR / "user_sessions_feedback.csv", index=False
    )

    completed_sessions = sessions_df.loc[sessions_df["completed_session"]].copy()
    pair_rows: list[dict[str, Any]] = []
    for _, row in completed_sessions.iterrows():
        transcript = row["transcript"] if isinstance(row["transcript"], dict) else {}
        pair_rows.extend(build_pair_rows(transcript, row))

    pair_df = pd.DataFrame(pair_rows)
    if not pair_df.empty:
        pair_df.to_csv(ANALYSIS_DIR / "session_pair_relevance.csv", index=False)

    relevance_summary = pd.DataFrame()
    if not pair_df.empty:
        relevance_summary = (
            pair_df.groupby("session_id", as_index=False)
            .agg(
                total_pairs=("relevance", "count"),
                relevant_pairs=("relevance", lambda col: int((col == "Relevant").sum())),
                partially_relevant_pairs=("relevance", lambda col: int((col == "Partially Relevant").sum())),
                not_relevant_pairs=("relevance", lambda col: int((col == "Not Relevant").sum())),
            )
        )
        relevance_summary["relevance_pct"] = (
            relevance_summary["relevant_pairs"] / relevance_summary["total_pairs"] * 100
        ).round(2)
        relevance_summary["mostly_not_relevant"] = (
            relevance_summary["not_relevant_pairs"] > relevance_summary["relevant_pairs"]
        )
        relevance_summary.to_csv(
            ANALYSIS_DIR / "session_relevance_summary.csv", index=False
        )

    aggregate_rows = [
        {
            "metric": "sessions_initiated",
            "value": int(len(sessions_df)),
        },
        {
            "metric": "completed_with_report",
            "value": int((sessions_df["session_bucket"] == "completed_with_report").sum()),
        },
        {
            "metric": "completed_no_report",
            "value": int((sessions_df["session_bucket"] == "completed_no_report").sum()),
        },
        {
            "metric": "dropped_midway",
            "value": int((sessions_df["session_bucket"] == "dropped_midway").sum()),
        },
        {
            "metric": "sessions_with_all_profile_fields_present",
            "value": int(sessions_df["all_profile_fields_present"].sum()),
        },
        {
            "metric": "average_call_duration_seconds_completed_with_report",
            "value": round(
                float(
                    sessions_df.loc[
                        sessions_df["session_bucket"] == "completed_with_report",
                        "duration_seconds",
                    ].dropna().mean()
                    or 0
                ),
                2,
            ),
        },
    ]

    if not pair_df.empty:
        aggregate_rows.extend(
            [
                {
                    "metric": "overall_relevance_pct",
                    "value": round(
                        float((pair_df["relevance"] == "Relevant").mean() * 100), 2
                    ),
                },
                {
                    "metric": "overall_partial_relevance_pct",
                    "value": round(
                        float((pair_df["relevance"] == "Partially Relevant").mean() * 100),
                        2,
                    ),
                },
                {
                    "metric": "overall_not_relevant_pct",
                    "value": round(
                        float((pair_df["relevance"] == "Not Relevant").mean() * 100), 2
                    ),
                },
                {
                    "metric": "sessions_mostly_not_relevant",
                    "value": int(
                        relevance_summary["mostly_not_relevant"].sum()
                        if not relevance_summary.empty
                        else 0
                    ),
                },
            ]
        )

    pd.DataFrame(aggregate_rows).to_csv(
        ANALYSIS_DIR / "aggregate_metrics.csv", index=False
    )

    field_counts = pd.DataFrame(
        [
            {"field": "name", "completed_sessions": int(sessions_df["has_name"].sum())},
            {"field": "email", "completed_sessions": int(sessions_df["has_email"].sum())},
            {"field": "phone_number", "completed_sessions": int(sessions_df["has_phone_number"].sum())},
            {"field": "preferred_name", "completed_sessions": int(sessions_df["has_preferred_name"].sum())},
            {"field": "institution", "completed_sessions": int(sessions_df["has_institution"].sum())},
            {"field": "degree", "completed_sessions": int(sessions_df["has_degree"].sum())},
            {"field": "stream", "completed_sessions": int(sessions_df["has_stream"].sum())},
            {"field": "year_of_study", "completed_sessions": int(sessions_df["has_year_of_study"].sum())},
            {"field": "coach", "completed_sessions": int(sessions_df["has_coach"].sum())},
        ]
    )
    field_counts.to_csv(ANALYSIS_DIR / "profile_field_completion.csv", index=False)


if __name__ == "__main__":
    main()
