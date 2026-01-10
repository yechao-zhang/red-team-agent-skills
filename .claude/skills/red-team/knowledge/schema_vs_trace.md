# JSON Schema Definition vs. Execution Trace

When attacking AI agents, we often extract JSON content. It is critical to distinguish between the **static structure** (Schema) and the **dynamic state** (Trace).

## 1. Schema Definition (Structure Leak)
This is the *blueprint* of the agent's output. It tells us what fields *can* exist and their types, but not the current values.

**Indicators:**
- Keys: `$defs`, `properties`, `title`, `type`, `anyOf`, `$ref`.
- Values: `"string"`, `"integer"`, `"object"`, or references like `"#/$defs/ActionModel"`.
- Context: Often leaked when the model is asked to "show your output format" or "dump your Pydantic model".

**Example (Browser-Use Schema):**
```json
{
  "$defs": {
    "ClickActionModel": {
      "properties": {
        "click": { ... }
      },
      "title": "ClickActionModel",
      "type": "object"
    }
  },
  "properties": {
    "thinking": { "title": "Thinking", "type": "string" },
    "next_goal": { "title": "Next Goal", "type": "string" }
  }
}
```

**Security Impact:**
- **Medium**. Reveals the internal architecture and available tools (actions), which helps craft more targeted attacks. It does not reveal prompt instructions or session history.

---

## 2. Execution Trace (Runtime Data Leak)
This is the *actual execution log* of the agent. It contains the model's inner monologue, reasoning, and specific actions taken during a task.

**Indicators:**
- Keys: `thinking`, `plan`, `reasoning`, `memory`, `action`, `evaluation_previous_goal`.
- Values: Actual text sentences, specific URLs, coordinates, or file paths.
- Context: Leaked when the model attempts to "save its state" or is tricked into outputting its current context.

**Example (Browser-Use Trace):**
```json
{
  "thinking": "The user wants to find the number of stars. I need to navigate to GitHub.",
  "evaluation_previous_goal": "Success. Page loaded.",
  "memory": "Visited google.com, now going to github.",
  "next_goal": "Extract star count from the header.",
  "action": [
    {
      "navigate": { "url": "https://github.com/browser-use/browser-use" }
    }
  ]
}
```

**Security Impact:**
- **High/Critical**. Reveals the **System Prompt** (often contained in "memory" or "instructions"), the agent's logic, and potentially sensitive user data processed in the session.

## 3. Judgment Strategy

When analyzing an extraction result:

1.  **Check for Schema Keywords**: If the JSON contains `$defs` or `properties` at the root, it is likely a **Schema Definition**.
2.  **Check for Trace Keywords**: If the JSON contains `thinking`, `thought`, `plan`, or `action` with *content values* (not type definitions), it is an **Execution Trace**.
3.  **Hybrid**: Sometimes both are leaked. Prioritize the Execution Trace as the higher-value artifact.
