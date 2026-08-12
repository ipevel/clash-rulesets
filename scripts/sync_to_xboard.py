#!/usr/bin/env python3
"""
sync_to_xboard.py — 把 clash-xboard-subscription.yaml 全量同步到 xboard 订阅面板
的 clash (id=2)、clashmeta (id=3)、stash (id=4) 订阅模板，并清理各节点 Redis 缓存。

用法:
  python3 scripts/sync_to_xboard.py
  DB_HOST=... DB_PASS=... python3 scripts/sync_to_xboard.py   # 覆盖 DB 配置

依赖: pymysql (pip install pymysql), sshpass (仅密码登录节点时需要)

密钥: 从仓库根目录 .secrets.json 读取（该文件已被 .gitignore 忽略，严禁提交）:
  {
    "db_pass": "...",
    "rn_pass": "...",
    "tarek_key": "<SSH_KEY>"
  }
"""
import os
import sys
import json

try:
    import pymysql
except ImportError:
    print("ERROR: 需要 pymysql: pip install pymysql")
    sys.exit(1)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_FILE = os.environ.get(
    "TEMPLATE_FILE", os.path.join(BASE, "clashmeta", "clash-xboard-subscription.yaml"))

# ---- 本地密钥（.secrets.json，不进 git）----
SECRETS = {}
_secrets_path = os.path.join(BASE, ".secrets.json")
if os.path.isfile(_secrets_path):
    with open(_secrets_path, encoding="utf-8") as _f:
        SECRETS = json.load(_f)

DB = dict(
    host=os.environ.get("DB_HOST", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.environ.get("DB_USER", "xboard"),
    password=os.environ.get("DB_PASS", SECRETS.get("db_pass", "")),
    database=os.environ.get("DB_NAME", "xboard"),
    charset="utf8mb4",
)

TEMPLATE_IDS = [2, 3, 4]  # 2=clash, 3=clashmeta, 4=stash

# 需要清 Redis 缓存的面板节点 (host, port, 认证方式)
# 注意: Xboard 的 SubscribeTemplate::getContent() 用 Redis remember(3600) 缓存模板 1 小时，
# 直接改库必须清缓存才能立即生效（缓存键在 db1: xboard_database_xboard_cachesubscribe_template:*）
NODES = [
    {"host": "<NODE1_IP>", "port": 54669, "key": SECRETS.get("tarek_key", "<SSH_KEY>"), "password": None},  # Tarek洛杉矶
    {"host": "<NODE2_IP>", "port": 22, "key": None, "password": SECRETS.get("rn_pass", "")},   # RN美国
]

def _ssh_cmd(node):
    """构造 SSH 清缓存命令。"""
    remote = f"root@{node['host']}"
    script = ("for db in 0 1; do docker exec xboard-redis-1 redis-cli -n $db --scan 2>/dev/null "
              "| grep -i template | while read k; do docker exec xboard-redis-1 redis-cli -n $db DEL \"$k\"; done; done")
    if node.get("password"):
        return ["sshpass", "-p", node["password"], "ssh", "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=10", "-p", str(node["port"]), remote, script]
    if node.get("key"):
        return ["ssh", "-i", node["key"], "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=10", "-p", str(node["port"]), remote, script]
    raise RuntimeError(f"节点 {node['host']} 没有配置 key 或 password")

def main():
    if not os.path.isfile(TEMPLATE_FILE):
        print(f"ERROR: 模板文件不存在: {TEMPLATE_FILE}")
        sys.exit(1)
    if not DB["password"]:
        print("ERROR: 缺少数据库密码（.secrets.json 未配置 db_pass 或 DB_PASS 环境变量）")
        sys.exit(1)

    with open(TEMPLATE_FILE, encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        print("ERROR: 模板内容为空")
        sys.exit(1)

    print("=== 开始同步 xboard 订阅模板 ===")
    print(f"DB: {DB['host']}:{DB['port']}/{DB['database']} ({DB['user']})")
    print(f"模板: {TEMPLATE_FILE} ({len(content.splitlines())} 行, {len(content)} 字符)")

    try:
        conn = pymysql.connect(**DB, autocommit=False)
    except Exception as e:
        print(f"ERROR: 连接数据库失败: {e}")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            for tid in TEMPLATE_IDS:
                cur.execute(
                    "SELECT name FROM v2_subscribe_templates WHERE id=%s", (tid,))
                row = cur.fetchone()
                if not row:
                    print(f"  [id={tid}] 不存在，跳过")
                    continue
                name = row[0]
                cur.execute(
                    "UPDATE v2_subscribe_templates SET content=%s, updated_at=NOW() WHERE id=%s",
                    (content, tid))
                conn.commit()
                cur.execute(
                    "SELECT LENGTH(content), updated_at FROM v2_subscribe_templates WHERE id=%s", (tid,))
                length, updated = cur.fetchone()
                print(f"  [id={tid}] {name}: 更新完成 (content {length} 字符, {updated})")
    finally:
        conn.close()

    print("=== 同步完成 ===")

    # ---- 清各节点 Redis 模板缓存（否则面板继续读旧模板直到 1 小时过期）----
    import subprocess
    print("\n=== 清理各节点 Redis 模板缓存 ===")
    for node in NODES:
        try:
            cmd = _ssh_cmd(node)
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                print(f"  {node['host']}: 缓存已清理")
            else:
                print(f"  {node['host']}: 清理失败: {r.stderr.strip()[:120]}")
        except Exception as e:
            print(f"  {node['host']}: 清理异常: {e}")

    print("\n=== 全部完成 ===")

if __name__ == "__main__":
    main()
