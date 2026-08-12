#!/usr/bin/env python3
"""
sync_to_xboard.py — 把 clash-xboard-subscription.yaml 全量同步到 xboard 订阅面板
的 clash (id=2) 与 clashmeta (id=3) 订阅模板。

用法:
  python3 scripts/sync_to_xboard.py
  DB_HOST=... DB_PASS=... python3 scripts/sync_to_xboard.py   # 覆盖 DB 配置

依赖: pymysql (pip install pymysql)
"""
import os
import sys

try:
    import pymysql
except ImportError:
    print("ERROR: 需要 pymysql: pip install pymysql")
    sys.exit(1)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_FILE = os.environ.get(
    "TEMPLATE_FILE", os.path.join(BASE, "clashmeta", "clash-xboard-subscription.yaml"))

DB = dict(
    host=os.environ.get("DB_HOST", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.environ.get("DB_USER", "xboard"),
    password=os.environ.get("DB_PASS", "DB_PASS_PLACEHOLDER"),
    database=os.environ.get("DB_NAME", "xboard"),
    charset="utf8mb4",
)

TEMPLATE_IDS = [2, 3]  # 2=clash, 3=clashmeta

def main():
    if not os.path.isfile(TEMPLATE_FILE):
        print(f"ERROR: 模板文件不存在: {TEMPLATE_FILE}")
        sys.exit(1)

    with open(TEMPLATE_FILE, encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        print("ERROR: 模板内容为空")
        sys.exit(1)

    print(f"=== 开始同步 xboard 订阅模板 ===")
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

if __name__ == "__main__":
    main()
