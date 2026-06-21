# Auto-Scanner / 自动扫描器 — TradingView (no login) or Deepvue

> Automates the Qullamaggie screen and writes a **single combined daily report** — **Breakout (✓)** /
> **EP (⚡)** with strict Stage-2 compliance, per-stock analysis, a **daily chart**, and a
> **formation-health** read (accumulation vs distribution) on every pick.
>
> 自动跑 Qullamaggie 选股口径，输出**一份合并日报**：标记 **Breakout (✓)** / **EP (⚡)**，含严格 Stage-2
> 门槛、逐只分析、日K图、以及**形态健康度**（吸筹 vs 派发）判断。

**Two backends — pick in `themes.json` → `_meta.backend`:**

| backend | login? | data | ADR | best for |
|--|--|--|--|--|
| **`tradingview`** (default) | ❌ none | delayed / EOD | ≈ `Volatility.M` (near-exact) | **everyone** — free, zero setup |
| `deepvue` | ✅ own paid account | real-time | exact | Deepvue users wanting real-time / pre-market EP |

> 🟢 **No account needed for the default (TradingView) scan.** Public scan endpoint — no login, no token.

---

## Quick start

```bash
pip install -r ../requirements.txt              # requests + playwright + mplfinance
cp themes.example.json ~/.deepvue/themes.json   # backend already "tradingview"; edit themes / output_dir
python3 daily.py                                # ⭐ one combined daily report
```
`daily.py` writes **one** `<output_dir>/YYYY-MM-DD.md`: market regime → table-of-contents → **theme
heatmap** → **buyable Top 10** → **whole-market Breakout Top-N**, every hit with a chart + a
**formation-health** line. Charts → `<output_dir>/charts/YYYY-MM-DD/`.

*(Faster / no charts: `CHARTS=0 python3 daily.py`. The TradingView **scan** backend needs no browser —
chromium is only for chart screenshots and the Deepvue backend.)*

### Deepvue backend (optional, own account)
Set `"backend": "deepvue"` in `themes.json`, then `playwright install chromium` and supply your session
per **[AUTH_SETUP.md](AUTH_SETUP.md)**. Subject to Deepvue's ToS; personal use only, human cadence. If
the token expires it tells you to re-grab it (`update_token.py`), or just switch back to `tradingview`.

---

## Commands / 命令

| command | what it gives you / 用途 |
|--|--|
| **`python3 daily.py`** ⭐ | **One combined daily report** — regime + TOC + theme heatmap + buyable Top 10 + whole-market Top-N, every hit with chart + formation health. **Run this daily.** |
| `python3 theme_scan.py` | Single view: theme heatmap (→ `theme-*.md`). |
| `python3 ready_top10.py` | Single view: **"Buyable Top 10"** — Breakouts coiling near highs, ready to go (whole-market + your themes). `TOPN=10`. |
| `python3 breakout_top10.py` | Single view: whole-market Breakout Top-N, equities only. `TOPN=25`. |

