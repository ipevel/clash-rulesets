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
# polaris-rules 合并后的 AI 清单（ACL4SSR 的 AI/OpenAi/ClaudeAI/Gemini 四份合并去重），
# 覆盖 OpenAI / Claude / Gemini / Groq / Perplexity / Mistral / Meta AI / xAI / Cursor /
# JetBrains / GitHub·Microsoft Copilot 等，比本仓原本只拉 OpenAI/Claude/Gemini 三份更全。
POLARIS_AI = "https://raw.githubusercontent.com/ipevel/polaris-rules/main/dist/rules/ai.list"
UA = {"User-Agent": "Mozilla/5.0 (clash-rulesets-updater)"}

# 规则类型前缀（标准 Clash 规则行）
RULE_TYPES = ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-REGEX",
              "IP-CIDR", "IP-CIDR6", "IP-ASN", "GEOIP", "GEOSITE",
              "PROCESS-NAME", "MATCH", "RULE-SET", "SRC-IP-CIDR", "DST-PORT")

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", "replace")

def parse_list(text):
    """提取纯文本规则列表（每行一条，无 payload: 包裹）。

    polaris-rules 的 dist/rules/*.list 就是这种格式：一行一条 Clash 规则行。
    """
    items = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        items.append(s)
    return items

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
    """
    把条目转成 rule-provider 用的规则行。

    重要: 本仓库 domain 类 provider 的 behavior 均为 **classical**，payload 必须是
    规则行且**不带策略字段**（如 'DOMAIN-SUFFIX,example.com'）；策略由配置里的
    'RULE-SET,<name>,<策略组>' 决定。

    历史上这里会追加 ',Proxy' / ',REJECT'，导致 behavior:domain 下整行被当成域名
    插入 trie，所有远程规则集零命中（微软/Google/GFWlist 分流全部失效）。已修正。
    """
    kind = kind or classify(item)
    if kind == "rule":
        parts = [p.strip() for p in item.split(",")]
        rtype = parts[0].upper()
        if rtype in ("IP-CIDR", "IP-CIDR6", "IP-ASN"):
            return item  # ipcidr 走 cidr 分支输出裸网段，规则行形式原样保留
        # 剥离历史遗留的策略字段
        if len(parts) >= 3 and parts[-1] in ("Proxy", "DIRECT", "REJECT", "NO-DIRECT"):
            return ",".join(parts[:-1])
        return item
    if kind == "bare":
        # 裸域名 -> DOMAIN（精确匹配）
        return f"DOMAIN,{item}"
    if kind == "adguard":
        # +.domain -> DOMAIN-SUFFIX
        dom = item.lstrip("+.'\"").strip()
        return f"DOMAIN-SUFFIX,{dom}"
    if kind == "cidr":
        # 纯 IP 段输出（供 behavior: ipcidr 的 rule-provider 使用，不带规则前缀/策略）
        if "/" in item:
            return item
        return f"{item}/32"
    return None

# blackmatrix7 的 China_Domain 把一批微软域名标成「国内直连」，实际在国内访问不通，
# 会直接搞挂 Outlook / Office365 / Microsoft Store / Windows Update / Xbox。
# 这些域名应由 Microsoft.yaml / OneDrive.yaml（走代理）接管。
MS_DIRECT_DROP_DOMAIN = {
    "DOMAIN,download.microsoft.com",
    "DOMAIN,ntservicepack.microsoft.com",
}
MS_DIRECT_DROP_SUFFIX = {
    "dl.delivery.mp.microsoft.com",
    "hotmail.com",
    "microsoftonline.com",
    "office.com",
    "office.net",
    "office365.com",
    "outlook.com",
    "s-microsoft.com",
    "sharepoint.com",
    "update.microsoft.com",
    "windows.com",
    "windows.net",
    "windowsupdate.com",
    "windowsupdate.microsoft.com",
    "xbox.com",
    "xboxlive.com",
}


