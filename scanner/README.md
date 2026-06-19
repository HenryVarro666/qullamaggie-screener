# Auto-Scanner / 自动扫描器 — TradingView (no login) or Deepvue

> Automates the Qullamaggie screen and writes daily markdown reports — **Breakout (✓)** / **EP (⚡)**
> with strict Stage-2 compliance, per-stock analysis, and an **embedded TradingView daily chart** for
> every pick.
>
> 自动跑 Qullamaggie 选股口径，输出每日 markdown 报告：标记 **Breakout (✓)** / **EP (⚡)**，含严格
> Stage-2 门槛、逐只分析，且**每只选出的票都内嵌一张 TradingView 日K图**。

**Two backends — pick in `themes.json` → `_meta.backend`:**

| backend | login? | data | ADR | best for |
|--|--|--|--|--|
| **`tradingview`** (default) | ❌ none | delayed / EOD | ≈ `Volatility.M` (near-exact) | **everyone** — free, zero setup |
| `deepvue` | ✅ own paid account | real-time | exact | Deepvue users wanting real-time / pre-market EP |

> 🟢 **No account needed for the default (TradingView).** It uses TradingView's public scan
> endpoint — no login, no token. Just run it.

---

## Quick start

```bash
pip install -r ../requirements.txt
playwright install chromium                        # for the embedded TradingView chart screenshots
cp themes.example.json ~/.deepvue/themes.json      # backend already "tradingview"; edit themes / output_dir
python3 theme_scan.py
```
Reports → `_meta.output_dir` (default `~/qmag-scans/YYYY-MM-DD.md`). Charts → `<output_dir>/charts/YYYY-MM-DD/`.

*(No browser, or want it faster? `CHARTS=0 python3 theme_scan.py` skips the screenshots. The
TradingView **scan** backend itself needs no browser — chromium is only for the chart PNGs and for the
Deepvue backend.)*

### Deepvue backend (optional, own account)
Set `"backend": "deepvue"` in `themes.json`, then `pip install playwright && playwright install chromium`
and supply your session per **[AUTH_SETUP.md](AUTH_SETUP.md)**. Subject to Deepvue's Terms of Service;
personal use only, at human cadence. If the token expires it tells you to re-grab it (`update_token.py`),
or just switch back to `tradingview`.

---

## Three scanners / 三个扫描器

| command | what it gives you / 用途 |
|--|--|
| `python3 theme_scan.py` | **Theme heatmap** — scans your enabled theme baskets, flags ✓/⚡ per name, groups by theme, per-stock analysis. *"What moved in the sectors I track."* |
| `python3 ready_top10.py` | **"Buyable Top 10"** — from *all* Breakout hits keeps only **ready** setups (coiling near the 52w high, last month consolidating, liquid), ranked by readiness. One report, two sections: 🌐 whole-market + 🎯 your themes. *"What can I actually buy soon."* |
| `python3 breakout_top10.py` | **Whole-market Breakout Top-N** — every Breakout in the US market, ranked by 6M, equities only (excludes leveraged ETFs). `TOPN=25`. |

