#!/usr/bin/env bash
# ============================================================
# update_and_sync.sh — 本机定时任务:
#   1. git pull 拉取 clash-rulesets 最新 main
#   2. 重新生成 providers（双保险，与 Actions 一致）
#   3. 同步 clash-xboard-subscription.yaml 到 xboard DB (clash + clashmeta)
#   4. 若有本地改动（生成器更新源）则 commit & push
#
# 由 systemd timer 每日触发: clash-rule-sync.timer
# ============================================================
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/clash-rulesets}"
LOG_FILE="${LOG_FILE:-/var/log/clash-rule-sync.log}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "=== 开始规则同步 ==="

cd "$REPO_DIR"

# 1. 拉取最新
log "git pull..."
git pull --ff-only origin main 2>&1 | tee -a "$LOG_FILE" || log "WARN: git pull 失败（网络或冲突），继续用本地版本"

# 2. 生成 providers（更新源规则）
log "生成 providers..."
python3 scripts/generate_providers.py --update-template 2>&1 | tail -5 | tee -a "$LOG_FILE"

# 3. 若有本地生成改动则提交
if ! git diff --quiet; then
    log "检测到本地改动，commit & push..."
    git add -A
    git -c user.name="clash-rulesets-bot" -c user.email="ipevel@users.noreply.github.com" \
        commit -m "chore: local rule regeneration $(date -u +%Y-%m-%d)" || true
    git push origin main 2>&1 | tee -a "$LOG_FILE" || log "WARN: push 失败"
fi

# 4. 同步到 xboard DB
log "同步到 xboard DB..."
python3 scripts/sync_to_xboard.py 2>&1 | tee -a "$LOG_FILE"

log "=== 同步完成 ==="
