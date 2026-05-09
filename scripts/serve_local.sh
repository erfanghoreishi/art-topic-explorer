#!/bin/bash
#
# serve_local.sh — Generate local dataset from live Harvard API and start HTTP server.
# Usage: scripts/serve_local.sh [--max-pages N] [--port PORT]
#

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAX_PAGES=${MAX_PAGES:-"1"}
PORT=${PORT:-"8000"}

# Parse command-line args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-pages)
      MAX_PAGES="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

echo "📦 Harvard Art Knowledge Explorer — Local Serve"
echo "================================================"
echo "Repository: $REPO_ROOT"
echo "Max pages:  $MAX_PAGES"
echo "Port:       $PORT"
echo ""

# Activate venv if it exists
if [[ -d "$REPO_ROOT/.venv" ]]; then
  echo "🐍 Activating virtual environment..."
  source "$REPO_ROOT/.venv/bin/activate"
else
  echo "⚠️  No .venv found. Using system Python."
fi

# Generate dataset
echo "📥 Generating local dataset from live Harvard API..."
cd "$REPO_ROOT"
"${VENV_PYTHON:-./.venv/bin/python}" -m backend.src.local_demo --max-pages "$MAX_PAGES"

echo ""
echo "✅ Dataset generated successfully!"
echo "📁 Files:"
echo "   - frontend/dataset.json (legacy)"
echo "   - frontend/topics_index.json (paginated index)"
echo "   - frontend/topics/page_1.json .. page_N.json (paginated pages)"
echo ""
echo "🚀 Starting HTTP server on http://localhost:$PORT"
echo "   Press Ctrl+C to stop."
echo ""

# Start simple HTTP server
cd "$REPO_ROOT/frontend"
exec python3 -m http.server "$PORT"
