# 选股：如何扫出 Setup（Deepvue 为主，TradingView 映射）

来源：群内培训《趋势交易基础》里的两张选股器截图（Deepvue 风格）+ Qullamaggie 方法论。这一步回答的是"**怎么从几千只票里找到值得看的那几只**"——扫出来只是候选，最终能不能买仍要回到 `setups.md` 套形态、回到 `risk-and-exits.md` 算仓位。

> 截图原件：`assets/screeners/breakout-screener.png`（Breakout）、`assets/screeners/ep-screener.png`（EP）。照着在 Deepvue 里把 filter 摆成一样即可。

## 选股总流程（每天/盘前固定动作）

1. **先过市场环境闸门**——熊市/恐慌期不扫不交易（见 `SKILL.md` "打顺风局" + Market Environment 指标）。
2. **锁定热门主题**——看哪个板块在放量领涨（"嘴会骗人，钱不会"）。
3. **跑选股器**——Breakout 和 EP 各一套 filter（见下），得到原始候选。
4. **人工过滤**——逐只上 TradingView：周线确认 **Stage 2**、日线确认形态（整理是吸筹还是派发、是否贴均线收窄），筛掉不合格的。
5. **建 watchlist + 设 alert**——把幸存者放进 watchlist，画 PDH，挂突破 alert（衔接 `tradingview-setup.md`）。

选股器负责"广撒网把烂票滤掉"，**真正的判断在第 4 步人工过滤**。不要扫出来就买。

---

## Breakout 选股器 · Deepvue 精确设置

对应 `assets/screeners/breakout-screener.png`。白色高亮 = 已设阈值的**硬过滤**；深色 = 仅加进来当**排序/查看列**（不设阈值，用来人工排序和扫一眼）。

**硬过滤（必须满足）：**
- **Region = US**（只做美股）
- **ADR ≥ 3%**——铁律红线，`high ADR is Gold, low ADR is Shit`。
- **Price ≥ 1 USD**——剔除仙股。
- **Perf 6M ≥ 20%**——半年涨幅打底，保证是"正在领涨"的强势股；这是对"扫 1/3/6 月涨幅前 1-2%"的可操作近似。
- **Price × avg vol 30D ≥ 500K USD**——30 日日均成交额 ≥ 50 万美元，保证流动性（把"放量"和"能进得去出得来"量化）。

**排序/查看列（不设阈值）：** Watchlist、EMA、Avg vol、Perf %、Price、RSI、SMA、SMA、Sector、EPS dil growth。

**用法：** 跑完后按 **Perf %（1M/3M/6M）降序**排，取最强的一批；这就是"当下涨幅排前 1-2%"的实操做法。再逐只去人工过滤（Stage 2 + 整理形态）。

> 注意 EMA/SMA 列：把 9/21/50 均线放进来一眼看价格是否"贴"着上升均线（Breakout 形态第 2 步）。

---

## EP 选股器 · Deepvue 精确设置

对应 `assets/screeners/ep-screener.png`。EP 是事件驱动，**主用盘前/盘后**扫，关键是抓"意外利好 + 跳空 + 放量"。

**硬过滤（必须满足）：**
- **Region = US**
- **Price ≥ 1 USD**
- **Pre-mkt gap ≥ 10%**——盘前跳空 ≥ 10%，这是 EP 的硬门槛（量化了"跳空 ≥ 10%"）。

**排序/查看列（不设阈值，但这是 EP 选股的灵魂）：**
- **Recent earnings date / Upcoming earnings date**——锁定财报型 EP；财报当天/次日跳空的最优先。
- **EPS dil growth / Revenue growth**——确认"强劲增长"：EPS 与营收中/高双位甚至三位数增长、显著超预期。
- **Pre-mkt chg % / Chg %**——盘前/盘中涨幅，配合 gap 看强度。
- 其余参考列：Index、Mkt cap、P/E、Div yield %、Sector、Analyst rating、Perf %、PEG、ROE、Beta。

**用法：** 盘前用 `Pre-mkt gap ≥ 10%` 拉出今日跳空票 → 看哪些是财报驱动（earnings date 命中）+ 增长强劲（EPS/Revenue growth 高）→ 再确认**过去 3-6 个月没怎么涨过**（涨过了就不算"意外"，用 Perf % 列判断）→ 开盘看是否放量、走 ORH 进场。盘前没放量的，要求开盘 15-30 分钟内成交到日均量级。

---

## TradingView 内置 Stock Screener 映射

没有 Deepvue 时，用 TradingView 的 Stock Screener（Screener → Stock）尽量复刻。**TV 内置 screener 字段不如 Deepvue 全，下面是对应关系与替代方案：**

| Deepvue filter | TradingView Screener 字段 | 备注 / 替代 |
|---|---|---|
| Region = US | Market: United States | 顶部市场选 US |
| Price ≥ 1 USD | Price ≥ 1 | 直接有 |
| Perf 6M ≥ 20% | "6-Month Performance" ≥ 20% | 直接有；也可加 1M/3M Performance 列排序 |
| Price × avg vol 30D ≥ 500K | 无原生字段 → 用 **"Average Volume (30D)"** 或自己估算 | 近似：Average Volume(30) × 现价 ≥ 500K；或直接用 "Value Traded" 类字段 |
| **ADR ≥ 3%** | **无原生 ADR%** | TV screener 没有 ADR。替代：① 用 "Volatility" / ATR 字段粗筛；② 真正确认靠图上的 **ADR 指标**（见 `tradingview-setup.md`），或用 `ATR/收盘价 ≥ 3%` 近似 |
| Pre-mkt gap ≥ 10% | "Pre-market Change %" / "Gap %" | TV 盘前字段覆盖有限、依赖订阅档位；不全时改用盘前涨幅榜 + 财报日历人工找 |
| EPS dil growth / Revenue growth | "EPS Diluted Growth"、"Revenue Growth" | 直接有 |
| Recent/Upcoming earnings date | "Recent Earnings Date" / "Upcoming Earnings Date" | 直接有，EP 必加 |

**关键结论：ADR% 和 Price×avgvol 这两项 TV screener 做不精确**——所以 TV 路线是"screener 粗筛 + 图上 ADR 指标精确确认"两步走。Deepvue 能一步到位，故为主。

---

## 人工过滤：Stage 2 与形态确认

选股器只管数值，**Stage 和形态必须人工在图上看**。

### Stage 分析（来自 Stan Weinstein，培训《Reading Price Action》页引用）
价格生命周期分四阶段，基准是 **30 周均线（≈150 日线）**：
- **Stage 1 筑底**：30 周线走平，价格在其上下来回——不碰。
- **Stage 2 上涨**：价格在 30 周线**上方**、30 周线**上行**——**只在这个阶段做多**。
- **Stage 3 做头**：30 周线走平、价格上下穿——减仓/不进。
- **Stage 4 下跌**：价格在 30 周线**下方**、30 周线下行——绝不碰（更别抄底）。

实操：周线图挂 30 周 SMA（或 EMA 21/50 周线辅助），确认"价在线上 + 线向上"才算 Stage 2，再回日线找 Breakout 形态。

### 形态确认
回 `setups.md` 套 Breakout 三步形态 / EP 形态条件；重点用其中的"**吸筹 vs 派发**对照表"判断整理区是不是真的在蓄势，用"**突破后资金行为时间线**"判断现在处于突破早/中/晚期。

---

## 衔接执行
扫出 + 过滤完 → 进 watchlist → 画 PDH、切分钟线找 ORH、用 Long Position 工具算仓位与盈亏比。详见 `tradingview-setup.md` 与 `risk-and-exits.md`，本文件不重复。
