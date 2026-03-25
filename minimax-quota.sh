#!/bin/bash

# MiniMax Token Plan 用量查询脚本
# 用法: ./minimax-quota.sh

# ── 配置 ────────────────────────────────────────────────────────────────
CONFIG_FILE="${HOME}/.minimax-quota.json"

load_config() {
  if ! command -v jq &>/dev/null; then
    echo "✗ 错误: 未安装 jq 命令"
    if [[ "$(uname)" == "Darwin" ]]; then
      echo "  请运行: brew install jq"
    else
      echo "  请运行: sudo apt update && sudo apt install jq"
    fi
    exit 1
  fi

  if [[ -f "$CONFIG_FILE" ]]; then
    API_KEY=$(jq -r '.api_key' "$CONFIG_FILE" 2>/dev/null)
  fi

  if [[ -z "$API_KEY" || "$API_KEY" == "null" || ${#API_KEY} -lt 5 ]]; then
    echo "⚠  未找到有效配置文件 ${CONFIG_FILE}"
    echo ""
    echo -n "请输入 MiniMax Token Plan API Key: "
    read -r API_KEY
    echo ""
    mkdir -p "$(dirname "$CONFIG_FILE")"
    printf '{"api_key": "%s"}\n' "$API_KEY" > "$CONFIG_FILE"
    chmod 600 "$CONFIG_FILE"
    echo "✓ 配置已保存到 ${CONFIG_FILE}"
    echo ""
  fi
}

load_config

# ── API 调用 ───────────────────────────────────────────────────────────
RESPONSE=$(curl -s "https://www.minimaxi.com/v1/api/openplatform/coding_plan/remains" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Accept: application/json" \
  --max-time 10)

STATUS=$(echo "$RESPONSE" | jq -r '.base_resp.status_code' 2>/dev/null)
if [[ "$STATUS" != "0" ]]; then
  MSG=$(echo "$RESPONSE" | jq -r '.base_resp.status_msg' 2>/dev/null)
  echo "✗ API 请求失败: $MSG"
  echo ""
  echo "提示: Token Plan API Key 不能和普通 API Key 混用"
  echo "      请确认你使用的是 Token Plan 专用 Key（sk-cp- 开头）"
  exit 1
fi

# ── 解析数据 ──────────────────────────────────────────────────────────
DATA=$(echo "$RESPONSE" | jq -r '.model_remains[0]')

TOTAL=$(echo "$DATA" | jq -r '.current_interval_total_count')
REMAINING=$(echo "$DATA" | jq -r '.current_interval_usage_count')
# 防止 null/空字符串导致 bash 算术失败
REMAINING=${REMAINING:-0}
USED=$((TOTAL - REMAINING))
REMAINS_MS=$(echo "$DATA" | jq -r '.remains_time')

REMAINS_SEC=$((REMAINS_MS / 1000))
REMAINS_HOURS=$((REMAINS_SEC / 3600))
REMAINS_MINS=$(((REMAINS_SEC % 3600) / 60))

PCT=$(awk -v u="$USED" -v t="$TOTAL" 'BEGIN { printf "%.0f", (t==0 ? 0 : (u/t)*100) }')

# 状态
if (( PCT >= 85 )); then
  STATUS_TXT="⚠  剩余额度不足 15%，请注意使用！"
elif (( PCT >= 60 )); then
  STATUS_TXT="💡 剩余额度使用过半，请留意"
else
  STATUS_TXT="✓  额度充足，可正常使用"
fi

# ── Python 渲染（纯文本，无边框） ─────────────────────────────────────
python3 - "$USED" "$TOTAL" "$REMAINING" "$PCT" "$REMAINS_HOURS" "$REMAINS_MINS" "$STATUS_TXT" <<'PYEOF'
import sys, unicodedata
from datetime import datetime

USED=int(sys.argv[1]); TOTAL=int(sys.argv[2]); REMAINING=int(sys.argv[3])
PCT=int(sys.argv[4])
R_HOURS=int(sys.argv[5]); R_MINS=int(sys.argv[6])
STATUS=sys.argv[7]

def cbar(pct):
    """返回恰好 BAR_W 格宽的彩色进度条"""
    if pct >= 85:   c='\033[31m'
    elif pct >= 60: c='\033[33m'
    else:           c='\033[32m'
    r='\033[0m'
    n = 30 * pct // 100
    pct_str = f'  {pct}%'
    pct_vw = sum(2 if unicodedata.east_asian_width(ch) in ('F','W') else 1 for ch in pct_str)
    bar_visual = 60 + pct_vw
    trailing = 66 - bar_visual
    return c + '█'*n + r + '░'*(30-n) + pct_str + ' ' * max(0, trailing)

INFO_W = 60
print()
print(f'  MiniMax Token Plan  ·  用量状态')
print(f'  {"─" * INFO_W}')
print(f'  当前模型        MiniMax-M2.7')
print(f'  时间窗口        5 小时滚动窗口')
print()
print(f'  5小时窗口额度')
print(f'    {cbar(PCT)}')
print(f'    已用: {USED}  / {TOTAL}   剩余: {REMAINING}')
print(f'    重置倒计时: {R_HOURS} 小时 {R_MINS} 分钟')
print()
print(f'  {STATUS}')
print()
print(f'  更新于: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()
PYEOF
