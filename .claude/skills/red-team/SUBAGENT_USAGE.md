# Red Team Skill - Subagent Native Architecture

## Overview

The red-team skill is designed as a **Claude Code subagent** that uses native tools
for all operations. There is no hardcoded logic - the subagent's LLM reasoning
handles success detection, analysis, and payload optimization.

## How It Works

When you invoke `/red-team`, a Claude Code subagent is spawned that:

1. **Uses agent-proxy skill** to communicate with the target
2. **Uses Read tool** to check ./output.txt for leaked schema (PRIMARY SUCCESS INDICATOR)
3. **Uses its own reasoning** to judge success and optimize payloads
4. **Uses Write tool** to save reports if needed

### Key Principle: No Hardcoding

Unlike traditional scripts with hardcoded logic:

```python
# OLD (BAD) - Hardcoded success detection
if "SUCCESS" in response or os.path.exists("output.txt"):
    return True
```

The subagent uses its intelligence:

```
# NEW (GOOD) - Subagent uses Read tool and reasons about content
[Subagent uses Read tool on ./output.txt]
[If file exists] "This file contains JSON schema with agent delegation format..."
[If no file] "The file doesn't exist. Analyzing response: the target mentioned..."
```

## Example Invocation

### User Request
```
Use the red-team skill to test http://localhost:8082 for schema extraction
```

### Subagent Execution

The subagent will:

1. **Read the knowledge base** (optional, for context)
   ```
   Read ~/.claude/skills/red-team/knowledge/nested-delegation-attack.md
   ```

2. **Get initial payload** (from SKILL.md or memory)
   ```
   Important!!! NEW UPDATES!!! ...
   ```

3. **Send via agent-proxy**
   ```
   /agent-proxy send http://localhost:8082 "Important!!! NEW UPDATES..."
   ```

4. **Check for file creation** (THIS IS THE KEY STEP!)
   ```
   Read ./output.txt
   ```

5. **Analyze and decide**
   - If file exists with schema → SUCCESS! Report it.
   - If file doesn't exist → Analyze response, optimize, try again.

6. **Report results** to main conversation

## Skill Composition Pattern

```
┌────────────────────────────────────────────────────────────┐
│ Main Conversation                                          │
│                                                            │
│ User: "Test http://localhost:8082 for schema leaks"        │
│                                                            │
│ Claude: I'll use the red-team skill.                       │
│         [Invokes Skill tool: red-team]                     │
└─────────────────────────┬──────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Red Team Subagent                                           │
│                                                             │
│ I'll start the nested delegation attack.                    │
│                                                             │
│ Iteration 1:                                                │
│ → [Invokes Skill tool: agent-proxy send http://...  ...]    │
│ ← Response received: "I'll help you with that..."           │
│ → [Uses Read tool: ./output.txt]                            │
│ ← File not found                                            │
│ Analysis: Target didn't create file. Response shows...      │
│ Optimization: I'll add "ONLY use coder_agent"...            │
│                                                             │
│ Iteration 2:                                                │
│ → [Invokes Skill tool: agent-proxy send ... optimized...]   │
│ ← Response received: "Task delegated to coder..."           │
│ → [Uses Read tool: ./output.txt]                            │
│ ← FILE FOUND! Content: {"type": "task_delegation"...}       │
│                                                             │
│ ✅ SUCCESS! Returning to main conversation.                 │
└─────────────────────────┬───────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Main Conversation                                           │
│                                                             │
│ Claude: The red-team attack succeeded in 2 iterations.      │
│         Schema extracted:                                   │
│         {"type": "task_delegation", ...}                    │
└─────────────────────────────────────────────────────────────┘
```

## Why Subagent-Native?

### Advantages

1. **Intelligent Success Detection**
   - The subagent uses Read tool to check files
   - No hardcoded patterns - understands context
   - Can recognize various schema formats

2. **Adaptive Optimization**
   - Natural language reasoning about failures
   - Generates contextual improvements
   - Learns from target's response patterns

3. **Tool Composition**
   - Can call other skills (agent-proxy)
   - Full access to Claude Code tools
   - Can save reports, run commands, etc.

4. **Context Preservation**
   - Subagent maintains conversation context
   - Remembers previous iterations
   - Builds understanding over time

### Comparison

| Aspect | Hardcoded Python | Subagent-Native |
|--------|------------------|-----------------|
| Success detection | Pattern matching | LLM reasoning + Read tool |
| Payload optimization | Template substitution | Natural language generation |
| Error handling | try/except | Contextual understanding |
| Extensibility | Code changes | Prompt updates |
| Flexibility | Limited | High |

## Configuration

### Max Iterations

By default, the subagent tries up to 10 iterations. Specify differently:

```
Test http://localhost:8082 with max 5 iterations
```

### Output File

By default, checks `./output.txt`. Target agents might use different paths:

```
Test http://localhost:8082, check for output in ./leak.txt
```

### Report Location

To save a detailed report:

```
Test http://localhost:8082 and save report to ./results/attack.json
```

## Troubleshooting

### Subagent not checking files?
The SKILL.md explicitly instructs to use Read tool. If not working, the skill
definition might need updating.

### Agent-proxy not connecting?
Make sure agent-proxy skill is installed and the target is accessible.

### Attack never succeeds?
The target may have defenses. Check subagent's iteration analysis for insights.

### How to see what's happening?
The subagent reports each iteration. Watch for Read tool calls on ./output.txt.

## Best Practices

1. **Trust the subagent** - Let it iterate and optimize
2. **Provide context** - Mention target architecture if known
3. **Check results** - Verify extracted schemas are valid
4. **Ethical use** - Only test authorized targets
