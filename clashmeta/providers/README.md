# Rule Providers

Rule provider files for Clash Meta / Mihomo（`behavior: classical`）。

## Format

绝大多数 provider 使用 `classical`：**每行是一条完整规则，但不带策略字段**。

```yaml
payload:
  - DOMAIN-SUFFIX,apple.com
  - DOMAIN-KEYWORD,google
  - IP-CIDR,91.108.0.0/16,no-resolve
```

策略由配置里的 `RULE-SET,<provider名>,<策略组>` 决定。

⚠️ 不要在 payload 里写 `,Proxy` / `,DIRECT` / `,REJECT`。早期版本生成时带了策略后缀，
配合 `behavior: domain` 会让内核把整行当成域名插入 trie，导致**所有远程规则零命中**
（微软 / Google / GFWlist 分流全部失效）。现已统一改为 `classical`。

例外：`ProxyLite.yaml` 是裸域名/关键词列表 → `behavior: domain`；
`ChinaIp.yaml` / `ChinaIpV6.yaml` / `ChinaCompanyIp.yaml` / `TelegramCIDR.yaml` 是裸网段 → `behavior: ipcidr`。

## Usage

```yaml
rule-providers:
  Apple:
    type: http
    behavior: classical
    url: "https://fastly.jsdelivr.net/gh/ipevel/clash-rulesets@main/clashmeta/providers/Apple.yaml"
    path: ./providers/Apple.yaml
    interval: 86400
```

## Files

| File | behavior | Description | Rules |
|------|----------|-------------|-------|
| Apple.yaml | classical | Apple services | 33 |
| Bing.yaml | classical | Microsoft Bing | 9 |
| ChinaCompanyIp.yaml | ipcidr | China company CIDR (DIRECT) | 208 |
| ChinaDomain.yaml | classical | China domains (DIRECT, 微软条目已剔除) | 3673 |
| ChinaIp.yaml | ipcidr | China IPv4 CIDR (DIRECT) | 9741 |
| ChinaIpV6.yaml | ipcidr | China IPv6 CIDR (DIRECT) | 1502 |
| Claude.yaml | classical | Claude AI | 3 |
| GitHub.yaml | classical | GitHub | 31 |
| Google.yaml | classical | Google services | 694 |
| GoogleFCM.yaml | classical | Google FCM | 41 |
| GoogleGemini.yaml | classical | Google Gemini | 13 |
| GooglePlay.yaml | classical | Google Play | 2 |
| Instagram.yaml | classical | Instagram | 4 |
| Microsoft.yaml | classical | Microsoft services | 670 |
| Netflix.yaml | classical | Netflix | 38 |
| OneDrive.yaml | classical | Microsoft OneDrive / SharePoint | 18 |
| OpenAI.yaml | classical | OpenAI / ChatGPT | 35 |
| ProxyGFWlist.yaml | classical | GFW proxy list | 4384 |
| ProxyLite.yaml | domain | Lightweight proxy list (bare keywords) | 329 |
| ProxyMedia.yaml | classical | YouTube / TikTok / IG | 183 |
| Telegram.yaml | classical | Telegram | 46 |
| TelegramCIDR.yaml | ipcidr | Telegram CIDR | 12 |
| TikTok.yaml | classical | TikTok | 32 |
