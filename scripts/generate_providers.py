#!/usr/bin/env python3
"""
从 blackmatrix7/ios_rule_script + Loyalsoldier/clash-rules 拉取最新 Clash 规则，
生成 ipevel/clash-rulesets 的 provider 文件。

源格式支持三种:
  1. 标准 Clash 规则行  (DOMAIN-SUFFIX,xxx / IP-CIDR,x / DOMAIN-KEYWORD,x ...)
  2. 裸域名列表         ('xxx.com' / xxx.com)  -> DOMAIN,xxx.com
  3. AdGuard 格式       ('+.xxx.com')          -> DOMAIN-SUFFIX,xxx.com
  4. 裸 CIDR 列表       (91.108.4.0/22)        -> IP-CIDR,x,policy,no-resolve

输出: clashmeta/providers/*.yaml (payload 格式，规则行带策略)
模板: clashmeta/clash-xboard-subscription.yaml 的 rule-providers URL 统一 @main

用法:
  python3 scripts/generate_providers.py
  python3 scripts/generate_providers.py --update-template   # 生成后把模板 URL 改为 @main
"""
import os
import re
import sys
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVIDER_DIR = os.path.join(BASE, "clashmeta", "providers")
TEMPLATE = os.path.join(BASE, "clashmeta", "clash-xboard-subscription.yaml")

BM7 = "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/{cat}/{file}"
LOYO = "https://raw.githubusercontent.com/Loyalsoldier/clash-rules/release/{file}"
UA = {"User-Agent": "Mozilla/5.0 (clash-rulesets-updater)"}

# 规则类型前缀（标准 Clash 规则行）
RULE_TYPES = ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-REGEX",
              "IP-CIDR", "IP-CIDR6", "IP-ASN", "GEOIP", "GEOSITE",
              "PROCESS-NAME", "MATCH", "RULE-SET", "SRC-IP-CIDR", "DST-PORT")

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")

def parse_payload(text):
    """提取 payload: 块内的条目（去引号、去注释）。返回原始条目列表。"""
    items = []
    in_payload = False
    for line in text.splitlines():
        s = line.strip()
        if s == "payload:":
            in_payload = True
            continue
        if in_payload:
            if s.startswith("- "):
                item = s[2:].strip()
                # 去单引号/双引号
                if len(item) >= 2 and item[0] in "'\"" and item[-1] == item[0]:
                    item = item[1:-1]
                if item:
                    items.append(item)
            elif s and not s.startswith("#"):
                pass  # payload 块内的非列表行，忽略
    return items

def classify(item):
    """判断条目类型: rule / bare / adguard / cidr / process / skip"""
    if item.startswith("'+"):
        return "adguard"
    if item.startswith("+."):
        return "adguard"
    if item.startswith("'") or item.startswith('"'):
        return "bare"
    head = item.split(",")[0].upper()
    if head in RULE_TYPES:
        return "rule"
    # 纯 IP/CIDR
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}(/\d{1,2})?$", item):
        return "cidr"
    if ":" in item and re.match(r"^[0-9a-fA-F:]+(/\d{1,3})?$", item):
        return "cidr"
    if re.match(r"^[\w.-]+\.\w{2,}$", item):
        return "bare"
    return "skip"

def to_rule(item, policy, kind=None):
    """把条目转成带策略的 Clash 规则行。"""
    kind = kind or classify(item)
    if kind == "rule":
        parts = [p.strip() for p in item.split(",")]
        rtype = parts[0].upper()
        if rtype == "PROCESS-NAME":
            return item  # 原样
        if len(parts) >= 3 and parts[-1] in ("Proxy", "DIRECT", "REJECT", "no-resolve", "NO-DIRECT"):
            if parts[-1] == "no-resolve" and len(parts) >= 4:
                return item  # 已带完整策略
            return item
        if rtype in ("IP-CIDR", "IP-CIDR6", "IP-ASN"):
            return f"{item},{policy},no-resolve" if rtype != "IP-ASN" else f"{item},{policy}"
        return f"{item},{policy}"
    if kind == "bare":
        # 裸域名 -> DOMAIN（精确匹配）
        return f"DOMAIN,{item},{policy}"
    if kind == "adguard":
        # +.domain -> DOMAIN-SUFFIX
        dom = item.lstrip("+.'\"").strip()
        return f"DOMAIN-SUFFIX,{dom},{policy}"
    if kind == "cidr":
        if "/" in item:
            return f"IP-CIDR,{item},{policy},no-resolve"
        return f"IP-CIDR,{item}/32,{policy},no-resolve"
    return None

