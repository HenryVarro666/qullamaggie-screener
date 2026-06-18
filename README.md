# Qullamaggie Screener & Skill

**A Qullamaggie (Kristjan Kullamägi) swing-trading toolkit** — a Claude Code *skill* that
coaches the method on TradingView, plus an optional auto-scanner that builds a daily
**Breakout / EP** watchlist. Works with or without Deepvue.

**Qullamaggie 趋势交易工具箱** —— 一个在 TradingView 上执行该方法的 Claude Code *skill*，外加一个
可选的自动扫描器，每天产出 **Breakout / EP** 候选清单。**有没有 Deepvue 都能用。**

> ⚠️ **Not financial advice / 非投资建议.** Educational & personal-research use only. Trading
> involves risk of loss. The method is Kristjan Kullamägi's; this repo just helps you execute it.

---

## What's inside / 仓库内容

| Path | What it is |
|--|--|
| `skills/qullamaggie-swing-trading/` | The **Claude Code skill** — method, screening, entry/stop/exit, risk sizing, market-environment gating. Chinese. |
| `skills/.../references/tradingview-screener.md` | **No-Deepvue TradingView fallback** — how to screen Breakout/EP in TradingView's built-in screener. |
| `skills/.../assets/*.pine` | TradingView Pine: market-environment regime + a Breakout/EP flag-and-alert helper. |
| `scanner/` | **Optional** Deepvue auto-scanner (needs your own paid account). Daily theme-grouped report. |

---

## Three ways to use it / 三种用法

### A. As a Claude Code skill (everyone) / 当 Claude Code 陪练（人人可用）
Install the skill, then ask Claude things like *"NVDA 现在算不算 breakout？在哪进场、止损放哪？"*
or *"现在大盘能不能交易？"* — it answers strictly from the method.

**Install / 安装:**
```bash
git clone https://github.com/HenryVarro666/qullamaggie-screener.git
# copy the skill into your Claude Code skills dir:
cp -R qullamaggie-screener/skills/qullamaggie-swing-trading ~/.claude/skills/
```
Or use it as a plugin (the repo ships a `.claude-plugin/plugin.json`). Manual copy above is the
reliable path.

### B. No Deepvue? Use the TradingView fallback (everyone) / 没有 Deepvue 走 TradingView
Follow **[`tradingview-screener.md`](skills/qullamaggie-swing-trading/references/tradingview-screener.md)**:
build the Breakout/EP screen in TradingView's built-in Stock Screener, confirm the base on the
chart, and (optionally) load `assets/breakout-ep-flags.pine` to get per-symbol alerts.
没有 Deepvue 的人**从这条开始**。

### C. Deepvue auto-scanner (own account) / Deepvue 自动扫描（需自备账号）
Automates the whole screen and writes a daily heatmap-style markdown report grouped by theme,
with **Breakout ✓ / EP ⚡** flags and per-stock analysis. See **[`scanner/README.md`](scanner/README.md)**
and **[`scanner/AUTH_SETUP.md`](scanner/AUTH_SETUP.md)**.
```bash
pip install -r requirements.txt && playwright install chromium
# set up ~/.deepvue/ per AUTH_SETUP.md, then:
python3 scanner/theme_scan.py
```
⚠️ Deepvue has no public API; this drives **your own** logged-in session and is subject to
**Deepvue's Terms of Service**. Personal use only, human cadence, don't redistribute its data.
Deepvue 扫描器逆向其付费私有接口，**仅供你自己付费账号自用**、遵守其服务条款、勿高频滥用。

---

## The method in one screen / 一屏看懂口径

- **Breakout ✓**: big prior move → orderly tightening pullback hugging rising MAs → volume
  breakout. Screen ≈ `price≥1 · ADR%≥3 · 6M perf≥20% · 20d $vol≥500K · still trending`.
- **EP ⚡** (Episodic Pivot): surprise catalyst gap on a quiet stock. Screen ≈ `gap≥10% ·
  rel-vol≥1.5 · prior 6M not already run`. Earnings is the main case, not the only one.
- **Entry** = open-range high (ORH). **Stop** = day's low, width ≤ ADR. **Exit** = sell ⅓–½ in
  3–5 days + move stop to breakeven, trail the rest on EMA10/20. Risk ≤ 0.5% of account per trade.
- Only in a **bull market** (QQQ/NDX weekly), only **hot themes**, only **Stage 2** leaders.

Full detail lives in the skill's `references/`.

---

## Disclaimers / 免责

- **Not financial advice.** For education and personal research only.
- **Deepvue scanner** requires your own **paid** account and respects Deepvue's ToS. No
  credentials are included in this repo (they live locally and are git-ignored).
- ✓/⚡ are **numeric screens only** — always confirm Stage 2 and the actual base/consolidation
  on the chart before acting.
- Data is only as good as its source.

## Credits / 致谢
Method by **Kristjan "Qullamaggie" Kullamägi** (qullamaggie.com). Packaged by
[@HenryVarro666](https://github.com/HenryVarro666). MIT licensed.
