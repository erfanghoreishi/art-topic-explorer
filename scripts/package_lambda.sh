#!/usr/bin/env bash
set -euo pipefail

# Build a single Lambda zip that contains both handlers:
# - ingestion_lambda.handler
# - admin_lambda.handler

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/build"
PKG_DIR="${BUILD_DIR}/python"
OUTPUT_ZIP="${1:-${BUILD_DIR}/lambda_bundle.zip}"

echo "[package] root: ${ROOT_DIR}"
echo "[package] output: ${OUTPUT_ZIP}"

rm -rf "${BUILD_DIR}"
mkdir -p "${PKG_DIR}"

python3 -m pip install -r "${ROOT_DIR}/backend/requirements.txt" -t "${PKG_DIR}"
cp -R "${ROOT_DIR}/backend/src" "${PKG_DIR}/backend_src"

cat > "${PKG_DIR}/ingestion_lambda.py" <<'PY'
from backend_src.lambda_handler import handler
PY

cat > "${PKG_DIR}/admin_lambda.py" <<'PY'
from backend_src.admin_handler import handler
PY

(
  cd "${PKG_DIR}"
  zip -r "${OUTPUT_ZIP}" .
)

echo "[package] done"