def filter_cn_proxy(rules):
    """Proxy 策略的规则剔除 .cn 域名（防止国内服务误走代理）。"""
    out = []
    for r in rules:
        if ".cn" in r.lower() and (r.startswith("DOMAIN-SUFFIX,") or r.startswith("DOMAIN,")):
            continue
        out.append(r)
    return out

def dedup(rules):
    seen, out = set(), []
    for r in rules:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out

def write_provider(fname, rules, header_note=""):
    os.makedirs(PROVIDER_DIR, exist_ok=True)
    path = os.path.join(PROVIDER_DIR, fname)
    name = fname.replace(".yaml", "")
    with open(path, "w") as f:
        f.write(f"# {name} - {len(rules)} rules{header_note}\n")
        f.write("payload:\n")
        for r in rules:
            f.write(f"  - {r}\n")
    return path, len(rules)

# (源URL, 目标文件, 策略, 格式类型, 是否滤.cn)
SOURCES = [
    # --- 广告（blackmatrix7 AdvertisingLite，量级可控）---
    (BM7.format(cat="AdvertisingLite", file="AdvertisingLite_Domain.yaml"), "BanAD.yaml",       "REJECT", "auto", False),
    (BM7.format(cat="AdvertisingLite", file="AdvertisingLite.yaml"),       "BanADCompany.yaml", "REJECT", "rule",  False),
    # --- AI ---
    (BM7.format(cat="OpenAI", file="OpenAI.yaml"), "OpenAI.yaml",       "Proxy", "rule", True),
    (BM7.format(cat="Claude", file="Claude.yaml"), "Claude.yaml",       "Proxy", "rule", True),
    (BM7.format(cat="Gemini", file="Gemini.yaml"), "GoogleGemini.yaml", "Proxy", "rule", True),
    # --- 流媒体 & 社交 ---
    (BM7.format(cat="YouTube",   file="YouTube.yaml"),   "ProxyMedia.yaml", "Proxy", "rule", True),
    (BM7.format(cat="TikTok",    file="TikTok.yaml"),    "TikTok.yaml",     "Proxy", "rule", True),
    (BM7.format(cat="Instagram", file="Instagram.yaml"), "Instagram.yaml",  "Proxy", "rule", True),
    (BM7.format(cat="Netflix",   file="Netflix.yaml"),   "Netflix.yaml",    "Proxy", "rule", True),
    # --- Google / Apple / GitHub / 微软 ---
    (BM7.format(cat="Google",    file="Google.yaml"),    "Google.yaml",    "Proxy", "rule", True),
    (BM7.format(cat="GoogleFCM", file="GoogleFCM.yaml"), "GoogleFCM.yaml", "Proxy", "rule", True),
    (BM7.format(cat="Apple",     file="Apple.yaml"),     "Apple.yaml",     "Proxy", "rule", True),
    (BM7.format(cat="GitHub",    file="GitHub.yaml"),    "GitHub.yaml",    "Proxy", "rule", True),
    (BM7.format(cat="Bing",      file="Bing.yaml"),      "Bing.yaml",      "Proxy", "rule", True),
    (BM7.format(cat="OneDrive",  file="OneDrive.yaml"),  "OneDrive.yaml",  "Proxy", "rule", True),
    (BM7.format(cat="Microsoft", file="Microsoft.yaml"), "Microsoft.yaml", "Proxy", "rule", True),
    (BM7.format(cat="Xbox",      file="Xbox.yaml"),      "Xbox.yaml",      "Proxy", "rule", True),
    # --- 国内 ---
    (BM7.format(cat="BiliBili",     file="BiliBili.yaml"),     "ChinaMedia.yaml",  "DIRECT", "rule", False),
    (BM7.format(cat="NetEaseMusic", file="NetEaseMusic.yaml"), "NetEaseMusic.yaml", "DIRECT", "rule", False),
    (BM7.format(cat="China",        file="China_Domain.yaml"), "ChinaDomain.yaml",  "DIRECT", "auto", False),
    # --- Telegram / GFW ---
    (BM7.format(cat="Telegram", file="Telegram.yaml"), "Telegram.yaml", "Proxy", "rule", True),
    (LOYO.format(file="gfw.txt"),           "ProxyGFWlist.yaml", "Proxy", "adguard", True),
    (LOYO.format(file="telegramcidr.txt"),  "TelegramCIDR.yaml", "Proxy", "cidr",    False),
]

