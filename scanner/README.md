# Deepvue Auto-Scanner / Deepvue 自动扫描器

> **Optional / advanced.** Automates the Qullamaggie screen against the live Deepvue screener
> and writes a daily heatmap-style markdown report grouped by theme, flagging **Breakout (✓)**
> and **EP (⚡)** setups with per-stock analysis.
>
> **可选/进阶。** 对接 Deepvue 实时选股器自动跑 Qullamaggie 选股口径，输出按主题分组的每日
> markdown 报告，标记 **Breakout (✓)** 与 **EP (⚡)**，每只附分析。

⚠️ **Requires your own paid Deepvue account.** Deepvue has no public API — this drives your own
logged-in session. See **[AUTH_SETUP.md](AUTH_SETUP.md)** first. Subject to Deepvue's Terms of
Service; for personal use only, at human cadence. Don't redistribute Deepvue's data.

> 🟢 No Deepvue account? **Skip this whole folder** and use the **TradingView fallback** instead:
> [`skills/qullamaggie-swing-trading/references/tradingview-screener.md`](../skills/qullamaggie-swing-trading/references/tradingview-screener.md).

---

## Files

| File | What |
|--|--|
| `theme_scan.py` | Main. Scans the tickers in your enabled themes, flags ✓/⚡, writes the daily report. |
| `breakout_top10.py` | Whole-market (≈13k symbols) Breakout Top-10, console output. |
| `themes.example.json` | Template theme config — copy to `~/.deepvue/themes.json` and edit. |
| `AUTH_SETUP.md` | How to supply your own Deepvue session. |

## Quick start

```bash
pip install -r ../requirements.txt
playwright install chromium
# one-time: set up ~/.deepvue/ per AUTH_SETUP.md, then:
cp themes.example.json ~/.deepvue/themes.json   # edit as you like
python3 theme_scan.py
```
Output → `_meta.output_dir` from your `themes.json` (default `~/qmag-scans/YYYY-MM-DD.md`).

## How the screen maps to the method

- **Breakout ✓**: `price ≥ 1` · `ADR% ≥ 3` · `6-month perf ≥ 20%` · `20-day $vol ≥ 500K` ·
  still trending (`3M ≥ +5%`, `1M ≥ −20%`). Ranked by 6-month performance.
- **EP ⚡**: `gap ≥ 10%` · `relative volume ≥ 1.5×` · `prior 6-month perf ≤ 100%` (a quiet stock
  surprised) · basic liquidity. Earnings-driven is the main case but not required.

All thresholds live in `_meta.breakout_floors` / `_meta.ep_rules` — tune them in `themes.json`.

## How it works (for the curious)

Deepvue's screener streams over a WebSocket (`wss://lightserver.deepvue.com/ws-data`). The
script refreshes your access token, opens that socket with your session (subprotocol auth),
requests the column data for your themes' tickers, then filters/ranks locally. No Deepvue
server-side filter is reverse-engineered beyond fetching the columns your account can already
see in the UI.

## Disclaimers

Not financial advice. Data is only as good as Deepvue's feed. ✓/⚡ are numeric screens only —
**confirm Stage 2 and the actual base/consolidation on the chart in TradingView before acting.**
