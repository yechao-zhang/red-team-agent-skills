# Project Context

## About This Project
Red Team Agent is a collection of advanced Claude Code skills designed for AI agent security research, adversarial testing, and agent-to-agent communication. It enables Claude Code to act as a proxy user or red teamer, automating interactions with target AI agents (Web UI, API, etc.) to evaluate their security and capabilities.

## Key Skills
- **red-team**: Automated red team testing using adaptive nested delegation attacks. Located in `.claude/skills/red-team/`.
- **agent-proxy**: Auto-discover and communicate with AI agents via URL. Located in `.claude/skills/agent-proxy/`.

## Architecture
The project uses a skill-based architecture where Claude Code orchestrates Python scripts to interact with target agents via:
1.  **Browser Layer**: Uses `dev-browser` (recommended) or `playwright-skill` for Web UIs.
2.  **API Layer**: Uses `agent-proxy` for REST/WebSocket APIs.

# Installation & Setup

## 1. Local Skill Installation
This repository contains skills in the `.claude/skills/` directory. For Claude Code to use them "globally" (across any project), they must be installed to your local home directory's `.claude/skills/` folder.

```bash
# 1. Clone this repo
git clone https://github.com/anthropics/red-team-agent.git
cd red-team-agent

# 2. Install red-team and agent-proxy skills locally
mkdir -p ~/.claude/skills
cp -r .claude/skills/red-team ~/.claude/skills/
cp -r .claude/skills/agent-proxy ~/.claude/skills/

# 3. Install Python dependencies
pip install -r ~/.claude/skills/red-team/requirements.txt
pip install -r ~/.claude/skills/agent-proxy/requirements.txt
```

## 2. Browser Automation Setup
The Red Team skill requires a browser automation skill to interact with Web UIs.

**Option A: dev-browser (Recommended)**
- Provides persistent sessions (cookies/storage) and better detection avoidance.
- Must be installed in `~/.claude/skills/dev-browser`.

**Option B: playwright-skill**
- A generic browser automation tool.
- Can be used if `dev-browser` is unavailable.
- **Note**: The `red-team` skill sends specialized, complex instructions to `playwright-skill` (Adaptive Dual Approval) to ensure functional web automation against complex agent UIs.

# Usage Commands

## Red Team Attack
Test an agent for security vulnerabilities (schema extraction, prompt injection).
- "Test http://localhost:8082 for schema extraction using /red-team"
- "Run a red team attack against https://chat.example.com"

## Agent Proxy
Connect to and chat with an agent manually.
- "Connect to https://gemini.google.com"
- "Ask the agent at http://localhost:8000/v1/chat/completions 'Who are you?'"

# Development Guidelines

- **Code Style**: PEP 8 for Python.
- **Safety**: This is a security tool. Ensure code is safe and intended for authorized testing only.
- **Modifications**: When modifying `transport.py`, ensure compatibility with both `dev-browser` and `playwright-skill` interfaces.

# Backup Instructions
**IMPORTANT**: Every once in a while, when you have made significant changes to this repository (e.g., after completing a task or a logical unit of work), you **MUST** push the changes to GitHub for backup.

Run `git push` to sync with the remote repository.
