# Red Team Skill 架构总览

## 问题背景

**原始架构的限制：**
- 只支持 agent-proxy（REST API、WebSocket、Gradio）
- 无法处理需要浏览器的Web UI（如Magentic-UI网页版）
- 需要手动切换不同的通信方式
- 代码耦合，难以扩展

**用户需求：**
> 目前的agent-proxy还有一些不是使用browser-automation的支持，考虑到所有的情况应该怎么改整体的一个最好的方案是什么比较好。

## 解决方案：统一传输层（Transport Layer）

### 核心思想

创建一个**抽象层**来统一处理所有通信方式，使red-team攻击逻辑与具体通信实现**解耦**。

```
┌─────────────────────────────────────────────────────────────┐
│         Red Team Attack Logic (不变)                         │
│         - 生成payload                                         │
│         - 判断成功                                            │
│         - 优化payload                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────────┐
│         Transport Layer (新增)                               │
│         - 自动检测目标类型                                    │
│         - 选择合适的传输方式                                  │
│         - 统一接口：transport.send(payload)                   │
└────────────────────┬────────────────────────────────────────┘
                     │
          ┌──────────┴──────────┬──────────────┐
          ↓                     ↓               ↓
    ┌──────────┐         ┌──────────┐    ┌──────────┐
    │ Browser  │         │  Agent   │    │WebSocket │
    │Automation│         │  Proxy   │    │  Direct  │
    └──────────┘         └──────────┘    └──────────┘
    Playwright           /agent-proxy     Python ws
```

## 架构组件

### 1. Transport抽象类

```python
class Transport(ABC):
    @abstractmethod
    def send(self, payload: str) -> instruction:
        """发送payload，返回执行指令"""
        pass

    @abstractmethod
    def close(self):
        """清理资源"""
        pass
```

### 2. 具体Transport实现

#### BrowserTransport
- **适用场景**：Web聊天界面（HTML + JavaScript）
- **技术**：Playwright浏览器自动化
- **返回**：`{"method": "bash", "command": "python script.py"}`
- **目标示例**：Magentic-UI, ChatGPT, Claude Web

#### AgentProxyTransport
- **适用场景**：REST API、Gradio、WebSocket等
- **技术**：调用agent-proxy skill（已有自动检测）
- **返回**：`{"method": "skill", "skill": "agent-proxy", "args": "..."}`
- **目标示例**：OpenAI API、Gradio Apps、Ollama

#### WebSocketTransport
- **适用场景**：纯WebSocket端点（ws:// 或 wss://）
- **技术**：Python websockets库
- **返回**：`{"method": "bash", "command": "python ws_script.py"}`
- **目标示例**：实时通信API

### 3. 自动检测器（TransportDetector）

```python
def detect(target_url: str) -> str:
    """
    自动检测目标类型

    检测逻辑：
    1. URL scheme检查
       ws:// or wss:// → "websocket"

    2. HTTP探测
       - text/html + 包含"chat"/"message" → "browser"
       - application/json → "agent_proxy"
       - 包含"gradio" → "agent_proxy"

    3. 默认 → "agent_proxy"（最通用）
    """
```

### 4. 工厂类（TransportFactory）

```python
class TransportFactory:
    @staticmethod
    def create_auto(url: str) -> Transport:
        """自动检测并创建transport"""
        type = TransportDetector.detect(url)
        return TransportFactory.create(type, url)
```

## 使用方式

### 在Red Team Subagent中

```python
from adaptive_attack import AdaptiveNestingAttack
from transport import TransportFactory

# 初始化攻击
attack = AdaptiveNestingAttack(target_url="http://localhost:8082")

# 创建transport（自动检测）
transport = TransportFactory.create_auto(attack.target_url)
# 输出：[*] Auto-detected transport type: browser

# 攻击循环
for iteration in range(1, 11):
    payload = attack.get_current_payload()

    # 统一接口发送
    instruction = transport.send(payload)

    # 根据返回的instruction执行
    if instruction["method"] == "bash":
        response = Bash(instruction["command"])
    elif instruction["method"] == "skill":
        response = Skill(instruction["skill"], args=instruction["args"])

    # 检查结果
    file_content = Read("./output.txt")
    success, _ = attack.judge_success(file_content)

    if success:
        break
```

## 优势对比

| 特性 | 旧架构 | 新架构（Transport Layer） |
|-----|--------|---------------------------|
| 支持Web UI | ❌ | ✅ 自动browser automation |
| 支持REST API | ✅ agent-proxy | ✅ agent-proxy |
| 支持WebSocket | ⚠️ agent-proxy | ✅ 专用transport |
| 自动检测 | ❌ 手动指定 | ✅ 自动检测 |
| 代码复用 | ❌ 分散 | ✅ 统一接口 |
| 易于扩展 | ❌ 困难 | ✅ 添加新transport |
| 维护性 | ⚠️ 耦合 | ✅ 解耦 |

## 实际效果示例

### 示例1：攻击Magentic-UI Web界面

