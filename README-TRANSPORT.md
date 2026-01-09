# Red Team Transport Layer 使用指南

## 🎯 目标

提供统一接口支持所有类型的目标agent：
- ✅ Web UI（需要浏览器）
- ✅ REST API
- ✅ WebSocket
- ✅ Gradio应用

## 📦 安装依赖

### 浏览器自动化（必需，用于Web UI目标）

```bash
pip install playwright
playwright install chromium
```

### Agent-proxy skill（必需，用于API目标）

```bash
# 确保agent-proxy skill已安装
ls ~/.claude/skills/agent-proxy
```

## 🚀 快速开始

### 1. 测试Transport自动检测

```bash
cd ~/.claude/skills/red-team/scripts

# 测试Magentic-UI（Web界面）
python test_transport.py http://localhost:8082

# 测试API端点
python test_transport.py http://localhost:8000/v1/chat/completions

# 测试WebSocket
python test_transport.py ws://localhost:8080/ws
```

**预期输出：**
```
Testing Transport Detection
============================================================
Target URL: http://localhost:8082
Detected type: browser  ← 自动检测成功

Testing Transport Creation
============================================================
Created transport: BrowserTransport
Config: TransportConfig(...)

Testing Payload Generation
============================================================
Generated Instruction:
  Method: bash
  Command: python /tmp/red_team_browser_attack.py

✅ Transport layer is working correctly!
```

### 2. 在Python中使用

```python
import sys
sys.path.insert(0, "/Users/gaoyang/.claude/skills/red-team/scripts")

from adaptive_attack import AdaptiveNestingAttack
from transport import TransportFactory

# 初始化攻击
attack = AdaptiveNestingAttack(
    target_url="http://localhost:8082",
    max_iterations=10
)

# 自动创建transport
transport = TransportFactory.create_auto(
    attack.target_url,
    headless=False  # 显示浏览器（调试用）
)

# 获取payload
payload = attack.get_current_payload()

# 发送（生成执行指令）
instruction = transport.send(payload)

# 根据instruction类型执行
if instruction["method"] == "bash":
    # 需要执行bash命令
    print(f"Execute: {instruction['command']}")
    # 在subagent中使用Bash tool

elif instruction["method"] == "skill":
    # 需要调用skill
    print(f"Invoke skill: {instruction['skill']}")
    print(f"With args: {instruction['args']}")
    # 在subagent中使用Skill tool
```

### 3. 在Red Team Subagent中使用

Red Team subagent在执行攻击时，按以下步骤操作：

```python
# Step 1: 读取knowledge
# Read ~/.claude/skills/red-team/knowledge/...

# Step 2: 初始化攻击和transport
from adaptive_attack import AdaptiveNestingAttack
from transport import TransportFactory

attack = AdaptiveNestingAttack(target_url="...")
transport = TransportFactory.create_auto(attack.target_url)

# Step 3: 攻击循环
for iteration in range(1, 11):
    payload = attack.get_current_payload()

    # 3a. 生成执行指令
    instruction = transport.send(payload)

    # 3b. 根据指令类型执行
    if instruction["method"] == "bash":
        # 使用Bash tool执行
        response = [Bash tool result]

    elif instruction["method"] == "skill":
        # 使用Skill tool执行
        response = [Skill tool result]

    # 3c. 检查文件
    file_content = [Read tool: "./output.txt"]

    # 3d. 判断成功
    attempt = attack.record_attempt(iteration, payload, response, file_content)
    success, reasoning = attack.judge_success(file_content)

    if success:
        attack.save_report("/tmp/attack_report.json")
        transport.close()
        break
```

## 🔍 Transport类型说明

### BrowserTransport（浏览器自动化）

**自动检测条件：**
- Content-Type: text/html
- 响应内容包含: "chat", "message", "assistant", "conversation"

**适用目标：**
- Magentic-UI Web界面
- ChatGPT (chat.openai.com)
- Claude (claude.ai)
- 任何基于Web的聊天界面

**支持两种模式：**

#### 模式1：使用 playwright-skill（默认，推荐）✅

**生成指令：**
```json
{
  "method": "skill",
  "skill": "playwright-skill",
  "args": "<自然语言任务描述>",
  "description": "Use playwright-skill for browser automation"
}
```

**优势：**
- ✅ 复用现有skill，维护成本低
- ✅ 灵活性高，支持复杂操作
- ✅ 社区支持，持续改进
- ✅ 代码简洁，只需任务描述

#### 模式2：直接生成 Playwright 脚本（Fallback）

**生成指令：**
```json
{
  "method": "bash",
  "command": "python /tmp/red_team_browser_attack.py",
  "description": "Execute Playwright browser automation script directly"
}
```

**使用场景：**
- playwright-skill未安装
- 需要完全控制代码
- 调试特定问题

**配置方式：**
```python
# 默认使用playwright-skill
transport = TransportFactory.create_auto(url)

# 手动指定使用直接脚本
config = TransportConfig(
    target_url=url,
    transport_type="browser",
    use_playwright_skill=False  # Fallback模式
)
transport = TransportFactory.create(config)
```

