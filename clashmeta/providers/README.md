# Rule Providers

Individual rule files for Clash Meta rule-providers format.

## Usage

```yaml
rule-providers:
  Apple:
    type: http
    behavior: domain
    url: "https://fastly.jsdelivr.net/gh/ipevel/karing-ruleset@main/clashmeta/providers/Apple.txt"
    path: ./providers/Apple.txt
    interval: 86400
```

## Files

| File | Description | Rules |
|------|-------------|-------|
| Apple.txt | Apple services | 29 |
| BanAD.txt | Block ads | 6458 |
| BanADCompany.txt | Block ad companies | 131 |
| Bing.txt | Microsoft Bing | 3 |
| ChinaDomain.txt | China domains DIRECT | 635 |
| ChinaMedia.txt | Bilibili, video | 37 |
| Claude.txt | Claude AI | 2 |
| GitHub.txt | GitHub | 6 |
| Google.txt | Google services | 1113 |
| GoogleFCM.txt | Google FCM | 12 |
| GoogleGemini.txt | Google Gemini | 38 |
| GooglePlay.txt | Google Play | 37 |
| Instagram.txt | Instagram | 4 |
| Microsoft.txt | Microsoft services | 79 |
| NetEaseMusic.txt | NetEase Music | 37 |
| Netflix.txt | Netflix | 33 |
| OneDrive.txt | Microsoft OneDrive | 15 |
| OpenAI.txt | OpenAI / ChatGPT | 17 |
| ProxyGFWlist.txt | GFW proxy list | 6985 |
| ProxyMedia.txt | YouTube/TikTok/IG | 368 |
| Telegram.txt | Telegram | 13 |
| TikTok.txt | TikTok | 10 |
| Xbox.txt | Gaming platforms | 7 |