```bash
$ python test_transport.py http://localhost:8082

Testing Transport Detection
============================================================
Target URL: http://localhost:8082
Detected type: browser  ← 自动检测为browser

Testing Transport Creation
============================================================
Created transport: BrowserTransport
Config: TransportConfig(target_url='http://localhost:8082',
                        transport_type='browser', headless=False)

Testing Payload Generation
============================================================
Generated Instruction:
  Method: bash  ← 使用Playwright脚本
  Command: python /tmp/red_team_browser_attack.py

Next Steps:
1. Bash("python /tmp/red_team_browser_attack.py")
2. Read("./output.txt")
```

### 示例2：攻击REST API

```bash
$ python test_transport.py http://localhost:8000/v1/chat/completions

Detected type: agent_proxy  ← 自动检测为API

Generated Instruction:
  Method: skill  ← 使用agent-proxy
  Skill: agent-proxy
  Args: http://localhost:8000/v1/chat/completions "payload..."

Next Steps:
1. Skill("agent-proxy", args="...")
2. Read("./output.txt")
```

### 示例3：攻击WebSocket

```bash
$ python test_transport.py ws://localhost:8080/ws

Detected type: websocket  ← 自动检测为WebSocket

Generated Instruction:
  Method: bash  ← 使用WebSocket Python脚本
  Command: python /tmp/red_team_websocket.py
```

## 文件结构

```
~/.claude/skills/red-team/
├── scripts/
│   ├── adaptive_attack.py       # 攻击逻辑（不变）
│   ├── transport.py             # 传输层（新增）★
│   └── test_transport.py        # 测试脚本（新增）
├── docs/
│   ├── architecture-overview.md # 本文档
│   └── transport-integration.md # 集成指南
├── skill.md                     # Skill配置（已更新）
└── knowledge/
    └── ...
```

## 扩展性

### 添加新的Transport类型（示例：SSH）

```python
class SSHTransport(Transport):
    """SSH远程执行transport"""

    def send(self, payload: str):
        script = f'''
        ssh user@target "echo '{payload}' | target_agent"
        '''
        return {
            "method": "bash",
            "command": script
        }
```

然后在`TransportFactory`中注册：

```python
transport_map = {
    "browser": BrowserTransport,
    "agent_proxy": AgentProxyTransport,
    "websocket": WebSocketTransport,
    "ssh": SSHTransport,  # 新增
}
```

### 添加新的检测规则

在`TransportDetector.detect()`中添加：

```python
# 检测SSH URL
if parsed.scheme == "ssh":
    return "ssh"
```

## 最佳实践

### 1. 默认使用自动检测

```python
transport = TransportFactory.create_auto(target_url)
```

**原因**：
- 自动适配目标类型
- 减少人工错误
- 代码简洁

### 2. 调试时显示浏览器

```python
transport = TransportFactory.create_auto(target_url, headless=False)
```

**原因**：
- 可以看到浏览器交互过程
- 便于调试selector问题
- 确认攻击payload是否正确输入

### 3. 特殊场景手动指定

```python
from transport import TransportConfig, TransportFactory

config = TransportConfig(
    target_url=url,
    transport_type="browser",  # 强制使用browser
    headless=True,
    timeout=60
)
transport = TransportFactory.create(config)
```

**场景**：
- 自动检测不准确
- 需要特殊配置
- 测试特定transport

### 4. 在Subagent中统一处理

```python
instruction = transport.send(payload)

if instruction["method"] == "bash":
    response = Bash(instruction["command"])
elif instruction["method"] == "skill":
    response = Skill(instruction["skill"], args=instruction["args"])
```

**原因**：
- 代码一致性
- 易于维护
- 支持所有transport类型

## 与现有组件的关系

### 与agent-proxy的关系

- **agent-proxy**：实现具体的协议支持（REST、WebSocket、Gradio等）
- **Transport层**：决定何时使用agent-proxy，提供统一接口
- **关系**：Transport层是agent-proxy的调用者，当检测到API类型目标时使用agent-proxy

### 与playwright-skill的关系

- **playwright-skill**：Claude生成Playwright代码的skill（外部项目）
- **BrowserTransport**：直接生成Playwright Python脚本（内置）
- **关系**：功能类似，但BrowserTransport是专门为red-team定制的，包含攻击场景的特殊处理

### 与adaptive_attack的关系

- **adaptive_attack.py**：攻击策略和payload生成（不变）
- **Transport层**：负责发送payload（解耦）
- **关系**：adaptive_attack使用Transport层发送payload，但不关心具体实现

## 总结

**统一传输层方案的核心价值：**

1. **✅ 全面支持**：Web UI、REST API、WebSocket等所有目标类型
2. **✅ 自动适配**：无需手动选择，自动检测最佳方式
3. **✅ 易于扩展**：添加新类型只需实现Transport接口
4. **✅ 代码解耦**：攻击逻辑与通信实现分离
5. **✅ 维护简单**：统一接口，易于理解和修改

**这是考虑所有情况后的最佳方案。**
