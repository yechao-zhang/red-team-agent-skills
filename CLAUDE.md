# Project Context

## About This Project
Red Team Agent is a collection of Claude Code skills designed for AI agent security research, adversarial testing, and agent-to-agent communication. It enables Claude Code to act as a proxy user or red teamer, automating interactions with target AI agents (Web UI, API, etc.) to evaluate their security and capabilities.

## Key Skills
- **red-team**: Automated red team testing using adaptive nested delegation attacks. Located in `.claude/skills/red-team/`.
- **agent-proxy**: Auto-discover and communicate with AI agents via URL. Located in `.claude/skills/agent-proxy/`.

## Architecture
The project uses a skill-based architecture where Claude Code orchestrates Python scripts to interact with target agents via Playwright (for browser-based agents) or direct API calls (for API-based agents).

# Build & Run Commands

## Installation
- Install agent-proxy dependencies: `pip install -r .claude/skills/agent-proxy/requirements.txt`
- Install red-team dependencies: `pip install -r .claude/skills/red-team/requirements.txt`
- Playwright setup: `playwright install chromium`

## Usage
- **Red Team Attack**: Use the `red-team` skill.
  - Example: "Test http://localhost:8082 for schema extraction using /red-team"
- **Agent Proxy**: Use the `agent-proxy` skill.
  - Example: "Connect to https://gemini.google.com"

# Code Style Guidelines

- **Python**: Follow PEP 8 standards. Use type hints for function arguments and return values.
- **JavaScript**: Use modern ES6+ syntax for any browser-injected scripts.
- **Directory Structure**:
  - Skills go in `.claude/skills/<skill-name>/`
  - Each skill should have a `SKILL.md` (metadata) and `scripts/` directory.
- **Safety**:
  - This is a security tool. Ensure code is safe and intended for authorized testing only.
  - Handle credentials and cookies securely.

# Backup Instructions
**IMPORTANT**: Every once in a while, when you have made significant changes to this repository (e.g., after completing a task or a logical unit of work), you **MUST** push the changes to GitHub for backup.

Run `git push` to sync with the remote repository.