def drop_microsoft_direct(rules):
    """从国内直连列表里剔除微软条目（精确值匹配，不误伤 chinalive.com 等）。"""
    out = []
    for r in rules:
        parts = [p.strip() for p in r.split(",")]
        if len(parts) >= 2:
            if r in MS_DIRECT_DROP_DOMAIN:
                continue
            if parts[0].upper() == "DOMAIN-SUFFIX" and parts[1] in MS_DIRECT_DROP_SUFFIX:
                continue
        out.append(r)
    return out


def filter_cn_proxy(rules):
    """Proxy 策略的规则剔除 .cn 域名（防止国内服务误走代理）。"""
    out = []
    for r in rules:
        if (r.startswith("DOMAIN-SUFFIX,") or r.startswith("DOMAIN,")) and r.lower().rstrip().endswith(".cn"):
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

# AI 服务普遍依赖的第三方基础设施（登录/支付/人机验证/统计/客服/证书）。
# 这些域名被 ACL4SSR 和 blackmatrix7 打进了 AI 清单，但它们服务的是**全网大量与 AI 无关的站点**
# （Intercom 客服挂在无数网站上、Cloudflare Turnstile、Sentry、Stripe 支付……）。
# 留在 AI 规则里会劫持非 AI 站点流量，且由于 AI 分组排在靠前位置，还会压过国内直连/GFW 兜底。
# 2026-10-19 用户裁定：生成阶段统一剔除。
AI_INFRA_DROP = {
    "auth0.com",                     # 登录
    "client-api.arkoselabs.com",     # Arkose 人机验证（多家站点共用）
    "events.statsigapi.net",         # Statsig 埋点
    "featuregates.org",              # 功能开关
    "identrust.com",                 # 证书校验
    "intercom.io",                   # 客服组件（挂在无数网站）
    "intercomcdn.com",               # 客服组件 CDN
    "challenges.cloudflare.com",     # Cloudflare Turnstile 人机验证
    "sentry.io",                     # 错误上报
    "stripe.com",                    # 支付
}

# 需要套用 AI_INFRA_DROP 的产出文件（4 条 AI 产线）
AI_PROVIDERS = {"OpenAI.yaml", "Claude.yaml", "GoogleGemini.yaml", "AI.yaml"}

def drop_ai_infra(rules):
    """剔除 AI 清单里的第三方基础设施域名。

    规则行形如 'DOMAIN-SUFFIX,auth0.com'，取第 2 段（域名）比对忽略大小写。
    """
    out = []
    for r in rules:
        parts = r.split(",")
        val = parts[1].strip().lower() if len(parts) >= 2 else r.strip().lower()
        if val in AI_INFRA_DROP:
            continue
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
    # --- AI ---
    (BM7.format(cat="OpenAI", file="OpenAI.yaml"), "OpenAI.yaml",       "Proxy", "rule", True),
    (BM7.format(cat="Claude", file="Claude.yaml"), "Claude.yaml",       "Proxy", "rule", True),
    (BM7.format(cat="Gemini", file="Gemini.yaml"), "GoogleGemini.yaml", "Proxy", "rule", True),
    # 合并 AI 清单（来自 polaris-rules），作为 AI 平台的兜底：单条 RULE-SET 覆盖全部 AI 服务。
    (POLARIS_AI, "AI.yaml", "Proxy", "list", True),
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
    # --- 国内 ---
    (BM7.format(cat="China",        file="China_Domain.yaml"), "ChinaDomain.yaml",  "DIRECT", "auto", False),
    (LOYO.format(file="cncidr.txt"), "ChinaIp.yaml", "DIRECT", "cidr", False),
    # --- Telegram / GFW ---
    (BM7.format(cat="Telegram", file="Telegram.yaml"), "Telegram.yaml", "Proxy", "rule", True),
    (LOYO.format(file="gfw.txt"),           "ProxyGFWlist.yaml", "Proxy", "adguard", True),
    (LOYO.format(file="telegramcidr.txt"),  "TelegramCIDR.yaml", "Proxy", "cidr",    False),
]

