#!/usr/bin/env python3

from __future__ import annotations

import csv
import os
import re
import shutil
import sys
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path

import whisper


ROOT = Path(__file__).resolve().parent.parent
WHATSAPP_DIR = ROOT / "data" / "whatsapp"
UNZIPPED_DIR = WHATSAPP_DIR / "unzipped"
OUTPUT_CSV = WHATSAPP_DIR / "whatsapp_feedback.csv"
ZIP_GLOB = "WhatsApp*.zip"
DEFAULT_MODEL_NAME = os.getenv("WHISPER_MODEL", "small.en")

MESSAGE_RE = re.compile(
    r"^\u200e?\[(?P<timestamp>.*?)\]\s(?P<sender>[^:]+):\s?(?P<body>.*)$"
)
ATTACHED_RE = re.compile(r"<attached:\s*([^>]+)>")
PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")


@dataclass
class Message:
    timestamp: str
    sender: str
    body: str


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\u200e", "").replace("\u202f", " ").replace("\xa0", " ")
    return value.strip()


def normalize_sender(sender: str) -> str:
    sender = normalize_text(sender)
    if sender.startswith("~"):
        sender = sender[1:].strip()
    return sender


def extract_phone(sender: str) -> str:
    match = PHONE_RE.search(sender)
    if not match:
        return ""
    return re.sub(r"\D", "", match.group(0))


def unzip_exports() -> list[Path]:
    if UNZIPPED_DIR.exists():
        shutil.rmtree(UNZIPPED_DIR)
    UNZIPPED_DIR.mkdir(parents=True)

    extracted_dirs: list[Path] = []
    for zip_path in sorted(WHATSAPP_DIR.glob(ZIP_GLOB)):
        target_dir = UNZIPPED_DIR / zip_path.stem
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(target_dir)
        extracted_dirs.append(target_dir)
    return extracted_dirs


def parse_chat(chat_path: Path) -> list[Message]:
    messages: list[Message] = []
    current: Message | None = None

    for raw_line in chat_path.read_text(
        encoding="utf-8-sig", errors="replace"
    ).splitlines():
        line = normalize_text(raw_line)
        if not line:
            if current is not None:
                current.body += "\n"
            continue

        match = MESSAGE_RE.match(line)
        if match:
            if current is not None:
                messages.append(current)
            current = Message(
                timestamp=normalize_text(match.group("timestamp")),
                sender=normalize_sender(match.group("sender")),
                body=normalize_text(match.group("body")),
            )
            continue

        if current is not None:
            current.body = f"{current.body}\n{line}".strip()

    if current is not None:
        messages.append(current)
    return messages


def should_skip_message(body: str) -> bool:
    text = body.strip().lower()
    if not text:
        return True
    skipped = {
        "messages and calls are end-to-end encrypted. only people in this chat can read, listen to, or share them.",
        "image omitted",
        "video omitted",
        "sticker omitted",
        "gif omitted",
        "document omitted",
        "audio omitted",
        "this message was deleted.",
        "waiting for this message. this may take a while.",
        "you're now an admin",
    }
    if text in skipped:
        return True
    if (
        " created this group" in text
        or " created group " in text
        or " added you" in text
        or " added " in text
        or " removed " in text
    ):
        return True
    return False


def transcribe_audio(model, audio_path: Path) -> str:
    result = model.transcribe(str(audio_path), fp16=False, language="en")
    return normalize_text(result.get("text", ""))


def process_exports(model_name: str = DEFAULT_MODEL_NAME) -> None:
    extracted_dirs = unzip_exports()
    model = whisper.load_model(model_name)
    feedback_by_sender: dict[tuple[str, str], dict[str, object]] = {}

    for export_dir in extracted_dirs:
        chat_path = export_dir / "_chat.txt"
        if not chat_path.is_file():
            continue

        group_name = export_dir.name
        for message in parse_chat(chat_path):
            if should_skip_message(message.body):
                continue

            attachment_match = ATTACHED_RE.search(message.body)
            body_parts: list[str] = []
            if attachment_match:
                attachment_name = attachment_match.group(1).strip()
                attachment_path = export_dir / attachment_name
                if (
                    attachment_path.suffix.lower() in {".opus", ".mp3", ".m4a", ".wav"}
                    and attachment_path.is_file()
                ):
                    transcription = transcribe_audio(model, attachment_path)
                    if transcription:
                        body_parts.append(f"[Audio note transcription] {transcription}")

                cleaned_body = ATTACHED_RE.sub("", message.body).strip()
                cleaned_body = cleaned_body.replace("audio omitted", "").strip()
                if cleaned_body:
                    body_parts.insert(0, cleaned_body)
            else:
                body_parts.append(message.body)

            final_body = "\n".join(part for part in body_parts if part).strip()
            if not final_body:
                continue

            sender_name = message.sender
            phone_number = extract_phone(sender_name)
            key = (phone_number or "", sender_name)
            if key not in feedback_by_sender:
                feedback_by_sender[key] = {
                    "phone_number": phone_number,
                    "sender_name": sender_name,
                    "groups": set(),
                    "responses": [],
                }

            record = feedback_by_sender[key]
            record["groups"].add(group_name)
            record["responses"].append(f"[{message.timestamp}] {final_body}")

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["phone_number", "sender_name", "groups", "response"],
        )
        writer.writeheader()
        for key in sorted(
            feedback_by_sender, key=lambda item: (item[0] or "", item[1].lower())
        ):
            record = feedback_by_sender[key]
            writer.writerow(
                {
                    "phone_number": record["phone_number"],
                    "sender_name": record["sender_name"],
                    "groups": " | ".join(sorted(record["groups"])),
                    "response": "\n\n".join(record["responses"]),
                }
            )


if __name__ == "__main__":
    selected_model = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL_NAME
    process_exports(selected_model)
