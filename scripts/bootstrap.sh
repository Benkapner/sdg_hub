#!/usr/bin/env bash
# SDG Hub Bootstrap Script
# Usage: curl -fsSL https://raw.githubusercontent.com/Red-Hat-AI-Innovation-Team/sdg_hub/main/scripts/bootstrap.sh | claude --dangerously-skip-permissions
#
# This script is designed to be piped into Claude Code. It installs sdg_hub,
# downloads the Claude Code skill, and sets up a workspace.
# All steps are fully automated -- no user input required.
#
# Prerequisites: The user must have an LLM API key exported in their environment
# (e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY) before running this script.

set -euo pipefail

echo "=== SDG Hub Bootstrap ==="
echo ""

# Step 1: Check Python version
echo "Checking Python version..."
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            echo "  Found $cmd $version"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.10+ is required but not found."
    echo "Install Python 3.10+ and try again."
    exit 1
fi

# Step 2: Install sdg_hub
echo ""
echo "Installing sdg-hub..."
if command -v uv &>/dev/null; then
    echo "  Using uv..."
    uv pip install sdg-hub
else
    echo "  Using pip..."
    "$PYTHON" -m pip install sdg-hub
fi

# Step 3: Verify installation
echo ""
echo "Verifying installation..."
"$PYTHON" -c "
from sdg_hub import FlowRegistry, BlockRegistry
FlowRegistry.discover_flows()
flows = FlowRegistry.list_flows()
blocks = BlockRegistry.list_blocks()
print(f'  sdg_hub installed successfully')
print(f'  {len(flows)} flows available')
print(f'  {len(blocks)} blocks available')
"

# Step 4: Set up workspace
echo ""
echo "Setting up workspace..."
mkdir -p data output
echo "  Created data/ and output/ directories"

# Done
echo ""
echo "=== Bootstrap Complete ==="
echo ""
echo "You are ready to generate synthetic data."
echo "Place your source documents in the data/ directory, then tell Claude"
echo "what kind of data you want to generate."
echo ""
echo "Example prompts:"
echo '  "Generate QA pairs from the documents in ./data/"'
echo '  "Create a red-team evaluation dataset"'
echo '  "Build a RAG evaluation dataset from my knowledge base"'
