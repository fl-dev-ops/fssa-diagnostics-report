#!/usr/bin/env python3
"""Teacher-facing Streamlit app for diagnostic report review."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "analysis" / "shareable_student_sessions_full.csv"

STATUS_COLORS = {
    "Strong": "#6fcf97",
    "Clear": "#b8e6c9",
    "Moderate": "#f2cf7a",
    "Emerging": "#b8d6f2",
    "Low": "#f1b4b4",
    "Unclear": "#d98585",
    "—": "#ecece7",
}

CLARITY_ORDER = ["Clear", "Moderate", "Unclear", "—"]
AWARENESS_ORDER = ["Strong", "Emerging", "Low", "—"]
SALARY_BUCKET_ORDER = [
    "Below 15k",
    "15k-30k",
    "30k-50k",
    "50k-1L",
    "Above 1L",
    "Unclear",
    "Not shared",
]
DIMENSION_FIELDS = {
    "JD Awareness": "jd_awareness",
    "Skills Research": "skills_research",
    "Tools & Role Clarity": "tools_and_role_clarity",
    "Company Clarity": "company_clarity",
    "Salary Clarity": "salary_clarity",
}

st.set_page_config(
    page_title="Teacher Diagnostic Report", page_icon="📊", layout="wide"
)


def normalize_text(value: Any, fallback: str = "—") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def parse_report_json(value: Any) -> dict[str, Any]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    text = str(value).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def map_clarity_status(value: Any) -> str:
    raw = normalize_text(value)
    mapping = {
        "Strong": "Clear",
        "Good": "Clear",
        "Clear": "Clear",
        "Rough idea": "Moderate",
        "Some gaps": "Moderate",
        "Not Enough": "Unclear",
        "Not yet": "Unclear",
        "Unclear": "Unclear",
        "—": "—",
    }
    return mapping.get(raw, raw)


def map_awareness_status(value: Any) -> str:
    raw = normalize_text(value)
    mapping = {
        "Strong": "Strong",
        "Clear": "Emerging",
        "Unclear": "Low",
        "—": "—",
    }
    return mapping.get(raw, raw)


def get_best_student_rows(df: pd.DataFrame) -> pd.DataFrame:
    ranked = df.copy()
    ranked["started_at_iso"] = pd.to_datetime(ranked["started_at_iso"], errors="coerce")
    ranked["report_generated_rank"] = (
        ranked["report_generated"].fillna(False).astype(int)
    )
    ranked["completed_session_rank"] = (
        ranked["completed_session"].fillna(False).astype(int)
    )
    ranked = ranked.sort_values(
        [
            "user_id",
            "report_generated_rank",
            "completed_session_rank",
            "started_at_iso",
        ],
        ascending=[True, False, False, False],
    )
    return ranked.drop_duplicates("user_id").copy()


@st.cache_data
def load_data() -> pd.DataFrame:
    raw_df = pd.read_csv(DATA_PATH)
    best_df = get_best_student_rows(raw_df)
    parsed_reports = best_df["report_json"].apply(parse_report_json)

    student_df = pd.DataFrame(
        {
            "Student": best_df["preferred_name"].apply(normalize_text),
            "Aspiring Job": parsed_reports.apply(
                lambda r: normalize_text(r.get("aiming_for"))
            ),
            "Salary": parsed_reports.apply(
                lambda r: normalize_text(r.get("salary_expectation"))
            ),
            "Aspiring Company": parsed_reports.apply(
                lambda r: ", ".join(r.get("companies_mentioned") or [])
                if isinstance(r.get("companies_mentioned"), list)
                and r.get("companies_mentioned")
                else "—"
            ),
            "Awareness": parsed_reports.apply(
                lambda r: map_awareness_status(r.get("job_awareness_category"))
            ),
            "Backup Plan": parsed_reports.apply(
                lambda r: normalize_text(r.get("backup"))
            ),
            "Salary Clarity": parsed_reports.apply(
                lambda r: map_clarity_status(
                    (r.get("job_research_breakdown") or {}).get("salary_clarity")
                )
            ),
            "JD Awareness": parsed_reports.apply(
                lambda r: map_clarity_status(
                    (r.get("job_research_breakdown") or {}).get("jd_awareness")
                )
            ),
            "Company Clarity": parsed_reports.apply(
                lambda r: map_clarity_status(
                    (r.get("job_research_breakdown") or {}).get("company_clarity")
                )
            ),
            "Skills Research": parsed_reports.apply(
                lambda r: map_clarity_status(
                    (r.get("job_research_breakdown") or {}).get("skills_research")
                )
            ),
            "Tools & Role Clarity": parsed_reports.apply(
                lambda r: map_clarity_status(
                    (r.get("job_research_breakdown") or {}).get(
                        "tools_and_role_clarity"
                    )
                )
            ),
        }
    )
    student_df.loc[student_df["Student"].eq("—"), "Student"] = best_df["name"].apply(
        normalize_text
    )
    student_df["Salary Bucket"] = student_df["Salary"].apply(normalize_salary_bucket)
    student_df["unclear_count"] = sum(
        student_df[label].eq("Unclear") for label in DIMENSION_FIELDS
    )
    student_df["moderate_count"] = sum(
        student_df[label].eq("Moderate") for label in DIMENSION_FIELDS
    )
    student_df["missing_count"] = (
        student_df["Salary"].eq("—").astype(int)
        + student_df["Aspiring Company"].eq("—").astype(int)
        + student_df["Backup Plan"].eq("—").astype(int)
    )
    awareness_rank = {"Low": 0, "Emerging": 1, "Strong": 2, "—": 3}
    student_df["awareness_rank"] = student_df["Awareness"].map(awareness_rank).fillna(9)
    return student_df.sort_values("Student").reset_index(drop=True)


def count_statuses(df: pd.DataFrame, column: str, order: list[str]) -> Counter:
    counter = Counter()
    for value in df[column]:
        counter[normalize_text(value)] += 1

    ordered = Counter()
    for label in order:
        if counter.get(label):
            ordered[label] = counter[label]
    return ordered


def render_vertical_bar_chart(title: str, counts: Counter, order: list[str]) -> None:
    labels = [label for label in order if counts.get(label)]
    values = [counts[label] for label in labels]
    colors = [STATUS_COLORS.get(label, "#d9d5cb") for label in labels]
    option = {
        "animation": False,
        "grid": {
            "left": 24,
            "right": 12,
            "top": 42,
            "bottom": 24,
            "containLabel": True,
        },
        "title": {
            "text": title,
            "left": "left",
            "textStyle": {"fontSize": 14, "fontWeight": 600},
        },
        "xAxis": {"type": "category", "data": labels, "axisTick": {"show": False}},
        "yAxis": {"type": "value", "minInterval": 1},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "series": [
            {
                "type": "bar",
                "data": [
                    {"value": value, "itemStyle": {"color": color}}
                    for value, color in zip(values, colors)
                ],
                "label": {"show": True, "position": "top"},
                "barWidth": "48%",
            }
        ],
    }
    chart_id = f"echart-{title.lower().replace(' ', '-')}"
    components.html(
        f"""
        <div id="{chart_id}" style="width: 100%; height: 300px;"></div>
        <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
        <script>
        const chart = echarts.init(document.getElementById("{chart_id}"));
        const option = {json.dumps(option)};
        chart.setOption(option);
        window.addEventListener("resize", function() {{
            chart.resize();
        }});
        </script>
        """,
        height=300,
    )


def normalize_salary_bucket(value: Any) -> str:
    text = normalize_text(value)
    if text == "—":
        return "Not shared"

    lowered = text.lower().replace(",", "").strip()
    numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", lowered)]
    if not numbers:
        return "Unclear"

    amount = max(numbers)
    if "lakh" in lowered or "lac" in lowered:
        amount *= 100000
    elif amount < 1000 and "k" in lowered:
        amount *= 1000

    if amount < 15000:
        return "Below 15k"
    if amount < 30000:
        return "15k-30k"
    if amount < 50000:
        return "30k-50k"
    if amount < 100000:
        return "50k-1L"
    return "Above 1L"


def with_status_dot(value: Any) -> str:
    label = normalize_text(value)
    color_map = {
        "Strong": "🟢",
        "Clear": "🟢",
        "Moderate": "🟡",
        "Emerging": "🔵",
        "Low": "🔴",
        "Unclear": "🔴",
        "—": "⚪",
    }
    return f"{color_map.get(label, '⚪')} {label}"


def build_teacher_insights(df: pd.DataFrame) -> list[str]:
    insights: list[str] = []

    awareness_counts = count_statuses(df, "Awareness", AWARENESS_ORDER)
    dimension_counts = {
        label: count_statuses(df, label, CLARITY_ORDER) for label in DIMENSION_FIELDS
    }

    tools_unclear = dimension_counts["Tools & Role Clarity"].get("Unclear", 0)
    if tools_unclear:
        insights.append(
            f"Priority group: {tools_unclear} students still do not have enough tools and role clarity. Use teacher check-ins to narrow them to one specific target job."
        )
    if awareness_counts.get("Low", 0):
        insights.append(
            f"Awareness risk: {awareness_counts['Low']} students have low awareness of the job path. These students likely need examples of actual roles, expectations, and entry routes."
        )

    salary_unclear = dimension_counts["Salary Clarity"].get("Unclear", 0)
    if salary_unclear:
        insights.append(
            f"Salary clarity gap: {salary_unclear} students still cannot state a realistic salary range. Add benchmarking examples during mentoring."
        )

    company_unclear = dimension_counts["Company Clarity"].get("Unclear", 0)
    if company_unclear:
        insights.append(
            f"Company research gap: {company_unclear} students do not yet have enough company clarity. Guided shortlists can make their search more concrete."
        )

    missing_salary = int(df["Salary"].eq("—").sum())
    if missing_salary:
        insights.append(
            f"Salary gap: {missing_salary} students have not stated a salary range. Add salary benchmarking during mentoring so expectations become more concrete."
        )

    missing_company = int(df["Aspiring Company"].eq("—").sum())
    if missing_company:
        insights.append(
            f"Company targeting gap: {missing_company} students have not named aspiration companies. This usually signals weak research depth and can be improved with guided company shortlists."
        )

    missing_backup = int(df["Backup Plan"].eq("—").sum())
    if missing_backup:
        insights.append(
            f"Fallback planning gap: {missing_backup} students do not yet have a backup plan. Teachers can use this to identify students who may struggle when their first choice role is unavailable."
        )

    return insights


student_df = load_data()
students_total = len(student_df)
cohort_date = pd.Timestamp.now().strftime("%d %B %Y")

awareness_counts = count_statuses(student_df, "Awareness", AWARENESS_ORDER)
dimension_counts = {
    label: count_statuses(student_df, label, CLARITY_ORDER)
    for label in DIMENSION_FIELDS
}
salary_bucket_counts = count_statuses(student_df, "Salary Bucket", SALARY_BUCKET_ORDER)
teacher_focus = build_teacher_insights(student_df)

st.title("Student Job Readiness Dashboard")
st.caption(f"Snapshot date: {cohort_date}")

st.metric(
    "Students in cohort", students_total, help="One best session selected per student."
)

st.subheader("Overview")
render_vertical_bar_chart("Awareness", awareness_counts, AWARENESS_ORDER)
render_vertical_bar_chart("Salary Range", salary_bucket_counts, SALARY_BUCKET_ORDER)

st.subheader("Teacher insights")
if teacher_focus:
    for item in teacher_focus:
        st.write(f"- {item}")
else:
    st.write("- No major gaps detected in the current cohort snapshot.")

st.subheader("Dimension breakdown")
dim_col_1, dim_col_2 = st.columns(2)
for index, label in enumerate(DIMENSION_FIELDS):
    target_col = dim_col_1 if index % 2 == 0 else dim_col_2
    with target_col:
        render_vertical_bar_chart(label, dimension_counts[label], CLARITY_ORDER)

st.subheader("Student breakdown")
search_col, awareness_col = st.columns([1.4, 1])
with search_col:
    search = st.text_input("Search", placeholder="Type a student, job, or company")
with awareness_col:
    awareness_filter = st.selectbox(
        "Awareness",
        ["All"]
        + [
            label
            for label in AWARENESS_ORDER
            if label in student_df["Awareness"].values
        ],
    )

filtered_df = student_df.copy()
if awareness_filter != "All":
    filtered_df = filtered_df[filtered_df["Awareness"] == awareness_filter]
if search.strip():
    term = search.strip().lower()
    filtered_df = filtered_df[
        filtered_df["Student"].str.lower().str.contains(term, na=False)
        | filtered_df["Aspiring Job"].str.lower().str.contains(term, na=False)
        | filtered_df["Aspiring Company"].str.lower().str.contains(term, na=False)
    ]

table_columns = [
    "Student",
    "Aspiring Job",
    "Awareness",
    "JD Awareness",
    "Skills Research",
    "Tools & Role Clarity",
    "Company Clarity",
    "Salary Clarity",
    "Salary",
    "Salary Bucket",
    "Aspiring Company",
    "Backup Plan",
]

display_df = filtered_df[table_columns].copy()
categorical_columns = [
    "Awareness",
    "JD Awareness",
    "Skills Research",
    "Tools & Role Clarity",
    "Company Clarity",
    "Salary Clarity",
]
for column in categorical_columns:
    display_df[column] = display_df[column].apply(with_status_dot)

st.dataframe(
    display_df,
    width="stretch",
    hide_index=True,
    column_config={
        "Aspiring Job": st.column_config.TextColumn(width="medium"),
        "Aspiring Company": st.column_config.TextColumn(width="medium"),
        "Backup Plan": st.column_config.TextColumn(width="large"),
        "Awareness": st.column_config.TextColumn("Awareness"),
        "JD Awareness": st.column_config.TextColumn("JD Awareness"),
        "Skills Research": st.column_config.TextColumn("Skills Research"),
        "Tools & Role Clarity": st.column_config.TextColumn("Tools & Role Clarity"),
        "Company Clarity": st.column_config.TextColumn("Company Clarity"),
        "Salary Clarity": st.column_config.TextColumn("Salary Clarity"),
    },
)
