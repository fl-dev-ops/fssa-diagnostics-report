#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # Load repo-local AWS_S3_* variables if present.
  source "$ENV_FILE"
  set +a
fi

: "${AWS_S3_BUCKET:?Missing AWS_S3_BUCKET}"
: "${AWS_S3_REGION:?Missing AWS_S3_REGION}"
: "${AWS_S3_ACCESS_KEY:?Missing AWS_S3_ACCESS_KEY}"
: "${AWS_S3_SECRET_KEY:?Missing AWS_S3_SECRET_KEY}"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is not installed or not on PATH."
  exit 1
fi

DEST_DIR="$ROOT_DIR/data/agents/raw_sessions"
mkdir -p "$DEST_DIR"

AWS_ACCESS_KEY_ID="$AWS_S3_ACCESS_KEY" \
AWS_SECRET_ACCESS_KEY="$AWS_S3_SECRET_KEY" \
AWS_DEFAULT_REGION="$AWS_S3_REGION" \
aws s3 cp "s3://$AWS_S3_BUCKET/agents/" "$DEST_DIR/" --recursive

echo "Downloaded S3 assets into $DEST_DIR"