# 合并源：把多个上游分类合并成一个 provider（去重），对应订阅模板里的合并分组。
# 2026-10-19 用户要求社交/流媒体/开发者各自并成一个分组；用合并 provider 可以避免
# 模板里堆十几个 rule-provider 块，也少几次客户端 CDN 拉取。
# 结构：(输出文件名, [(blackmatrix7 分类, 该分类文件名), ...])
MERGED_SOURCES = [
    ("Social.yaml", [
        ("Twitter",  "Twitter.yaml"),
        ("Facebook", "Facebook.yaml"),
        ("Whatsapp", "Whatsapp.yaml"),
        ("Discord",  "Discord.yaml"),
        ("Reddit",   "Reddit.yaml"),
    ]),
    ("Streaming.yaml", [
        ("Disney",     "Disney.yaml"),
        ("HBO",        "HBO.yaml"),
        ("PrimeVideo", "PrimeVideo.yaml"),
        ("Twitch",     "Twitch.yaml"),
        ("Spotify",    "Spotify.yaml"),
    ]),
    ("Dev.yaml", [
        ("GitLab", "GitLab.yaml"),
        ("Docker", "Docker.yaml"),
        ("Npmjs",  "Npmjs.yaml"),
        ("Python", "Python.yaml"),
    ]),
]

def main():
    update_tpl = "--update-template" in sys.argv
    results = []
    total = 0
    for url, out, policy, fmt, filter_cn in SOURCES:
        try:
            text = fetch(url)
            if fmt == "list":
                items = parse_list(text)
            else:
                items = parse_payload(text)
            rules = []
            for it in items:
                if fmt in ("rule", "list"):
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
            if out == "ChinaDomain.yaml":
                rules = drop_microsoft_direct(rules)
            if out in AI_PROVIDERS:
                rules = drop_ai_infra(rules)
            rules = dedup(rules)
            if not rules:
                raise RuntimeError("empty rules")
            path, n = write_provider(out, rules)
            src = url.split("/")[-1]
            results.append(f"OK   {out:20s} {n:7d} rules  <- {src}")
            total += n
        except Exception as e:
            results.append(f"FAIL {out:20s} {url}: {e}")

    # --- 合并源：多个上游分类合成一个 provider ---
    for out, cats in MERGED_SOURCES:
        try:
            rules = []
            used = []
            for cat, fname in cats:
                url = BM7.format(cat=cat, file=fname)
                items = parse_payload(fetch(url))
                got = []
                for it in items:
                    r = to_rule(it, "Proxy", "rule")
                    if r:
                        got.append(r)
                got = filter_cn_proxy(got)
                rules.extend(got)
                used.append(f"{cat}({len(got)})")
            rules = dedup(rules)
            if not rules:
                raise RuntimeError("empty rules")
            path, n = write_provider(out, rules)
            results.append(f"OK   {out:20s} {n:7d} rules  <- merged {' + '.join(used)}")
            total += n
        except Exception as e:
            results.append(f"FAIL {out:20s} {e}")

    # --- GooglePlay 从 Google.yaml 提取 ---
    try:
        google_rules = []
        gpath = os.path.join(PROVIDER_DIR, "Google.yaml")
        if os.path.exists(gpath):
            with open(gpath) as f:
                for line in f:
                    if line.startswith("  - DOMAIN") or line.startswith("  - PROCESS"):
                        google_rules.append(line.strip()[2:])
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
    if any(r.startswith("FAIL") for r in results):
        sys.exit(1)

    if update_tpl:
        try:
            with open(TEMPLATE) as f:
                text = f.read()
            new_text, n = re.subn(
                r"(https://cdn\.jsdelivr\.net/gh/ipevel/clash-rulesets)@[0-9a-f]+(/clashmeta/providers/)",
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
