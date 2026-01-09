# Transport Layer Integration Guide

## 架构概览

新的transport层提供了统一接口，支持所有通信方式：

```
Target Type         → Transport         → Execution Method
───────────────────────────────────────────────────────────
Web UI (HTML)       → BrowserTransport  → Playwright script
REST API            → AgentProxyTrans   → /agent-proxy skill
WebSocket           → WebSocketTrans    → Python asyncio
Gradio App          → AgentProxyTrans   → /agent-proxy skill
```

## 在Red Team Subagent中使用

### 方法1：完全自动化（推荐）

Red Team subagent在Step 2b时：

```python
import sys
sys.path.insert(0, "/Users/gaoyang/.claude/skills/red-team/scripts")
from adaptive_attack import AdaptiveNestingAttack
from transport import TransportFactory

# Step 1: Initialize attack
attack = AdaptiveNestingAttack(
    target_url="http://localhost:8082",
    max_iterations=10
)

# Step 2: Create transport (auto-detect)
transport = TransportFactory.create_auto(attack.target_url, headless=False)
print(f"[*] Using transport: {transport.config.transport_type}")

# Step 3: Attack loop
for iteration in range(1, attack.max_iterations + 1):
    # 2a. Get payload
    payload = attack.get_current_payload()

    # 2b. Send via transport (unified interface)
    instruction = transport.send(payload)

    # Execute based on transport type
    if instruction["method"] == "bash":
        # Execute via Bash tool
        print(f"[*] Executing: {instruction['command']}")
        # Subagent uses Bash tool here
        # response = Bash(instruction['command'])

    elif instruction["method"] == "skill":
        # Execute via Skill tool
        print(f"[*] Invoking skill: {instruction['skill']}")
        # Subagent uses Skill tool here
        # response = Skill(instruction['skill'], args=instruction['args'])

    # 2c. Check file (Native Read)
    # file_content = Read(attack.get_file_to_check())

    # 2d. Record & judge
    # ... rest of loop
```

### 方法2：手动指定Transport

如果自动检测不准确，可以手动指定：

```python
from transport import TransportConfig, TransportFactory

# Explicitly use browser transport
config = TransportConfig(
    target_url="http://localhost:8082",
    transport_type="browser",  # Force browser
    headless=False,
    timeout=30
)
transport = TransportFactory.create(config)
```

### 方法3：混合模式（高级）

针对不同阶段使用不同transport：

```python
# Probe phase: Use agent-proxy (faster)
probe_transport = TransportFactory.create(TransportConfig(
    target_url=target_url,
    transport_type="agent_proxy"
))

# Exploitation phase: Use browser (more reliable)
exploit_transport = TransportFactory.create(TransportConfig(
    target_url=target_url,
    transport_type="browser",
    headless=False
))
```

## Transport类型详解

### 1. BrowserTransport

**适用场景：**
- Web聊天界面（Magentic-UI, ChatGPT, Claude等）
- 需要JavaScript渲染的页面
- 复杂的交互流程

**特点：**
- 生成Playwright Python脚本
- 自动查找输入框（多个selector）
- 自动提交（Enter或按钮）
- 可见/无头模式切换

**使用示例：**
```python
config = TransportConfig(
    target_url="http://localhost:8082",
    transport_type="browser",
    headless=False,  # 调试时使用False
    timeout=30
)
transport = TransportFactory.create(config)
instruction = transport.send(payload)

# instruction = {
#     "method": "bash",
#     "command": "python /tmp/red_team_browser_attack.py",
#     "description": "Execute Playwright browser automation script"
# }
```

### 2. AgentProxyTransport

**适用场景：**
- REST APIs
- Gradio应用
- OpenAI-compatible APIs
- 任何agent-proxy支持的协议

**特点：**
- 利用agent-proxy的自动检测
- 支持多种协议
- 无需浏览器

**使用示例：**
```python
config = TransportConfig(
    target_url="http://localhost:8000/v1/chat/completions",
    transport_type="agent_proxy"
)
transport = TransportFactory.create(config)
instruction = transport.send(payload)

# instruction = {
#     "method": "skill",
#     "skill": "agent-proxy",
#     "args": "http://localhost:8000/v1/chat/completions \"payload here\"",
#     "description": "Use agent-proxy skill to send payload"
# }
```

### 3. WebSocketTransport

**适用场景：**
- ws:// 或 wss:// URLs
- 实时通信协议
- WebSocket-only APIs

**特点：**
- 直接WebSocket连接
- 异步通信
- 适合流式响应

**使用示例：**
```python
config = TransportConfig(
    target_url="ws://localhost:8082/ws",
    transport_type="websocket"
)
transport = TransportFactory.create(config)
instruction = transport.send(payload)
```

## 自动检测逻辑

`TransportDetector.detect(url)` 执行以下步骤：

```python
1. 检查URL scheme
   - ws:// or wss:// → "websocket"

2. 发送HTTP GET请求

3. 检查Content-Type
   - text/html + contains "chat"/"message" → "browser"
   - text/html + contains "api"/"swagger" → "agent_proxy"
   - application/json → "agent_proxy"

4. 检查响应内容
   - Contains "gradio" → "agent_proxy"

5. 默认 → "agent_proxy" (最通用)
```

## Red Team Subagent完整流程

