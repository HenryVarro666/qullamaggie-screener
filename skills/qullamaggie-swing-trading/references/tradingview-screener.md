# 没有 Deepvue？用 TradingView 替补选股（Breakout + EP）

> 💡 **已可自动化**：仓库的 `scanner/theme_scan.py` 现在内置 **TradingView 后端（`backend: tradingview`，免登录）**，
> 直接用 TradingView 公开 scan 接口自动出报告——`Volatility.M` ≈ Deepvue ADR%（实测近乎一致）。本文件是**手动版/原理版**：
> 想手点 screener、看图确认、或理解口径时读。

这份是 `screening.md` 的**纯 TradingView 版**：不用 Deepvue，用 TradingView 内置 **Stock Screener** 做"全市场粗筛"，再回到图上人工确认形态。诚实前提：**TradingView 内置 screener 不如 Deepvue 精确**——没有原生 ADR%、盘前 gap 字段受订阅档位限制、也不能像 Deepvue 那样一键按多周期涨幅排序。所以 TV 路线是 **"screener 粗筛 + 图上指标精确确认"两步走**。

> 进场/止损/止盈/仓位/市场环境判断完全沿用 `setups.md`、`risk-and-exits.md`、`tradingview-setup.md`、`SKILL.md`，本文件只补"怎么在 TV 里把候选扫出来"。

---

## 第 0 步：先过市场环境闸门
熊市/回调不扫不交易。看 QQQ/NDX 周线趋势，或挂 `assets/market-environment.pine`（绿=牛）。牛市才继续。

---

## 一、Breakout：TradingView Stock Screener 设置

打开 **Screener →（顶部）Stock**，市场选 **United States**，加以下 **Filters**：

| 方法要求 (screening.md) | TradingView Screener 字段 | 设置 |
|---|---|---|
| Price ≥ 1 | **Price** | ≥ 1 |
| 6 月涨幅 ≥ 20%（领涨） | **6-Month Performance** | ≥ 20%（想更严设 50%+） |
| 流动性（$额 ≥ 500K） | **Average Volume (30D)** + Price | 例如均量 ≥ 300K 股、且 Price≥1（两者合起来近似"够流动"；TV 没有单一'成交额'字段） |
| 只做上升趋势（Stage 2 近似） | **Simple Moving Average (200)** → 用 "Price" vs "SMA200" | Price > SMA200（粗代 30 周线之上；周线再人工确认） |

**加列**（Columns，用来排序+扫一眼）：1-Month / 3-Month / 6-Month Performance、Volatility (Month)、Average Volume、Price、Sector。

**排序**：点 **6-Month Performance** 列降序 → 取最强的一批（≈"涨幅前 1-2%"的实操做法）。也可切到 1M/3M 看近月谁在接力。

**存预设 + 出 watchlist**：右上 **Save** 存成 "Breakout"；勾选结果 → **Add to Watchlist**，进入逐只人工过滤。

### ADR% 没有原生字段——三个替代
TV screener **没有 ADR%**（方法的硬指标 ADR≥3%）。任选其一确认：
1. **图上挂 ADR 指标**（最准）：搜 `ADR (Average Daily Range)`（MikeC / TheScrutiniser 版），数值 ≥3% 才要。详见 `tradingview-setup.md`。
2. **用 screener 的 Volatility (Month) 粗筛**：把它当波动代理，过滤掉太死的票（低波动直接淘汰）。
3. **ATR/价格 近似**：`ATR(14) / 收盘 ≥ 3%`（图上 ATR 指标读数 ÷ 现价）。
> 自动忽略 ADR<3% 的票——`high ADR is Gold, low ADR is Shit`。

---

## 二、EP（事件驱动）：TradingView 怎么扫

EP 看**当日/盘前**跳空。两条路，看你的 TV 订阅：

**A. Screener 有盘前/Gap 字段时**（部分档位）：
- **Gap %** ≥ 10%（或 **Pre-market Change %** ≥ 10%）
- **Relative Volume** ≥ 1.5（放量）
- Price ≥ 1
- 加列看 1M/3M/6M Performance——确认**过去 3-6 月没大涨**（涨过了就不算"意外"）

**B. 没有可靠盘前字段时**（最稳的通用做法）：
- 盘中用 TV **Gainers**（涨幅榜）筛 Change% ≥ 10% + 放量；
- 配 TV **Earnings Calendar** 把范围缩到"今天/昨晚出财报"的票；
- 二者交集 + 前 3-6 月未大涨 = 真 EP 候选。盘前没放量的，要求**开盘 15-30 分钟内放到日均量**。

---

## 三、扫出来不等于能买：回图上人工确认（关键）
screener 只管数值，**形态必须看图**（沿用 `setups.md`）：
- **周线 Stage 2**：价在 **30 周均线**之上、30 周线上行（screener 的 SMA200 只是粗代，终判看周线）。
- **Breakout 三步形态**：大涨 → 有序回调收窄、贴升均线 → 放量突破；判断整理是**吸筹**（缩量、收区间上沿、低点抬高）而非**派发**。
- **进场/止损/止盈**：开盘区间高点 **ORH** 进；**当日低点**止损且宽度 ≤ ADR；3-5 天卖 1/3~1/2 并移保本，余仓 EMA10/20 trailing。用 **Long Position 工具**算仓位与盈亏比（`tradingview-setup.md`）。

---

## 四、半自动：用 Pine 在 watchlist 上盯 Breakout/EP
TradingView Pine **不能全市场扫**，但能对**单只图**计算条件并**报警**。把 `assets/breakout-ep-flags.pine` 贴进 Pine 编辑器，加到图上：
- 它实时算 **ADR%(20)、1M/3M/6M 涨幅、Gap%、相对量**，满足 **Breakout** 或 **EP** 条件时在图上打标记；
- 用它的 `alertcondition` 给你的 watchlist 每只票挂 **Alert**（Breakout setup / EP），命中即推送——相当于把"全市场 screener"降级成"在你关注的篮子里盯"。

> 做法：把粗筛出的 watchlist 每只都加这个指标+alert，等它通知，再回图确认形态。这就是 TV 版的"主题篮子盯盘"。

---

## 诚实边界
- TV 内置 screener **无原生 ADR%**、**盘前 gap 字段依赖订阅**、**无单一成交额字段**——本文件给的是可用替代，不是与 Deepvue 等价。
- Pine 只能逐图计算 + 报警，**不能一次性扫全市场**。
- 所有 ✓/⚡ 只是数值门槛，**Stage2 与整理/吸筹形态务必在图上终判**。不构成投资建议。