> **Why `ready_top10` exists:** ranking Breakouts by 6-month performance floats the *most extended*
> names to the top (already +70% on the month — the method says **don't chase those**). `ready_top10`
> instead surfaces names that had their move and are now **paused in a tight base near the highs**,
> about to break out. All knobs live in `_meta.ready_filter`.

Every selected stock gets an **embedded daily TradingView chart** so you can eyeball the pattern right
in the markdown (VS Code / Typora / Obsidian / GitHub all render the downward-relative image paths).
Each ticker is screenshotted **once per day and reused** across the three reports.

---

## Files
| File | What |
|--|--|
| `qmag_core.py` | Shared core: config, strict predicates (`is_breakout` / `is_ep` / `is_ready`), dual-backend fetchers (TradingView / Deepvue), per-stock `analysis()`, formatters. |
| `theme_scan.py` | Theme-grouped scan → daily report with ✓/⚡ + per-stock analysis + charts. |
| `ready_top10.py` | **"Buyable" Top-N** — ready / near-breakout filter; whole-market + your themes in one report. `TOPN=10`. |
| `breakout_top10.py` | **Whole-market** Breakout Top-N (dual backend; equities only). `TOPN=25 python3 breakout_top10.py`. |
| `charts.py` | TradingView daily-chart screenshots (Playwright). Shared by all three; `CHARTS=0` disables, `CHART_WAIT_MS` tunes render wait. |
| `themes.example.json` | Template config (backend, themes, `breakout_floors` / `ep_rules` / `ready_filter`) — copy to `~/.deepvue/themes.json`. |
| `update_token.py` | Deepvue token helper: one-command import + `--refresh`. |
| `AUTH_SETUP.md` | How to supply your own Deepvue session (Deepvue backend only). |

---

## The screen (strict mode)
- **Breakout ✓**: `price≥1` · `ADR%≥3` · `6M perf≥20%` · `20d $vol≥$1M` · still trending
  (`3M≥+5%`, `1M≥−20%`) · **within 25% of the 52-week high** · **Stage 2: above the 50- & 200-day
  MA, with 50DMA > 200DMA**. Ranked by 6-month performance.
- **EP ⚡** (财报型): `gap≥10%` · `relative volume≥1.5×` · `prior 6M ≤ 100%` · liquidity ·
  **recent earnings (≤5 trading days) + strong EPS YoY growth (≥25%)**. Set
  `ep_rules.require_earnings:false` to also include non-earnings catalysts (FDA / regulatory / macro).
- **Ready / buyable ⭐** (`ready_top10` only): a Breakout hit that is **within ~20% of its 52-week
  high**, with **last-month perf in −10%…+25%** (consolidating, not blown off) and **≥ $10M/day**
  liquidity. Ranked by **readiness = `off_high − |1M perf| + ADR × 1.5`** (near-high + tight + high-ADR
  first — *high ADR is gold*). All knobs in `_meta.ready_filter`.

> **Note — this is stricter than Qullamaggie's original Deepvue screener.** Those screenshots
> hard-filter only the **core** values (Breakout: ADR≥3%·Price≥1·Perf6M≥20%·$vol≥**500K**; EP:
> Price≥1·pre-mkt gap≥10%) and leave MA/Stage/earnings/growth as *view columns* for the eye. This
> tool promotes them to **hard gates** (matching the method's text: only Stage 2, big volume,
> earnings-driven EP) and raises liquidity to $1M (still 2× the source 500K). The **near-high +
> Stage-2** gates are what keep blown-off ex-runners (a stock spiked then −70% off its high) out of
> the list. Every threshold is tunable in `_meta.breakout_floors` / `_meta.ep_rules` /
> `_meta.ready_filter` — set them back to the screenshot values for an exact match.

## Market environment (gate #1) / 市场环境
Every report headers the Qullamaggie bull/bear regime — **QQQ EMA10/20/50 stack** (mirrors
`assets/market-environment.pine`): 🟢 bull / 🟡 pullback / 🔴 bear. It **warns** when not bullish
(the method's first gate is *only trade in a bull market*) but does **not** suppress results — you decide.
每份报告顶部给出牛/回调/熊判断（QQQ 10/20/50 均线堆叠，等价那个判断牛熊的 pine 脚本）；非牛市会提示但不屏蔽结果。

## Notes / honest limits
- TradingView backend is **delayed/EOD** (fine for after-close swing screening; intraday/pre-market
  EP is weaker than Deepvue real-time). ADR ≈ TradingView `Volatility.M` (verified near-exact).
- **Charts** are real TradingView widget screenshots (delayed/EOD, personal-use, ~4–6s each). If one
  renders blank, raise `CHART_WAIT_MS`; `CHARTS=0` disables charting entirely.
- Both endpoints are unofficial (Deepvue private API / TradingView public screener backend) — use
  reasonably, don't hammer them.
- Not financial advice. ✓/⚡/⭐ are **numeric screens only** — confirm Stage 2 and the actual
  base/consolidation on the chart before acting.
