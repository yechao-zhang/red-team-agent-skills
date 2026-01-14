#!/bin/bash
# 并行批量攻击启动器
# 使用Claude Code的Task tool实现真正的并行执行

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "Parallel Red Team Attack Launcher"
echo "=========================================="
echo ""
echo "此脚本需要在Claude Code中执行"
echo "它会启动多个并行的red-team agent"
echo ""
echo "目标:"
echo "  - http://localhost:8082"
echo "  - http://localhost:7860"
echo ""

# 检查是否在Claude Code环境中
if [ -z "$CLAUDE_CODE" ]; then
    echo "⚠️  此脚本需要在Claude Code CLI中运行"
    echo ""
    echo "使用方法:"
    echo "  在Claude Code中运行:"
    echo "  > /red-team parallel 8082 7860"
    echo ""
    echo "或者手动执行:"
    echo "  claude '运行并行red team攻击: 8082和7860'"
    exit 1
fi

echo "✓ 在Claude Code环境中运行"
echo ""
echo "提示: 实际的并行执行由Claude Code的Task tool处理"
echo "      你应该直接在Claude Code中说:"
echo "      '并行攻击 localhost:8082 和 localhost:7860'"
