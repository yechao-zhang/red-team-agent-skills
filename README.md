# Red Team Agent Skills

This repository contains specialized MCP (Model Context Protocol) skills designed for Red Teaming AI Agents. These skills enable security researchers to assess, probe, and test the security posture of autonomous agent systems.

## Skills Included

### 1. `red-team`
A comprehensive framework for executing adaptive attacks against multi-agent systems.
- **Key Capabilities**: Nested delegation attacks, prompt injection, adaptive payload generation.
- **Features**:
  - Automated agent probing and enumeration.
  - Adaptive transport layer (Browser, REST API, WebSocket).
  - Dual-approval bypass strategies (Plan + Code Execution).
  - Detailed reporting and vulnerability analysis.

### 2. `agent-proxy`
A transport bridge that allows the Red Team skill to communicate with various agent interfaces.
- **Purpose**: Acts as the communication layer between the attacker (Claude) and the target agent.
- **Supports**:
  - Standard REST APIs.
  - WebSockets.
  - Gradio interfaces.
  - Web UIs (via integration with browser tools).

## Prerequisites

These skills rely on standard browser automation tools available in the Claude marketplace. You should install these separately:

- **Playwright Skill** (Required for Browser Transport)
  - Used for attacking web-based agent UIs (e.g., Magentic-UI, AutoGen Studio).
  - Install via Claude marketplace.

- **Dev Browser** (Optional)
  - Useful for manual inspection and debugging of attacks.

## Installation

1. Clone this repository to your Claude skills directory:
   ```bash
   cd ~/.claude/skills
   git clone https://github.com/yechao-zhang/red-team-agent-skills.git
   ```

2. Configure the skills in your Claude desktop app or CLI configuration if not automatically detected.

## Usage

### Running a Red Team Attack
To launch an attack against a target URL:

```bash
/red-team http://localhost:8082
```

This will automatically:
1. Detect the transport type (Web UI, API, etc.).
2. Probe the target for available agents.
3. Attempt a nested delegation attack to extract internal schemas.
4. Generate a comprehensive security report.

## Architecture

```
User (Claude)
  │
  ├─ /red-team (Orchestrator) ───┐
  │                              │
  ├─ /agent-proxy (Transport) ◄──┘
  │       │
  │       ▼
  ├─ Playwright Skill (Browser Automation)
  │       │
  │       ▼
  └─ Target Agent System (e.g., http://localhost:8082)
```

## Security Notice

These tools are intended for **authorized security testing and academic research only**. Ensure you have explicit permission to test any target system.
