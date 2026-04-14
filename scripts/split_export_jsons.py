#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import boto3


ROOT = Path(__file__).resolve().parent.parent


def load_json_field(value: str):
    value = (value or "").strip()
    if not value:
        return None
    return json.loads(value)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def load_repo_env(env_path: Path) -> None:
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def build_s3_client():
    return boto3.client(
        "s3",
        region_name=os.environ["AWS_S3_REGION"],
        aws_access_key_id=os.environ["AWS_S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["AWS_S3_SECRET_KEY"],
    )


def extract_audio_s3_info(
    audio_url: str, default_bucket: str
) -> tuple[str, str] | None:
    audio_url = (audio_url or "").strip()
    if not audio_url:
        return None

    parsed = urlparse(audio_url)
    key = unquote(parsed.path.lstrip("/"))
    if not key:
        return None

    host = parsed.netloc.lower()
    if (
        host.startswith(f"{default_bucket}.s3.")
        or host == f"{default_bucket}.s3.amazonaws.com"
    ):
        return default_bucket, key

    bucket_prefix = f"{default_bucket}/"
    if key.startswith(bucket_prefix):
        return default_bucket, key[len(bucket_prefix) :]

    return default_bucket, key


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 split_export_jsons.py <export.csv>", file=sys.stderr)
        return 1

    csv_path = Path(sys.argv[1]).resolve()
    if not csv_path.is_file():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1

    load_repo_env(ROOT / ".env")
    for key in (
        "AWS_S3_BUCKET",
        "AWS_S3_REGION",
        "AWS_S3_ACCESS_KEY",
        "AWS_S3_SECRET_KEY",
    ):
        if not os.environ.get(key):
            print(f"Missing {key}", file=sys.stderr)
            return 1

    s3 = build_s3_client()
    output_dir = csv_path.parent / f"{csv_path.stem}_split"

    written_meta = 0
    written_reports = 0
    written_transcripts = 0
    downloaded_audio = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            session_id = (row.get("Session ID") or "").strip()
            if not session_id:
                continue

            session_dir = output_dir / session_id
            meta = {
                "username": (row.get("User") or "").strip() or None,
                "sessionId": session_id,
                "timestamp": (row.get("Started At") or "").strip() or None,
            }
            write_json(session_dir / "meta.json", meta)
            written_meta += 1

            report_json = load_json_field(row.get("Report JSON", ""))
            transcript_json = load_json_field(row.get("Transcript JSON", ""))

            if report_json is not None:
                write_json(session_dir / "report.json", report_json)
                written_reports += 1

            if transcript_json is not None:
                write_json(session_dir / "transcript.json", transcript_json)
                written_transcripts += 1

            audio_info = extract_audio_s3_info(
                row.get("Audio", ""), os.environ["AWS_S3_BUCKET"]
            )
            if audio_info is not None:
                bucket, key = audio_info
                destination_audio = session_dir / Path(key).name

                if not destination_audio.exists():
                    destination_audio.parent.mkdir(parents=True, exist_ok=True)
                    s3.download_file(bucket, key, str(destination_audio))
                    downloaded_audio += 1

    print(f"Wrote {written_meta} meta files to session folders in {output_dir}")
    print(f"Wrote {written_reports} report files to session folders in {output_dir}")
    print(
        f"Wrote {written_transcripts} transcript files to session folders in {output_dir}"
    )
    print(
        f"Downloaded {downloaded_audio} audio files to session folders in {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
