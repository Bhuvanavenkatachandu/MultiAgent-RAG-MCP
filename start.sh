#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

# Catch exit/interrupt signals to cleanly terminate both processes
trap 'echo -e "\nStopping servers..."; kill $(jobs -p) 2>/dev/null || true; exit' SIGINT SIGTERM EXIT

echo "=================================================="
echo " Starting PostgreSQL MCP + RAG (Backend & Frontend)"
echo "=================================================="

# 1. Start Backend in the background
echo "1. Launching Backend Server on http://localhost:8001..."
uv run mcp-server &
BACKEND_PID=$!

# Wait briefly for backend port
sleep 2

# 2. Start Frontend
echo "2. Launching Frontend Server on http://localhost:5173..."
cd frontend
npm run dev

# Wait for background processes
wait
