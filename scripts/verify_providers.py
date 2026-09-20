#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校验（改规则前后都要跑）：
1) 模板里每个 rule-provider 的 behavior，是否与它指向的文件 payload 格式匹配。
   不匹配 = 这份远程规则在内核里零命中。
2) 策略组成员名引用是否存在只差 emoji 前缀的错配（如 '全球直连' vs '🎯 全球直连'），
   这类错配会让 mihomo 顺延到下一个真实节点，表面上"改了却没生效"
用法: python3 scripts/verify_providers.py [profile.yaml ...]
"""
import os, re, sys
sys.stdout.reconfigure(encoding="utf-8")

BASE = r"E:\AI\Github\clash-rulesets"
PROV = os.path.join(BASE, "clashmeta", "providers")


def classify_file(path):
    numbered = bare = cidrs = 0
    samples = []
    cidr_re = re.compile(r"^\d{1,3}(\.\d{1,3}){3}(/\d{1,2})?$")
    ipv6_re = re.compile(r"^[0-9a-fA-F:]+(/\d{1,3})?$")
    rule_types = ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-REGEX",
                  "IP-CIDR", "IP-CIDR6", "IP-ASN", "GEOIP", "GEOSITE",
                  "PROCESS-NAME", "PROCESS-PATH", "MATCH", "SRC-IP-CIDR", "DST-PORT")
    for i, ln in enumerate(open(path, encoding="utf-8")):
        s = ln.rstrip()
        st = s.lstrip()
        if not st.startswith("- "):
            continue
        v = st[2:].strip()
        if i < 300:
            samples.append(v)
        # 规则行（含 IP-CIDR6 这种带冒号的类型）一律算 classical
        if "," in v and v.split(",")[0].strip().upper() in rule_types:
            numbered += 1
        elif cidr_re.match(v) or (ipv6_re.match(v) and "/" in v):
            cidrs += 1
        elif "," in v:
            numbered += 1
        else:
            bare += 1
    total = numbered + bare + cidrs
    if total == 0:
        return "EMPTY", samples
    if cidrs == total:
        return "ipcidr", samples
    if numbered == total:
        return "classical", samples
    if bare == total:
        return "domain", samples
    return "MIXED", samples


def parse_providers(txt):
    """线性提取 rule-providers 段里每个条目: name -> (behavior, url)"""
    lines = txt.splitlines()
    out = []
    in_block = False
    cur = None
    base_indent = None
    for ln in lines:
        if re.match(r"^rule-providers:", ln):
            in_block = True
            continue
        if in_block and re.match(r"^[A-Za-z]", ln):
            break
        if not in_block:
            continue
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        indent = len(ln) - len(ln.lstrip())
        strip = ln.strip()
        if base_indent is None and ln.strip():
            base_indent = indent
        # 多级嵌套 {} 单行风格（本机 profile）
        m1 = re.match(r"^\s+([\w-]+):\s*\{(.*)\}\s*$", ln)
        if m1:
            name, body = m1.group(1), m1.group(2)
            b = re.search(r"behavior:\s*(\S+?)[\s,}]", body)
            u = re.search(r"url:\s*['\"]?([^'\"]+\.yaml)", body)
            if u:
                out.append((name, b.group(1) if b else "-", u.group(1)))
            continue
        # 缩进式
        if indent == base_indent and strip.endswith(":") and len(strip) < 40:
            cur = {"name": strip[:-1], "behavior": None, "url": None}
            out.append(cur)
            continue
        if cur is not None and isinstance(cur, dict) and indent > base_indent:
            if strip.startswith("behavior:"):
                cur["behavior"] = strip.split(":", 1)[1].strip()
            elif strip.startswith("url:"):
                cur["url"] = strip.split(":", 1)[1].strip().strip("'\"")
    return out


def check(label, txt):
    print("=" * 78)
    print("配置:", label)
    print("=" * 78)
    items = parse_providers(txt)
    ok = True
    seen = 0
    for it in items:
        if isinstance(it, tuple):
            name, beh, url = it
        else:
            name, beh, url = it["name"], it["behavior"], it["url"]
        if not url:
            continue
        seen += 1
        fn = os.path.basename(url)
        fpath = os.path.join(PROV, fn)
        if not os.path.isfile(fpath):
            print("  !! %-16s behavior=%-10s 文件不存在 %s" % (name, beh or "-", fn))
            ok = False
            continue
        actual, samples = classify_file(fpath)
        good = (actual == beh)
        if not good:
            ok = False
        print("  %s %-16s behavior=%-10s payload=%-10s %s%s" % (
            "OK " if good else "!!!", name, beh or "-", actual, fn,
            "" if good else "  <-- 不匹配，规则零命中"))
        if not good and samples:
            print("        样例: %s" % samples[:2])
    print("  共 %d 个 provider -> %s\n" % (seen, "全部匹配 ✓" if ok else "存在不匹配 ✗"))
    return ok


def check_group_refs(txt, label):
    """策略组成员名引用检查。

    2026-09-20 踩坑：把 select 组成员写成 '全球直连'，而真实组名是 '🎯 全球直连'。
    mihomo 找不到该组，会顺延到列表里下一个真实节点 —— 结果"改了默认出站却毫无效果"，
    排查了一整轮才定位。此处专门抓这类只差 emoji 前缀的错配。
    """
    def strip_prefix(s):
        return re.sub(r"^[\U0001F000-\U0001FAFF\uFE0F\u200D\s]+", "", s).strip()

    lines = txt.splitlines()
    groups, members_of = [], {}
    cur = None
    in_blk = False
    for ln in lines:
        if ln.startswith("proxy-groups:"):
            in_blk = True
            continue
        if in_blk and ln and not ln.startswith(" ") and not ln.startswith("#"):
            break
        m = re.match(r"^  - name:\s*(.+)$", ln)
        if m and in_blk:
            cur = m.group(1).strip().strip("'\"")
            groups.append(cur)
            members_of[cur] = []
            continue
        mm = re.match(r"^      - (.+)$", ln)
        if mm and cur:
            members_of[cur].append(mm.group(1).strip().strip("'\""))

    BUILTIN = {"DIRECT", "REJECT", "GLOBAL", "PASS"}
    gset = set(groups)
    print("  [%s] 分组数 %d" % (label, len(groups)))
    wrong = []
    for g in groups:
        for mem in members_of[g]:
            if mem in gset or mem in BUILTIN:
                continue
            core = strip_prefix(mem)
            near = [x for x in gset if strip_prefix(x) == core]
            if near:
                wrong.append((g, mem, near[0]))
    if wrong:
        print("  !! 成员名与组名只差 emoji 前缀（引用必失败）:")
        for g, mem, real in wrong:
            print("     [%s] 引用「%s」，实际组名是「%s」" % (g, mem, real))
    else:
        print("  OK  %s 无 emoji 前缀错配" % label)
    if not groups:
        print("     (未解析到 proxy-groups 段，跳过)")
    return not wrong


if __name__ == "__main__":
    targets = sys.argv[1:]
    if not targets:
        targets = [os.path.join(BASE, "clashmeta", "clash-full.clash.yaml"),
                   os.path.join(BASE, "clashmeta", "clash-xboard-subscription.yaml")]
    all_ok = True
    for t in targets:
        if not os.path.isfile(t):
            print("skip (不存在):", t)
            continue
        raw = open(t, encoding="utf-8").read()
        all_ok &= check(os.path.basename(t), raw)
        all_ok &= check_group_refs(raw, os.path.basename(t))
    print("=" * 78)
    print("总结果:", "全部通过 ✓" if all_ok else "有问题 ✗")
    sys.exit(0 if all_ok else 1)