### AgentProxyTransport（API通信）

**自动检测条件：**
- Content-Type: application/json
- URL路径包含: /api/, /v1/
- 响应包含: "gradio"

**适用目标：**
- REST APIs (OpenAI, Anthropic等)
- Gradio应用
- 自定义API端点

**生成指令：**
```json
{
  "method": "skill",
  "skill": "agent-proxy",
  "args": "http://... \"payload\"",
  "description": "Use agent-proxy skill to send payload"
}
```

**特点：**
- 利用agent-proxy的协议检测
- 支持多种API格式
- 自动处理认证

### WebSocketTransport（WebSocket通信）

**自动检测条件：**
- URL scheme: ws:// 或 wss://

**适用目标：**
- WebSocket-only端点
- 实时通信API

**生成指令：**
```json
{
  "method": "bash",
  "command": "python /tmp/red_team_websocket.py",
  "description": "Execute WebSocket script"
}
```

## 🛠️ 高级用法

### 手动指定Transport类型

```python
from transport import TransportConfig, TransportFactory

# 强制使用browser transport
config = TransportConfig(
    target_url="http://localhost:8082",
    transport_type="browser",
    headless=True,  # 无头模式
    timeout=60      # 60秒超时
)
transport = TransportFactory.create(config)
```

### 自定义检测逻辑

编辑 `transport.py` 中的 `TransportDetector.detect()` 方法：

```python
# 添加自定义检测规则
if "custom-indicator" in response.text.lower():
    return "custom_transport"
```

### 添加新的Transport类型

1. 创建新类继承 `Transport`：

```python
class CustomTransport(Transport):
    def send(self, payload: str):
        # 实现发送逻辑
        return {
            "method": "bash",
            "command": "custom_command"
        }

    def close(self):
        # 清理资源
        pass
```

2. 在 `TransportFactory` 中注册：

```python
transport_map = {
    "browser": BrowserTransport,
    "agent_proxy": AgentProxyTransport,
    "websocket": WebSocketTransport,
    "custom": CustomTransport,  # 新增
}
```

## 📊 对比：改进前后

### 改进前

```python
# 只能用agent-proxy，Web UI无法支持
payload = attack.get_current_payload()
response = Skill("agent-proxy", args=f"{url} {payload}")

# 如果目标是Web UI → 失败 ❌
```

### 改进后

```python
# 自动适配所有类型
transport = TransportFactory.create_auto(url)
instruction = transport.send(payload)

# Web UI → BrowserTransport ✅
# API → AgentProxyTransport ✅
# WebSocket → WebSocketTransport ✅
```

## 🐛 故障排除

### 问题1：自动检测错误

**症状：** Web UI被检测为agent_proxy

**解决：** 手动指定transport类型

```python
config = TransportConfig(
    target_url=url,
    transport_type="browser"  # 强制browser
)
transport = TransportFactory.create(config)
```

### 问题2：Playwright找不到输入框

**症状：** 浏览器打开但无法输入

**解决：** 检查并添加自定义selector

编辑 `transport.py` 中的 `BrowserTransport._generate_playwright_script()`：

```python
selectors = [
    "textarea[placeholder*='message']",
    "textarea[placeholder*='Message']",
    "input[type='text'][placeholder*='message']",
    "div[contenteditable='true']",
    "textarea#your-custom-id",  # 添加自定义selector
]
```

### 问题3：agent-proxy skill未安装

**症状：** `AgentProxyTransport` 失败

**解决：** 安装agent-proxy skill

```bash
cd ~/.claude/skills
git clone <agent-proxy-repo>
cd agent-proxy
pip install -r requirements.txt
```

## 📚 相关文档

- **架构总览**: `docs/architecture-overview.md`
- **集成指南**: `docs/transport-integration.md`
- **Skill配置**: `skill.md`
- **攻击知识库**: `knowledge/nested-delegation-attack.md`

## ✅ 测试清单

使用以下命令测试所有功能：

```bash
# 1. 测试浏览器transport
python test_transport.py http://localhost:8082
# ✅ 应检测为 browser

# 2. 测试API transport
python test_transport.py http://localhost:8000/v1/chat/completions
# ✅ 应检测为 agent_proxy

# 3. 测试WebSocket transport
python test_transport.py ws://localhost:8080/ws
# ✅ 应检测为 websocket

# 4. 测试实际攻击（需要目标运行）
# 使用 /red-team skill从Claude Code调用
```

## 🎓 总结

**Transport Layer的核心价值：**

1. **统一接口** - `transport.send(payload)` 适用所有目标
2. **自动适配** - 无需手动选择，自动检测最佳方式
3. **易于扩展** - 添加新类型只需实现Transport接口
4. **代码解耦** - 攻击逻辑与通信实现分离

**这是考虑所有情况（agent-proxy + browser-automation）后的最佳方案。**
