# Auto-Scanner / 自动扫描器 — TradingView (no login) or Deepvue

> Automates the Qullamaggie screen and writes a daily heatmap-style markdown report grouped by
> theme, flagging **Breakout (✓)** and **EP (⚡)** with strict Stage-2 compliance + per-stock analysis.
>
> 自动跑 Qullamaggie 选股口径，输出按主题分组的每日 markdown 报告，标记 **Breakout (✓)** / **EP (⚡)**，
> 含严格 Stage-2 门槛与逐只分析。

**Two backends — pick in `themes.json` → `_meta.backend`:**

| backend | login? | data | ADR | best for |
|--|--|--|--|--|
| **`tradingview`** (default) | ❌ none | delayed / EOD | ≈ `Volatility.M` (near-exact) | **everyone** — free, zero setup |
| `deepvue` | ✅ own paid account | real-time | exact | Deepvue users wanting real-time / pre-market EP |

> 🟢 **No account needed for the default (TradingView).** It uses TradingView's public scan
> endpoint — no login, no token. Just run it.

---

## Quick start (TradingView backend, default)

```bash
pip install -r ../requirements.txt
cp themes.example.json ~/.deepvue/themes.json     # backend already "tradingview"; edit themes/output_dir
python3 theme_scan.py
```
Output → `_meta.output_dir` from your `themes.json` (default `~/qmag-scans/YYYY-MM-DD.md`).
*(`playwright install chromium` is only needed for the Deepvue backend.)*

### Deepvue backend (optional, own account)
Set `"backend": "deepvue"` in `themes.json`, then `pip install playwright && playwright install chromium`
and supply your session per **[AUTH_SETUP.md](AUTH_SETUP.md)**. Subject to Deepvue's Terms of Service;
personal use only, at human cadence. If the token expires it tells you to re-grab it (or just switch
back to `tradingview`).

## Files
| File | What |
|--|--|
| `qmag_core.py` | Shared core: config, strict predicates, dual-backend fetchers (TradingView / Deepvue), formatters. |
| `theme_scan.py` | Theme-grouped scan → daily report with ✓/⚡ + per-stock analysis. |
| `breakout_top10.py` | **Whole-market** Breakout Top-N (dual backend; equities only — excludes leveraged ETFs). `TOPN=25 python3 breakout_top10.py`. |
| `themes.example.json` | Template config (backend, themes, thresholds) — copy to `~/.deepvue/themes.json`. |
| `update_token.py` | Deepvue token helper: one-command import + `--refresh`. |
| `AUTH_SETUP.md` | How to supply your own Deepvue session (Deepvue backend only). |

## The screen (strict — follows the method)
- **Breakout ✓**: `price≥1` · `ADR%≥3` · `6M perf≥20%` · `20d $vol≥$5M` · still trending
  (`3M≥+5%`, `1M≥−20%`) · **within 25% of the 52-week high** · **Stage 2: above the 50- & 200-day
  MA, with 50DMA > 200DMA**. Ranked by 6-month performance.
- **EP ⚡**: `gap≥10%` · `relative volume≥1.5×` · `prior 6M ≤ 100%` (a quiet stock surprised) ·
  liquidity. Earnings-driven is the main case, not required.

The **near-high + Stage-2** gates are what keep blown-off ex-runners (e.g. a stock spiked then
−70% off its high) out of the Breakout list. All thresholds live in `_meta.breakout_floors` /
`_meta.ep_rules`.

## Notes / honest limits
- TradingView backend is **delayed/EOD** (fine for after-close swing screening; intraday/pre-market
  EP is weaker than Deepvue real-time). ADR ≈ TradingView `Volatility.M` (verified near-exact).
- Both endpoints are unofficial (Deepvue private API / TradingView public screener backend) — use
  reasonably, don't hammer them.
- Not financial advice. ✓/⚡ are **numeric screens only** — confirm Stage 2 and the actual
  base/consolidation on the chart before acting.
