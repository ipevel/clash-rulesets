# Karing Ruleset

Clash Meta rulesets generated from [KaringX/karing-ruleset](https://github.com/KaringX/karing-ruleset).

## Directory Structure

```
clashmeta/
├── providers/          # Individual rule provider .txt files (23 categories)
├── karing-full.clash.yaml          # Complete ruleset (111,408 rules, 4.5MB)
├── karing-selected.clash.yaml      # Selected categories only (9,501 rules, 357KB)
├── karing-ruleproviders.clash.yaml # Xboard template with rule-providers
└── karing-xboard-subscription.yaml # Full Xboard subscription template
```

## Usage

### As Xboard Template

Import `karing-xboard-subscription.yaml` into Xboard's Clash Meta subscription template system.

### As Rule Providers (CDN)

Provider files hosted via jsDelivr CDN:

```
https://fastly.jsdelivr.net/gh/ipevel/karing-ruleset@main/clashmeta/providers/Google.txt
```

### Standalone Config

Use `karing-full.clash.yaml` or `karing-selected.clash.yaml` as standalone Clash Meta config files (fill in your proxy nodes under `proxies:` section).
