# Clash Rulesets

Clash Meta / Mihomo 分流规则集，兼容 Xboard 等面板。

## 目录结构

```
clashmeta/
├── providers/                        # 规则 provider 文件（23个分类）
├── clash-full.clash.yaml            # 完整规则集
└── clash-xboard-subscription.yaml   # Xboard 订阅模板
```

## 使用方式

### Xboard 模板

在 Xboard 的 Clash Meta 订阅模板系统中导入 `clash-xboard-subscription.yaml`。

### 规则 Provider（CDN）

通过 jsDelivr CDN 托管的 provider 文件：

```
https://fastly.jsdelivr.net/gh/ipevel/clash-rulesets@main/clashmeta/providers/Google.yaml
```

### 独立配置文件

将 `clash-full.clash.yaml` 作为独立的 Clash Meta 配置文件使用（在 `proxies:` 节点处填入你的代理节点）。

## 规则集清单

> provider 的 `behavior` 必须与 payload 格式对应，写错会导致**整份远程规则零命中**：
> - `classical` → payload 是规则行且**不带策略**：`- DOMAIN-SUFFIX,example.com`
> - `domain` → payload 是裸域名（仅 ProxyLite.yaml 用它）
> - `ipcidr` → payload 是裸网段（ChinaIp / ChinaIpV6 / ChinaCompanyIp / TelegramCIDR）
>
> 策略一律由配置里的 `RULE-SET,<name>,<策略组>` 指定，payload 里不要写 `,Proxy` / `,DIRECT` / `,REJECT`。

| Provider | behavior | 说明 |
|---|---|---|
| OpenAI / Claude / GoogleGemini | classical | AI 平台 |
| ProxyMedia / TikTok / Instagram / Netflix | classical | 流媒体 |
| Google / GooglePlay / GoogleFCM | classical | Google |
| Apple | classical | Apple |
| GitHub | classical | GitHub |
| Bing / OneDrive / Microsoft | classical | 微软 |
| ChinaDomain | classical | 国内域名（已剔除误标的微软条目） |
| ChinaIp / ChinaIpV6 / ChinaCompanyIp | ipcidr | 国内 IP |
| Telegram / TelegramCIDR | classical + ipcidr | Telegram |
| ProxyGFWlist / ProxyLite / ProxyMedia | classical / domain | GFW 列表 |

广告拦截规则集已于 2026-09-20 移除，不再提供任何 REJECT 类 provider。

## 生成与同步

- 每天 UTC 02:00：GitHub Actions 跑 `generate_providers.py` → `refactor_to_rule_set.py` → commit & push
- 本机 systemd timer（`clash-rule-sync.timer`）跑 `scripts/update_and_sync.sh` 同步到 xboard 面板（内部调用 `scripts/sync_to_xboard.py` 写入面板数据库）