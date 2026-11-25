#!/usr/bin/env bash
set -e

echo "=== Starting Build Process ==="

# 1. Install Node.js & npx if missing (required for PostgreSQL MCP server)
if ! command -v npx &> /dev/null; then
    echo "--- Node.js / npx not found. Installing Node.js & npm ---"
    if command -v apt-get &> /dev/null; then
        apt-get update -y && apt-get install -y curl
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y nodejs
    else
        echo "Downloading portable Node.js binaries..."
        mkdir -p "$HOME/.local"
        curl -fsSL https://nodejs.org/dist/v20.18.0/node-v20.18.0-linux-x64.tar.xz | tar -xJ -C "$HOME/.local"
        export PATH="$HOME/.local/node-v20.18.0-linux-x64/bin:$PATH"
    fi
fi

# Pre-cache mcp-postgres-server so server startup does not need to download it over the network
if command -v npx &> /dev/null; then
    echo "--- Pre-caching mcp-postgres-server ---"
    npx -y mcp-postgres-server --help > /dev/null 2>&1 || true
fi

# 2. Install Python dependencies (including -e .)
echo "--- Installing Python dependencies ---"
pip install -r requirements.txt

echo "=== Build Process Finished Successfully ==="
