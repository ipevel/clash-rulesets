# Clash Rulesets

Clash Meta / Mihomo 分流规则集，兼容 Xboard 等面板。

## 目录结构

```
clashmeta/
├── providers/                        # 规则 provider 文件（29个分类）
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

| Provider | 类型 | 策略 | 说明 |
|---|---|---|---|
| BanAD / BanADCompany | domain | REJECT | 广告拦截 |
| BanEasyList / BanEasyListChina / BanEasyPrivacy / BanProgramAD | domain | REJECT | 广告增强 |
| OpenAI / Claude / GoogleGemini | domain | Proxy | AI 平台 |
| ProxyMedia / TikTok / Instagram / Netflix | domain+ipcidr | Proxy | 流媒体 |
| Google / GooglePlay / GoogleFCM | domain+ipcidr | Proxy | Google |
| Apple | domain+ipcidr | Proxy | Apple |
| GitHub | domain | Proxy | GitHub |
| Bing / OneDrive / Microsoft | domain | Proxy | 微软 |
| ChinaDomain | domain | DIRECT | 国内域名 |
| ChinaIp / ChinaIpV6 / ChinaCompanyIp | ipcidr | DIRECT | 国内 IP |
| Telegram / TelegramCIDR | domain+ipcidr | Proxy | Telegram |
| ProxyGFWlist / ProxyLite / ProxyMedia | domain+ipcidr | Proxy | GFW 列表 |

## 生成与同步

- 每天 UTC 02:00：GitHub Actions 跑 `generate_providers.py` → `refactor_to_rule_set.py` → commit & push
- 本机 systemd timer 同步到 xboard 面板（见 `scripts/update_and_sync.sh`）