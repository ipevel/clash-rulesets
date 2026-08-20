#!/usr/bin/env python3
"""
clash-full / clash-selected 配置重构。

设计：in-place 修改 lines 数组（不重新拼接），保证 YAML 缩进结构不变。

段头格式: "  # === Name (N rules) ==="（前导 2 空格，括号内是数字 rules）
也支持:   "  # Name" (兜底段、Telegram IP 等)

操作：
  1) 全文规则行去重（同 TYPE+VALUE 视为同一条）
  2) 对目标段：整段替换为 1 条 RULE-SET 引用，同时把段内规则同步追加到
     providers/<name>.yaml（保留原段的规则，不丢）
  3) 自动生成 rule-providers: 块（独立配置模式用本地路径）
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVIDER_DIR = os.path.join(BASE, "clashmeta", "providers")
FULL = os.path.join(BASE, "clashmeta", "clash-full.clash.yaml")
SELECTED = os.path.join(BASE, "clashmeta", "clash-selected.clash.yaml")

# 段名 → 抽成 RULE-SET 后的策略
POLICY = {
    "Apple": "Proxy", "OpenAI": "Proxy", "Claude": "Proxy",
    "GoogleGemini": "Proxy", "GoogleFCM": "Proxy", "GooglePlay": "Proxy",
    "Telegram": "Proxy", "TelegramCIDR": "Proxy",
    "Microsoft": "Proxy", "Google": "Proxy",
    "GitHub": "Proxy", "Bing": "Proxy", "OneDrive": "Proxy", "Xbox": "Proxy",
    "Netflix": "Proxy", "TikTok": "Proxy", "Instagram": "Proxy",
    "ProxyGFWlist": "Proxy", "ProxyMedia": "Proxy",
    "ChinaDomain": "DIRECT", "ChinaMedia": "DIRECT",
    "NetEaseMusic": "DIRECT",
    "BanAD": "REJECT", "BanADCompany": "REJECT",
    "LocalAreaNetwork": "DIRECT", "LAN": "DIRECT",
    "TelegramIP": "Proxy", "Private": "DIRECT",
}

# selected 配置只外置精选
SELECTED_ONLY = {
    "Apple", "OpenAI", "Claude", "GoogleGemini", "GoogleFCM", "GooglePlay",
    "Telegram", "TelegramCIDR", "Microsoft", "Netflix", "TikTok", "Instagram",
    "GitHub", "Bing", "OneDrive", "Xbox", "ProxyGFWlist",
    "ChinaDomain", "ChinaMedia", "NetEaseMusic",
}

# 段头正则（捕获前导空格、段名、原条数）
SECTION_RE = re.compile(r"^(\s*)#\s*(?:===\s*([^\s(]+)\s*\(([0-9]+)\s*rules\)\s*===|([A-Z][A-Za-z0-9 ]+))\s*$")

def find_segment_end(lines, start):
    i = start
    while i < len(lines):
        line = lines[i]
        if SECTION_RE.match(line):
            return i
        i += 1
    return i

def extract_rules_in_segment(lines, start, end):
    """提取段内的规则行（不包含段头本身）。返回 [(raw_line, (TYPE, VALUE))]"""
    out = []
    for j in range(start, end):
        s = lines[j].strip()
        if s.startswith("- "):
            m = re.match(r"^([A-Z\-]+),([^,]+),", s[2:])
            if m:
                out.append((lines[j], (m.group(1).upper(), m.group(2).strip())))
    return out

def get_existing_provider_keys(name):
    """读 providers/<name>.yaml 现有 payload 的 (TYPE,VALUE) 集合"""
    path = os.path.join(PROVIDER_DIR, f"{name}.yaml")
    keys = set()
    if not os.path.exists(path):
        return keys
    in_payload = False
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s == "payload:":
                in_payload = True
                continue
            if in_payload and s.startswith("- "):
                m = re.match(r"^([A-Z\-]+),([^,]+),", s[2:])
                if m:
                    keys.add((m.group(1).upper(), m.group(2).strip()))
    return keys

def append_to_provider(name, new_rule_lines):
    """把新规则行追加到 providers/<name>.yaml（去重 + 保留原文件其他行）。
    关键: 统一缩进为 2 空格（跟原 provider 文件格式一致）。"""
    path = os.path.join(PROVIDER_DIR, f"{name}.yaml")
    # 读现有
    if not os.path.exists(path):
        # 创建新文件
        with open(path, "w") as f:
            f.write(f"# {name}\npayload:\n")
            for raw_line, _ in new_rule_lines:
                rule = raw_line.strip()
                if rule.startswith("- "):
                    f.write(f"  - {rule[2:]}\n")
                else:
                    f.write(f"{rule}\n")
        return len(new_rule_lines)

    with open(path) as f:
        text = f.read()
    existing_keys = get_existing_provider_keys(name)

    # 找 payload 段的边界:
    #   - 段开始:  "payload:" 行
    #   - 段结束:  下一个非 list 行（不以 "- " 开头的行，可能是空行/EOF）
    lines = text.splitlines(keepends=True)
    payload_start = -1
    payload_end = len(lines)  # 默认到 EOF
    for idx, line in enumerate(lines):
        if line.rstrip() == "payload:":
            payload_start = idx
            continue
        if payload_start >= 0 and idx > payload_start:
            stripped = line.strip()
            # list 行必须是 "- ..." 开头（允许前导空格）
            if stripped and not stripped.startswith("- "):
                payload_end = idx
                break

    # 提取新规则（去重 + 转格式）
    new_formatted = []
    for raw_line, key in new_rule_lines:
        if key in existing_keys:
            continue
        rule = raw_line.strip()
        if rule.startswith("- "):
            content = rule[2:]
        else:
            content = rule
        new_formatted.append(f"  - {content}\n")
        existing_keys.add(key)

    # 在 payload_end 之前插入新规则
    new_lines = lines[:payload_end] + new_formatted + lines[payload_end:]
    with open(path, "w") as f:
        f.writelines(new_lines)
    return len(new_formatted)

def process(config_path, target_sections):
    with open(config_path) as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    seen = set()
    stats = {"extracted": 0, "kept_inline": 0, "deduped": 0, "sections_seen": 0,
             "extracted_names": [], "rules_moved_to_providers": 0}

    def infer_policy(seg_rules):
        """从段内规则推断策略：看大多数规则的策略"""
        cnt = {"DIRECT": 0, "REJECT": 0, "Proxy": 0}
        for raw, _ in seg_rules[:50]:  # 只看前 50 条就够
            s = raw.strip()
            for k in ["DIRECT", "REJECT", "Proxy"]:
                if f",{k}" in s or s.endswith(f",{k}"):
                    cnt[k] += 1
                    break
        if not any(cnt.values()): return "Proxy"
        return max(cnt, key=cnt.get)

    while i < len(lines):
        line = lines[i]
        m = SECTION_RE.match(line)

        if m and (m.group(2) or m.group(4)) in target_sections:
            name = m.group(2) or m.group(4)
            provider_file = f"{name}.yaml"
            stats["sections_seen"] += 1
            stats["extracted"] += 1
            stats["extracted_names"].append(name)

            # 段内规则
            end = find_segment_end(lines, i + 1)
            segment_rules = extract_rules_in_segment(lines, i + 1, end)

            # 策略: POLICY 注册的优先, 否则自动推断
            if name in POLICY:
                policy = POLICY[name]
            else:
                policy = infer_policy(segment_rules)

            # 段内规则追加到 provider
            if segment_rules:
                added = append_to_provider(name, segment_rules)
                stats["rules_moved_to_providers"] += added
                for _, _ in segment_rules:
                    stats["deduped"] += 1

            new_lines.append(f"- RULE-SET,{provider_file},{policy}\n")
            i = end
            continue

        s = line.strip()
        if s.startswith("- ") and (",Proxy," in s or ",DIRECT," in s or s.endswith(",REJECT") or ",REJECT," in s):
            parts = s[2:].split(",")
            if len(parts) >= 2:
                key = (parts[0].upper(), parts[1].strip())
                if key in seen:
                    stats["deduped"] += 1
                    i += 1
                    continue
                seen.add(key)
                stats["kept_inline"] += 1

        if m:
            stats["sections_seen"] += 1

        new_lines.append(line)
        i += 1

    # 注入 rule-providers: 块
    if stats["extracted_names"]:
        new_lines.append("\n")
        new_lines.append("rule-providers:\n")
        for name in stats["extracted_names"]:
            key = name.lower()
            behavior = "ipcidr" if name in ("TelegramCIDR", "ChinaIp", "ChinaIpV6", "ChinaCompanyIp", "TelegramIP") else "domain"
            new_lines.append(f"  {key}:\n")
            new_lines.append(f"    type: http\n")
            new_lines.append(f"    behavior: {behavior}\n")
            new_lines.append(f"    url: \"https://fastly.jsdelivr.net/gh/ipevel/clash-rulesets@main/clashmeta/providers/{name}.yaml\"\n")
            new_lines.append(f"    path: \"./ruleset/{key}.yaml\"\n")
            new_lines.append(f"    interval: 86400\n")

    with open(config_path, "w") as f:
        f.writelines(new_lines)
    return stats

def main():
    full_targets = set()
    for fname in os.listdir(PROVIDER_DIR):
        if not fname.endswith(".yaml"):
            continue
        name = fname[:-5]
        if name in POLICY:
            full_targets.add(name)

    # 加上所有有规则的内联段（>=200 条），让它们也生成 provider 文件
    # 避免漏抽 BanEasyList 等 Loyalsoldier 来源的大段（auto 策略由 process() 推断）
    SECTION_RE_LOCAL = re.compile(r"^(\s*)#\s*===\s*([^\s(]+)\s*\(([0-9]+)\s*rules\)\s*===\s*$")
    with open(FULL) as f:
        for line in f:
            m = SECTION_RE_LOCAL.match(line)
            if not m: continue
            name = m.group(2)
            n = int(m.group(3))
            if n >= 200:
                full_targets.add(name)

    selected_targets = {n for n in SELECTED_ONLY
                        if os.path.exists(os.path.join(PROVIDER_DIR, f"{n}.yaml"))}
    # 加上 selected 配置里 >=200 条的段
    with open(SELECTED) as f:
        for line in f:
            m = SECTION_RE_LOCAL.match(line)
            if not m: continue
            name = m.group(2)
            n = int(m.group(3))
            if n >= 200:
                selected_targets.add(name)

    print("=== full 配置 ===")
    s1 = process(FULL, full_targets)
    print(f"  扫描段: {s1['sections_seen']}, 抽成 RULE-SET: {s1['extracted']} 段")
    print(f"  保留内联: {s1['kept_inline']} 条, 去重移除: {s1['deduped']} 条")
    print(f"  追加到 provider: {s1['rules_moved_to_providers']} 条")

    print("\n=== selected 配置 ===")
    s2 = process(SELECTED, selected_targets)
    print(f"  扫描段: {s2['sections_seen']}, 抽成 RULE-SET: {s2['extracted']} 段")
    print(f"  保留内联: {s2['kept_inline']} 条, 去重移除: {s2['deduped']} 条")
    print(f"  追加到 provider: {s2['rules_moved_to_providers']} 条")

    print("\n=== 文件大小 ===")
    for f in [FULL, SELECTED]:
        if os.path.exists(f):
            print(f"  {os.path.basename(f):35s}  {os.path.getsize(f):>10d} bytes  ({os.path.getsize(f)/1024:.1f} KB)")

if __name__ == "__main__":
    main()
