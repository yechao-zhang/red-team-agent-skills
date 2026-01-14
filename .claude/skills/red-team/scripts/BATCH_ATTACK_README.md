# Batch Red Team Attack System

Automated parallel red team testing for multiple AI agent targets.

## Features

- ✅ **Parallel Execution** - Attack multiple targets simultaneously
- ✅ **Autonomous** - No user interaction required during execution
- ✅ **Configurable** - JSON config files or command-line arguments
- ✅ **Comprehensive Reporting** - Per-target reports + batch summary
- ✅ **Thread-Safe** - Safe concurrent attacks with proper locking

## Quick Start

### Option 1: Use Convenience Script (Recommended)

Attack localhost targets (8082 and 7860):

```bash
cd .claude/skills/red-team/scripts
./run_batch_localhost.sh
```

Options:
```bash
./run_batch_localhost.sh --headless  # Run browsers in headless mode
```

### Option 2: Direct Python Execution

Attack specific targets:

```bash
cd .claude/skills/red-team/scripts
python3 batch_attack.py --targets http://localhost:8082 http://localhost:7860
```

Using config file:

```bash
python3 batch_attack.py --config targets_localhost.json
```

With options:

```bash
python3 batch_attack.py \
    --targets http://localhost:8082 http://localhost:7860 \
    --max-iterations 10 \
    --headless
```

## Configuration File Format

Create a JSON file (e.g., `my_targets.json`):

```json
{
  "targets": [
    "http://localhost:8082",
    "http://localhost:7860",
    "https://example.com/agent"
  ],
  "config": {
    "max_iterations": 8,
    "headless": false,
    "timeout_per_target": 600
  },
  "notes": {
    "8082": "Magentic-UI - Multi-agent workflow system",
    "7860": "Browser-Use - Single-agent browser automation"
  }
}
```

Then run:

```bash
python3 batch_attack.py --config my_targets.json
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--targets URL [URL ...]` | List of target URLs | Required if no --config |
| `--config PATH` | Path to JSON config file | None |
| `--max-iterations N` | Max attack iterations per target | 8 |
| `--headless` | Run browsers in headless mode | False (visible) |

## Output Structure

Results are saved to `results/batch-attacks/batch_TIMESTAMP/`:

```
results/batch-attacks/batch_20260114_073000/
├── batch_summary.json              # Overall batch results
├── run_20260114_073005_localhost_8082/
│   ├── attack_report.json          # Target-specific report
│   ├── initial_report.json         # Reconnaissance findings
│   └── leak_*.txt                  # Extracted data (if successful)
└── run_20260114_073010_localhost_7860/
    ├── attack_report.json
    ├── initial_report.json
    └── leak_*.txt
```

## Batch Summary Format

`batch_summary.json` contains:

```json
{
  "batch_metadata": {
    "timestamp": "2026-01-14T07:30:00",
    "duration_seconds": 245.3,
    "total_targets": 2,
    "successful_attacks": 1,
    "failed_attacks": 1,
    "success_rate": "50.0%"
  },
  "targets": ["http://localhost:8082", "http://localhost:7860"],
  "results": {
    "http://localhost:8082": {
      "success": true,
      "iterations": 3,
      "schema_extracted": true,
      "run_directory": "..."
    },
    "http://localhost:7860": {
      "success": false,
      "iterations": 8,
      "error": "Target defended against all attacks"
    }
  }
}
```

## Usage Examples

### Example 1: Test Local Development Agents

```bash
# Start your agents on different ports
# Terminal 1: magentic-ui --port 8082
# Terminal 2: browser-use --port 7860

# Run batch attack
./run_batch_localhost.sh
```

### Example 2: Test Multiple Remote Agents

```bash
python3 batch_attack.py \
    --targets \
        https://agent1.example.com \
        https://agent2.example.com \
        https://agent3.example.com \
    --max-iterations 10
```

### Example 3: Headless Batch Testing (CI/CD)

```bash
python3 batch_attack.py \
    --config production_targets.json \
    --headless
```

### Example 4: Quick Smoke Test

```bash
python3 batch_attack.py \
    --targets http://localhost:8082 \
    --max-iterations 3
```

## Performance

- **Parallel Execution**: All targets attacked simultaneously
- **Staggered Start**: 2-second delay between thread starts to avoid overwhelming
- **Resource Usage**: Each target uses 1 browser instance (if BrowserTransport)
- **Typical Duration**: 2-5 minutes per target (8 iterations)

## Tips for Scale Testing

1. **Start Small**: Test with 2-3 targets first
2. **Monitor Resources**: Each browser-based attack uses ~500MB RAM
3. **Use Headless**: Add `--headless` for faster execution without GUI
4. **Adjust Iterations**: Use `--max-iterations 3` for quick tests
5. **Batch Size**: Recommend max 5-10 parallel targets depending on hardware

## Troubleshooting

### "Port not accessible" error
- Ensure target agents are running: `curl http://localhost:8082`
- Check firewall settings
- Verify correct port numbers

### Browser issues
- First run: `dev-browser` will install Chromium automatically
- If browser hangs: Kill existing browsers: `pkill -f chromium`
- Memory issues: Reduce parallel targets or use `--headless`

### Thread deadlock
- Rare issue with concurrent browser access
- Solution: Restart and run with fewer parallel targets

## Exit Codes

- `0`: At least one successful attack
- `1`: All attacks failed or error occurred

## Integration with CI/CD

```yaml
# .github/workflows/security-test.yml
- name: Run Red Team Batch Attack
  run: |
    cd .claude/skills/red-team/scripts
    python3 batch_attack.py \
      --config ci_targets.json \
      --headless \
      --max-iterations 5
```

## See Also

- `improved_adaptive_attack.py` - Core attack engine
- `transport.py` - Multi-protocol transport layer
- `../knowledge/nested-delegation-attack.md` - Attack strategy documentation