> **Why "buyable" ≠ top gainers:** ranking Breakouts by 6-month performance floats the *most extended*
> names to the top (already +70% on the month — the method says **don't chase those**). The buyable
> filter instead surfaces names that had their move and are now **paused in a tight base near the
> highs**, about to break out. Knobs in `_meta.ready_filter`.

---

## Charts & formation health / 图表与形态

**Charts** — two modes, auto-selected, embedded per hit (paths render in VS Code / Typora / Obsidian /
GitHub; each ticker drawn once per day and reused):
- **Real TradingView screenshot, with *your own* indicators** — drop a logged-in **`tv_cookies.json`**
  (your browser's TradingView cookies, e.g. `sessionid`) in the scanner dir; it screenshots *your* chart
  layout (your indicators, your colors). **git-ignored, never committed.** Slower (~8s/chart).
- **mplfinance self-draw (default fallback)** — no login; candles + volume + colored MAs
  (`_meta.chart_ma`, default EMA10/EMA21/SMA50/SMA200). Fast. Used automatically when there's no
  `tv_cookies.json`, or with `CHART_MODE=mpl`.

**Formation health** (`daily.py`) — automates *"healthy tightening base, or distribution?"*:
- **Numeric**: volume contraction (TradingView avg-vol) + range tightening / higher-lows / closing
  strength / distribution-days (Yahoo daily bars) → 🟢 accumulation / 🟡 neutral / 🔴 distribution-risk.
- **Optional AI vision**: feeds the chart to **Gemini** for a second read. Needs `GEMINI_API_KEY` (or a
  git-ignored `secrets.json` with `gemini_api_key`); without it you get the numeric verdict only.
  `HEALTH=0` disables, `VISION=0` keeps numeric only. Model + thresholds in `_meta.health`.

---

## Files
| File | What |
|--|--|
| `daily.py` | ⭐ **Combined daily report** (regime + TOC + theme heatmap + buyable Top10 + whole-market Top-N; charts + formation health). |
| `qmag_core.py` | Shared core: config, predicates (`is_breakout`/`is_ep`/`is_ready`), dual-backend fetchers, per-stock `analysis()`, formatters. |
| `theme_scan.py` · `ready_top10.py` · `breakout_top10.py` | Single-view reports (theme heatmap / buyable Top10 / whole-market Top-N). |
| `charts.py` | Daily charts: real TradingView login-screenshot (your indicators; needs `tv_cookies.json`) or mplfinance self-draw fallback. `CHARTS=0` / `CHART_MODE=mpl`. |
| `health.py` | Formation health: numeric (TV vol + Yahoo bars) + optional Gemini vision. `HEALTH=0` / `VISION=0`. |
| `themes.example.json` | Template config (backend, themes, `breakout_floors`/`ep_rules`/`ready_filter`/`health`/`chart_ma`) — copy to `~/.deepvue/themes.json`. |
| `update_token.py` · `AUTH_SETUP.md` | Deepvue token helper + auth setup (Deepvue backend only). |

> **Credentials never get committed.** `tv_cookies.json` (TradingView login), `secrets.json` (Gemini
> key), and Deepvue `cookies.json`/`tokens.json` live locally and are git-ignored.

---

## The screen (strict mode)
- **Breakout ✓**: `price≥1` · `ADR%≥3` · `6M perf≥20%` · `20d $vol≥$1M` · still trending
  (`3M≥+5%`, `1M≥−20%`) · **within 25% of the 52-week high** · **Stage 2: above the 50- & 200-day
  MA, with 50DMA > 200DMA**. Ranked by 6-month performance.
- **EP ⚡** (财报型): `gap≥10%` · `relative volume≥1.5×` · `prior 6M ≤ 100%` · liquidity ·
  **recent earnings (≤5 trading days) + strong EPS YoY growth (≥25%)**. Set
  `ep_rules.require_earnings:false` to also include non-earnings catalysts (FDA / regulatory / macro).
- **Ready / buyable ⭐** (`ready_top10` / `daily.py`): a Breakout hit **within ~20% of its 52-week
  high**, **last-month perf in −10%…+25%** (consolidating, not blown off), **≥ $5M/day** liquidity
  (a universal "real names" gate — not tied to your account size; quality comes from ADR/Stage2/base).
  Ranked by **readiness = `off_high − |1M perf| + ADR × 1.5`** (*high ADR is gold*). Knobs in `_meta.ready_filter`.

> **Note — stricter than Qullamaggie's original Deepvue screener.** Those screenshots hard-filter only
> the **core** values (Breakout: ADR≥3%·Price≥1·Perf6M≥20%·$vol≥**500K**; EP: Price≥1·pre-mkt gap≥10%)
> and leave MA/Stage/earnings/growth as *view columns*. This tool promotes them to **hard gates**
> (matching the method's text) and raises liquidity to $1M. The **near-high + Stage-2** gates keep
> blown-off ex-runners out. Every threshold is tunable in `_meta.breakout_floors` / `_meta.ep_rules` /
> `_meta.ready_filter` — set them back to the screenshot values for an exact match.

## Market environment (gate #1) / 市场环境
Every report headers the Qullamaggie bull/bear regime — **QQQ EMA10/20/50 stack** (mirrors
`assets/market-environment.pine`): 🟢 bull / 🟡 pullback / 🔴 bear. It **warns** when not bullish but
does **not** suppress results — you decide.

## Notes / honest limits
- TradingView backend is **delayed/EOD** (fine for after-close swing screening; intraday/pre-market EP
  weaker than Deepvue real-time). ADR ≈ TradingView `Volatility.M`.
- **Charts/health/AI are aids, not verdicts.** ✓/⚡/⭐ and the health read are screens — confirm the
  actual base/consolidation on the chart before acting.
- Both endpoints are unofficial (Deepvue private API / TradingView public screener) and the TV
  login-screenshot drives **your own** session — use reasonably, personal-use, don't hammer them.
- Not financial advice.