def main():
    update_tpl = "--update-template" in sys.argv
    results = []
    total = 0
    for url, out, policy, fmt, filter_cn in SOURCES:
        try:
            text = fetch(url)
            items = parse_payload(text)
            rules = []
            for it in items:
                if fmt == "rule":
                    r = to_rule(it, policy, "rule")
                elif fmt == "adguard":
                    r = to_rule(it, policy, "adguard")
                elif fmt == "cidr":
                    r = to_rule(it, policy, "cidr")
                else:  # auto
                    r = to_rule(it, policy)
                if r:
                    rules.append(r)
            if filter_cn:
                rules = filter_cn_proxy(rules)
            rules = dedup(rules)
            if not rules:
                raise RuntimeError("empty rules")
            path, n = write_provider(out, rules)
            src = url.split("/")[-1]
            results.append(f"OK   {out:20s} {n:7d} rules  <- {src}")
            total += n
        except Exception as e:
            results.append(f"FAIL {out:20s} {url}: {e}")

    # --- GooglePlay 从 Google.yaml 提取 ---
    try:
        google_rules = []
        gpath = os.path.join(PROVIDER_DIR, "Google.yaml")
        if os.path.exists(gpath):
            with open(gpath) as f:
                for line in f:
                    if line.startswith("  - DOMAIN") or line.startswith("  - PROCESS"):
                        google_rules.append(line.strip()[4:])
        play_kw = ("googleplay", "play.google", "playgames", "android.play")
        play = [r for r in google_rules if any(k in r.lower() for k in play_kw)]
        rest = [r for r in google_rules if not any(k in r.lower() for k in play_kw)]
        # 更新 Google.yaml（去掉 play 部分，避免重叠）
        with open(gpath, "w") as f:
            f.write(f"# Google - {len(rest)} rules\npayload:\n")
            for r in rest:
                f.write(f"  - {r}\n")
        pn, _ = write_provider("GooglePlay.yaml", play)
        results.append(f"OK   {'GooglePlay.yaml':20s} {len(play):7d} rules  <- extracted from Google.yaml")
        total += len(play)
    except Exception as e:
        results.append(f"FAIL GooglePlay.yaml: {e}")

    print("\n".join(results))
    print(f"TOTAL: {total} rules across {len(SOURCES)+1} providers")

    if update_tpl:
        try:
            with open(TEMPLATE) as f:
                text = f.read()
            new_text, n = re.subn(
                r"(https://fastly\.jsdelivr\.net/gh/ipevel/clash-rulesets)@[0-9a-f]+(/clashmeta/providers/)",
                r"\1@main\2", text)
            # telegramcidr 指向新文件 TelegramCIDR.yaml
            new_text = new_text.replace(
                "clashmeta/providers/Telegram.yaml\"\n    path: ./ruleset/telegramcidr-v2.yaml",
                "clashmeta/providers/TelegramCIDR.yaml\"\n    path: ./ruleset/telegramcidr-v2.yaml")
            if n or new_text != text:
                with open(TEMPLATE, "w") as f:
                    f.write(new_text)
                print(f"template updated: {n} URLs -> @main")
            else:
                print("template already @main, no change")
        except Exception as e:
            print(f"FAIL template update: {e}")

if __name__ == "__main__":
    main()
