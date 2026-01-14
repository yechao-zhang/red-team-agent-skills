#!/bin/bash
# 串行批量攻击脚本 - 使用现有的red-team工作流
# 安全、稳定、资源占用低

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$(cd "$SCRIPT_DIR/../../../../results" && pwd)"

echo "=========================================="
echo "Serial Red Team Attack - Localhost Targets"
echo "=========================================="
echo ""

# 定义目标
TARGETS=(
    "http://localhost:8082"
    "http://localhost:7860"
)

# 创建批量结果目录
BATCH_TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BATCH_DIR="$RESULTS_DIR/serial-batch/batch_$BATCH_TIMESTAMP"
mkdir -p "$BATCH_DIR"

echo "Batch results will be saved to: $BATCH_DIR"
echo ""

# 记录开始时间
START_TIME=$(date +%s)
SUCCESS_COUNT=0
FAIL_COUNT=0

# 串行攻击每个目标
for i in "${!TARGETS[@]}"; do
    TARGET="${TARGETS[$i]}"
    TARGET_NUM=$((i + 1))

    echo ""
    echo "=========================================="
    echo "Target $TARGET_NUM/${#TARGETS[@]}: $TARGET"
    echo "=========================================="

    # 检查目标是否可访问
    if curl -s --connect-timeout 2 "$TARGET" >/dev/null 2>&1; then
        echo "✓ Target is accessible"
    else
        echo "✗ WARNING: Target is NOT accessible"
        echo "  Make sure the service is running on this port"
    fi

    # 执行攻击（通过Python red_team_session）
    echo ""
    echo "Launching attack..."

    cd "$SCRIPT_DIR"
    python3 <<EOF
import sys
import os
sys.path.insert(0, "$SCRIPT_DIR")

from red_team_session import init, get_next_action

# 初始化攻击
init(url="$TARGET", max_iterations=8, transport_type="browser")

# 执行攻击循环（最多8次迭代）
for iteration in range(8):
    action = get_next_action()

    if not action:
        break

    if action.get("action") == "complete":
        print("\n[+] Attack completed successfully!")
        sys.exit(0)

print("\n[-] Attack completed but may not have fully succeeded")
sys.exit(1)
EOF

    ATTACK_EXIT_CODE=$?

    if [ $ATTACK_EXIT_CODE -eq 0 ]; then
        echo "✓ SUCCESS: Target $TARGET"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo "✗ FAILED: Target $TARGET"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    # 移动结果到批量目录
    LATEST_RUN=$(ls -td "$RESULTS_DIR/red-team-task/run_"* 2>/dev/null | head -1)
    if [ -n "$LATEST_RUN" ]; then
        TARGET_NAME=$(echo "$TARGET" | sed 's|http://||' | sed 's|/||g' | sed 's|::|_|g')
        mv "$LATEST_RUN" "$BATCH_DIR/${TARGET_NUM}_${TARGET_NAME}"
        echo "Results moved to: $BATCH_DIR/${TARGET_NUM}_${TARGET_NAME}"
    fi

done

# 计算总时间
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# 生成摘要
echo ""
echo "=========================================="
echo "BATCH ATTACK SUMMARY"
echo "=========================================="
echo "Total Targets:      ${#TARGETS[@]}"
echo "Successful Attacks: $SUCCESS_COUNT"
echo "Failed Attacks:     $FAIL_COUNT"
echo "Success Rate:       $(awk "BEGIN {printf \"%.1f%%\", ($SUCCESS_COUNT/${#TARGETS[@]})*100}")"
echo "Total Duration:     ${DURATION}s"
echo "=========================================="
echo ""
echo "All results saved to: $BATCH_DIR"

# 生成JSON摘要
cat > "$BATCH_DIR/summary.json" <<SUMMARY
{
  "timestamp": "$(date -Iseconds)",
  "duration_seconds": $DURATION,
  "total_targets": ${#TARGETS[@]},
  "successful": $SUCCESS_COUNT,
  "failed": $FAIL_COUNT,
  "success_rate": "$(awk "BEGIN {printf \"%.1f%%\", ($SUCCESS_COUNT/${#TARGETS[@]})*100}")",
  "targets": [
$(for TARGET in "${TARGETS[@]}"; do echo "    \"$TARGET\","; done | sed '$ s/,$//')
  ]
}
SUMMARY

echo "Summary saved to: $BATCH_DIR/summary.json"

# 打开结果目录（macOS）
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "$BATCH_DIR"
fi

exit $FAIL_COUNT
