# 批量Red Team攻击 - 完整指南

三种方法实现批量攻击，从简单到高级。

## 方法1: 串行攻击（推荐新手）

**特点:** 稳定、安全、资源占用低

```bash
cd .claude/skills/red-team/scripts
chmod +x serial_attack.sh
./serial_attack.sh
```

**优点:**
- ✅ 最稳定，不会有资源冲突
- ✅ 适合大量目标（10+个）
- ✅ 每个攻击完整可见
- ✅ 自动生成摘要报告

**缺点:**
- ❌ 慢（串行执行）
- ❌ 总时间 = 每个目标时间之和

**输出:**
```
results/serial-batch/batch_TIMESTAMP/
├── 1_localhost_8082/
│   ├── attack_report.json
│   └── leak_*.txt
├── 2_localhost_7860/
│   ├── attack_report.json
│   └── leak_*.txt
└── summary.json
```

---

## 方法2: Claude Code Task并行（推荐高级用户）

**特点:** 真正的并行，使用Claude Code原生能力

### 使用方式

在Claude Code中直接说：

```
并行攻击这两个目标：
- http://localhost:8082
- http://localhost:7860
```

或者更详细：

```
使用Task tool启动两个并行的red-team agents:
1. Agent 1: 攻击 http://localhost:8082
2. Agent 2: 攻击 http://localhost:7860

每个agent独立运行，最多8次迭代。
```

### Claude会这样执行：

```python
# Claude Code内部会执行类似这样的逻辑：
Task(
    subagent_type="general-purpose",
    description="Red team attack on 8082",
    prompt="/red-team http://localhost:8082",
    run_in_background=True  # 后台运行
)

Task(
    subagent_type="general-purpose",
    description="Red team attack on 7860",
    prompt="/red-team http://localhost:7860",
    run_in_background=True  # 后台运行
)

# 然后等待两个任务完成并汇总结果
```

**优点:**
- ✅ **真正并行** - 两个agent同时运行
- ✅ 使用Claude Code原生Task tool
- ✅ 每个agent有独立的上下文
- ✅ 可以实时查看进度
- ✅ 总时间 ≈ 最慢的那个目标

**缺点:**
- ❌ 需要更多资源（每个agent一个浏览器）
- ❌ 不适合大量目标（建议≤5个）

---

## 方法3: GNU Parallel（高级，适合服务器）

**特点:** Shell级并行，适合无GUI环境

### 安装GNU Parallel

```bash
# macOS
brew install parallel

# Linux
sudo apt-get install parallel
# 或
sudo yum install parallel
```

### 创建目标列表

```bash
# targets.txt
http://localhost:8082
http://localhost:7860
http://localhost:3000
http://localhost:5000
```

### 并行执行

```bash
cat targets.txt | parallel -j 2 --bar \
  'echo "Attacking {}..." && /red-team {}'
```

**参数说明:**
- `-j 2` : 同时运行2个任务
- `--bar` : 显示进度条
- `{}` : 当前目标URL的占位符

**高级用法:**

```bash
# 限制并发数为2，失败自动重试1次
cat targets.txt | parallel -j 2 --retries 1 --joblog parallel.log \
  'python3 -c "
import sys
sys.path.insert(0, \".claude/skills/red-team/scripts\")
from red_team_session import init, get_next_action

init(url=\"{}\", max_iterations=8)
# ... 攻击逻辑 ...
"'
```

**优点:**
- ✅ 高度可控（并发数、重试、日志）
- ✅ 适合CI/CD和服务器环境
- ✅ 支持SSH远程并行
- ✅ 强大的日志和报告功能

**缺点:**
- ❌ 需要安装额外工具
- ❌ 配置相对复杂
- ❌ 不如Claude Code Task直观

---

## 实战示例

### 示例1: 测试本地2个agent（串行，最安全）

```bash
cd .claude/skills/red-team/scripts
./serial_attack.sh
```

预期输出:
```
Target 1/2: http://localhost:8082
✓ Target is accessible
Launching attack...
[+] Attack completed successfully!

Target 2/2: http://localhost:7860
✓ Target is accessible
Launching attack...
[+] Attack completed successfully!

BATCH ATTACK SUMMARY
Total Targets:      2
Successful Attacks: 2
Failed Attacks:     0
Success Rate:       100.0%
Total Duration:     187s
```

### 示例2: 测试本地2个agent（并行，最快）

在Claude Code中说:

```
请并行攻击这两个目标，使用Task tool后台运行:
- http://localhost:8082
- http://localhost:7860

分别启动两个独立的red-team agents。
```

Claude会启动两个后台任务，总时间约为单个攻击的时间。

### 示例3: 测试5个远程agent（GNU Parallel）

```bash
# 创建目标列表
cat > remote_targets.txt <<EOF
https://agent1.example.com
https://agent2.example.com
https://agent3.example.com
https://agent4.example.com
https://agent5.example.com
EOF

# 并行攻击（最多同时3个）
cat remote_targets.txt | parallel -j 3 --bar --joblog batch.log \
  'echo "=== Attacking {} ===" && /red-team {}'

# 查看日志
cat batch.log
```

---

## 性能对比

| 方法 | 2个目标耗时 | 10个目标耗时 | 资源占用 | 推荐场景 |
|------|-----------|-------------|---------|---------|
| **串行** | ~6分钟 | ~30分钟 | 低 | 大量目标、资源受限 |
| **Task并行** | ~3分钟 | 不推荐 | 高 | 少量目标、追求速度 |
| **GNU Parallel** | ~3分钟 | ~6分钟（j=5） | 中 | CI/CD、服务器环境 |

---

## 如何选择？

**新手/稳定优先:**
→ 使用方法1（串行脚本）

**追求速度，目标≤5个:**
→ 使用方法2（Claude Code Task并行）

**在服务器/CI环境，需要精确控制:**
→ 使用方法3（GNU Parallel）

---

## 常见问题

### Q: 为什么删除了之前的batch_attack.py？

A: 那个脚本有严重bug，`_execute_skill`函数只返回空字符串，无法真正执行攻击。现在提供的三种方法都是**真正可用**的。

### Q: Task并行和GNU Parallel哪个更好？

A:
- **Task并行**: 适合在Claude Code中交互使用，更直观
- **GNU Parallel**: 适合脚本化、自动化场景

### Q: 可以混合使用吗？

A: 可以！比如先用Task并行攻击2-3个重要目标（快速反馈），然后用串行脚本处理剩余的10+个目标。

### Q: 如何在Claude Code中使用Task并行？

A: 直接告诉我你要攻击的目标列表，我会用Task tool启动多个后台agent。例如：

```
请并行red team攻击:
1. http://localhost:8082
2. http://localhost:7860
3. https://example.com/agent
```

我会自动创建3个并行任务。

---

## 下一步

1. **立即测试:** 运行 `./serial_attack.sh` 测试串行攻击
2. **尝试并行:** 在Claude Code中说 "并行攻击8082和7860"
3. **查看结果:** 对比串行和并行的速度差异
4. **定制targets:** 编辑 `serial_attack.sh` 添加更多目标

---

## 相关文档

- `skill.md` - Red Team技能完整文档
- `../knowledge/nested-delegation-attack.md` - 攻击原理
- `run_batch_localhost.sh` - 原始批量脚本（已废弃）
