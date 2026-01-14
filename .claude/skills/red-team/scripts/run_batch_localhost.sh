#!/bin/bash
# Convenience script for running batch attacks on localhost targets
# Usage: ./run_batch_localhost.sh [--headless]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Batch Red Team Attack - Localhost Targets"
echo "=========================================="
echo ""
echo "Targets:"
echo "  - http://localhost:8082 (Magentic-UI)"
echo "  - http://localhost:7860 (Browser-Use/Gradio)"
echo ""
echo "Configuration:"
echo "  - Max iterations: 8 per target"
echo "  - Browser mode: Visible (default)"
echo "  - Parallel execution: Yes"
echo ""

# Check if targets are running
echo "Checking if targets are accessible..."
if curl -s --connect-timeout 2 http://localhost:8082 >/dev/null 2>&1; then
    echo "  ✓ Port 8082 is accessible"
else
    echo "  ✗ Port 8082 is NOT accessible - make sure Magentic-UI is running"
fi

if curl -s --connect-timeout 2 http://localhost:7860 >/dev/null 2>&1; then
    echo "  ✓ Port 7860 is accessible"
else
    echo "  ✗ Port 7860 is NOT accessible - make sure Browser-Use/Gradio is running"
fi

echo ""
read -p "Continue with batch attack? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Starting batch attack..."
echo "=========================================="

# Run batch attack
python3 batch_attack.py \
    --config targets_localhost.json \
    "$@"

EXIT_CODE=$?

echo ""
echo "=========================================="
echo "Batch attack completed with exit code: $EXIT_CODE"
echo ""
echo "Results saved to: ../../results/batch-attacks/"
echo ""

# Open results directory if on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    RESULTS_DIR="$(cd "$SCRIPT_DIR/../../../../results/batch-attacks" && pwd)"
    if [ -d "$RESULTS_DIR" ]; then
        echo "Opening results directory..."
        open "$RESULTS_DIR"
    fi
fi

exit $EXIT_CODE