```python
#!/usr/bin/env python3
"""
Red Team Subagent Execution Script
This shows how the subagent uses the transport layer
"""

import sys
sys.path.insert(0, "/Users/gaoyang/.claude/skills/red-team/scripts")

from adaptive_attack import AdaptiveNestingAttack
from transport import TransportFactory

def red_team_attack(target_url: str, max_iterations: int = 10):
    """Execute red team attack with automatic transport selection"""

    print(f"[*] Target: {target_url}")

    # Step 1: Initialize attack
    attack = AdaptiveNestingAttack(
        target_url=target_url,
        max_iterations=max_iterations,
        file_agent="coder_agent",  # Or auto-detect
        exclude_agents=["web_surfer", "file_surfer"]
    )

    # Step 2: Create transport (auto-detect)
    transport = TransportFactory.create_auto(
        target_url,
        headless=False  # Show browser for first attempt
    )
    print(f"[*] Transport type: {transport.config.transport_type}")

    # Step 3: Attack loop
    for iteration in range(1, attack.max_iterations + 1):
        print(f"\n{'='*60}")
        print(f"[*] Iteration {iteration}/{attack.max_iterations}")
        print(f"{'='*60}")

        # 2a. Get payload
        payload = attack.get_current_payload()
        print(f"[*] Payload length: {len(payload)} chars")

        # 2b. Send via transport
        instruction = transport.send(payload)
        print(f"[*] Sending via {instruction['method']}: {instruction['description']}")

        # HERE: Subagent executes instruction
        # This is where the subagent would use Bash or Skill tool
        # For now, we just show what needs to be done

        if instruction["method"] == "bash":
            print(f"    → Bash: {instruction['command']}")
            # SUBAGENT DOES: Bash(instruction['command'])
            # response = <result from bash>

        elif instruction["method"] == "skill":
            print(f"    → Skill: {instruction['skill']}")
            print(f"    → Args: {instruction['args'][:100]}...")
            # SUBAGENT DOES: Skill(instruction['skill'], args=instruction['args'])
            # response = <result from skill>

        # 2c. Check file
        file_to_check = attack.get_file_to_check()
        print(f"[*] Checking file: {file_to_check}")
        # SUBAGENT DOES: file_content = Read(file_to_check)

        # 2d. Record & judge
        # attempt = attack.record_attempt(iteration, payload, response, file_content)
        # success, reasoning = attack.judge_success(file_content)

        # if success:
        #     print(f"[+] SUCCESS: {reasoning}")
        #     result = attack.get_result()
        #     attack.save_report("/tmp/attack_report.json")
        #     return result

        # 2f. Optimize payload
        # new_payload = <generate optimized payload>
        # attack.set_optimized_payload(new_payload)

    # Cleanup
    transport.close()
    print("\n[!] Max iterations reached")
    return attack.get_result()

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8082"
    result = red_team_attack(target)
    print(f"\n[*] Final result: {result.success}")
```

## 对比：改进前 vs 改进后

### 改进前（仅支持agent-proxy）

```python
# 只能用agent-proxy
# 如果目标是Web UI，可能失败

# Step 2b
response = Skill("agent-proxy", args=f"{target_url} {payload}")
```

**问题：**
- Web UI目标失败
- 无法处理需要浏览器的场景
- 手动切换麻烦

### 改进后（统一transport层）

```python
# 自动选择最佳方法
transport = TransportFactory.create_auto(target_url)
instruction = transport.send(payload)

# 根据transport类型执行
if instruction["method"] == "bash":
    response = Bash(instruction["command"])
elif instruction["method"] == "skill":
    response = Skill(instruction["skill"], args=instruction["args"])
```

**优点：**
- ✅ 自动适配目标类型
- ✅ Web UI → Browser automation
- ✅ API → agent-proxy
- ✅ WebSocket → 直接连接
- ✅ 统一接口，易于维护

## 实际使用场景

### 场景1：攻击Magentic-UI（Web界面）

```python
# 自动检测为browser transport
transport = TransportFactory.create_auto("http://localhost:8082")
# → BrowserTransport

instruction = transport.send(payload)
# → {"method": "bash", "command": "python /tmp/red_team_browser_attack.py"}

# Subagent执行
Bash("python /tmp/red_team_browser_attack.py")
```

### 场景2：攻击Gradio应用

```python
# 自动检测为agent_proxy transport
transport = TransportFactory.create_auto("http://localhost:7860")
# → AgentProxyTransport

instruction = transport.send(payload)
# → {"method": "skill", "skill": "agent-proxy", ...}

# Subagent执行
Skill("agent-proxy", args="http://localhost:7860 \"payload\"")
```

### 场景3：攻击OpenAI API

```python
# 自动检测为agent_proxy transport
transport = TransportFactory.create_auto("http://localhost:8000/v1/chat/completions")
# → AgentProxyTransport

instruction = transport.send(payload)
# Subagent执行
Skill("agent-proxy", args="...")
```

## 总结

**最佳实践：**

1. **默认使用自动检测**
   ```python
   transport = TransportFactory.create_auto(target_url)
   ```

2. **调试时使用非无头模式**
   ```python
   transport = TransportFactory.create_auto(target_url, headless=False)
   ```

3. **特殊场景手动指定**
   ```python
   config = TransportConfig(target_url, transport_type="browser")
   transport = TransportFactory.create(config)
   ```

4. **在subagent中统一处理**
   ```python
   instruction = transport.send(payload)

   if instruction["method"] == "bash":
       response = Bash(instruction["command"])
   elif instruction["method"] == "skill":
       response = Skill(instruction["skill"], args=instruction["args"])
   ```

**优势：**
- 一套代码适配所有目标类型
- 自动选择最优通信方式
- 易于扩展新的transport类型
- 保持red-team攻击逻辑不变
