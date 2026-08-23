#!/usr/bin/env python3
"""dedup_providers.py — 清理 provider 文件 + 主配置内联规则的重复行。

设计原则:
  - 幂等: 重跑无副作用(去重后无重复可去)
  - 只删完全相同的行(同 TYPE+VALUE+POLICY), 不合并派生变体
  - 不动文件顺序、注释、RULE-SET / rule-providers / 段头结构
尽量保持格式化一致(()内引号风格)。
"""
import glob
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVIDER_DIR = os.path.join(BASE, "clashmeta", "providers")
MAIN_CONFIGS = [
    os.path.join(BASE, "clashmeta", "clash-full.clash.yaml"),
    os.path.join(BASE, "clashmeta", "clash-selected.clash.yaml"),
]


def dedup_provider(path):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    out_lines = []
    seen = set()
    removed = 0
    in_payload = False
    for line in lines:
        s = line.rstrip("\n")
        if s.lstrip().startswith("payload:"):
            in_payload = True
        if in_payload and s.lstrip().startswith("- "):
            # 规则行 (payload 内), 精确去重
            key = s.lstrip()
            if key in seen:
                removed += 1
                continue
            seen.add(key)
        out_lines.append(line)
    if removed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(out_lines)
    return removed


def dedup_main_config(path):
    """对主配置内联规则行去重(不碰 RULE-SET 行)。"""
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    out_lines = []
    seen = set()
    removed = 0
    for line in lines:
        s = line.rstrip("\n")
        stripped = s.lstrip()
        is_rule = stripped.startswith("- ") and not stripped.startswith("- RULE-SET,")
        if is_rule:
            key = stripped
            if key in seen:
                removed += 1
                continue
            seen.add(key)
        out_lines.append(line)
    if removed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(out_lines)
    return removed


def main():
    total = 0
    print("== Provider 文件去重 ==")
    for p in sorted(glob.glob(os.path.join(PROVIDER_DIR, "*.yaml"))):
        if "README" in os.path.basename(p):
            continue
        n = dedup_provider(p)
        if n:
            print(f"  {os.path.basename(p)}: 移除 {n} 行重复")
            total += n
    print("== 主配置内联去重 ==")
    for cfg in MAIN_CONFIGS:
        n = dedup_main_config(cfg)
        if n:
            print(f"  {os.path.basename(cfg)}: 移除 {n} 行重复")
            total += n
    print(f"TOTAL: 移除 {total} 行重复规则")


if __name__ == "__main__":
    main()