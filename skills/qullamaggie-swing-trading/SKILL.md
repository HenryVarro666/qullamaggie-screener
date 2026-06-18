---
name: qullamaggie-swing-trading
description: >-
  Qullamaggie (Kristjan Kullamägi) 趋势交易/swing trading 方法的实操助手，专为在 TradingView 上看盘和交易设计。
  覆盖两大 setup —— Breakout（突破）和 EP（Episodic Pivot 事件驱动转折）—— 的定义、选股筛选、进场（开盘区间高点 ORH）、
  止损（当日低点且不宽于 ADR/ATR）、分批止盈，以及 R/盈亏比、仓位与风险管理、市场环境（牛/熊/回调）判断、
  TradingView 工具（Long Position 仓位工具、Account Risk、PDH 画线、ADR 指标、Market Environment 指标）。
  当用户在做美股 swing trading / 趋势交易、提到 Qullamaggie/Qullamagie/Kullamägi/抠挖/黄哥的方法、
  在 TradingView 上分析某只股票能不能买/在哪进场/止损放哪/什么时候卖、判断当前是牛市还是熊市、
  计算仓位或 R、做交易复盘、或问 Breakout/EP/ADR/ATR/盈亏比 相关问题时，主动使用本 skill。
  既能当盘前/盘中的操作清单，也能当方法论陪练。不构成投资建议。
---

# Qullamaggie 趋势交易助手（TradingView 版）

这套方法来自 Kristjan Kullamägi（Qullamaggie），由群内"黄哥"的培训整理而成。核心信念：**低胜率（约 25-30%）、高盈亏比**，靠少数大赢家覆盖大量小亏损，单笔目标 5-20R 以上。本 skill 帮用户在 **TradingView** 上把这套方法执行到位。

> ⚠️ 这是交易方法学习与执行辅助工具，**不是投资建议**。所有进场/止损/止盈点位都需用户自己在图上确认。

## 何时做什么（先定位用户在哪一步）

- **判断能不能交易 / 现在是不是好时机** → 先查市场环境（见下方"打顺风局"），熊市不交易。
- **找票 / 怎么扫出 Setup / 建 watchlist** → 用选股器，Breakout 和 EP 各一套精确 filter（**Deepvue** 为主，TradingView 内置 screener 映射）→ `references/screening.md`。
- **某只票能不能买 / 在哪进场** → 走"识别 Setup"流程，先分清是 Breakout 还是 EP，再套对应规则（`references/setups.md`）。
- **止损放哪 / 仓位多大 / 这笔几个 R** → 用风险与仓位规则（`references/risk-and-exits.md`），并提醒用 TradingView Long Position 工具。
- **怎么在 TradingView 上操作 / 装指标 / 画线** → `references/tradingview-setup.md`。
- **复盘 / 解释方法 / 纠正认知** → 当陪练，引用本 skill 的原则，而不是凭空发挥。

## 三大铁律（任何建议都不能违背）

1. **只交易被反复验证的 Setup**（Breakout / EP）——减少试错，保证合理胜率。错过一只票的 setup 就去找下一只，专注 setup 而非某只股票。
2. **紧止损**——犯错代价小。单笔止损 ≤ 总账户 0.5%（铁律红线），止损宽度 ≤ 股票 ADR/ATR，否则盈亏比失真。
3. **分批止盈**——避免煮熟的鸭子飞了。进场后 3-5 天卖 1/3~1/2 并把止损移到成本之上（保本），剩余用 EMA10/EMA20 trailing。

> 进场前先问：我的对手是谁？凭什么让我赚到钱？股市是零和游戏。绝不抄底（大概率抄在半山腰）。

## 打顺风局：交易前三道闸门

只在三者同时成立时出手，否则空仓等待：

1. **市场环境 = 牛市**。用 QQQ/NDX 周线看趋势；或挂本 skill 的 **Market Environment 指标**（`assets/market-environment.pine`，绿=牛/黄=回调/红=熊）。**熊市/黑天鹅恐慌期一律不交易**——恐慌会系统性拉低胜率（黄哥 3 月美伊战争一夜跌破止损、回撤 20% 的教训）。
2. **热门产业/主题**。判断核心看**成交量**——"嘴会骗人，钱不会"。
3. **高 ADR 的强势股**。`high ADR is Gold, low ADR is Shit`。**自动忽略 ADR < 3% 的票**，无论公司多大多好。只交易**周线 Stage 2**（上升趋势）的股票。

## 识别 Setup（判断一只票能不能交易）

先分类，再套规则。完整细节见 `references/setups.md`。

**Breakout（突破）** —— 三步形态：
1. 过去 1-3 个月有过一波大涨（30-100%+，几天到几周）；
2. 之后**有序回调 + 横盘整理**，更高的低点、波动收窄，价格"贴"着上升的 10/20（有时 50）日均线；
3. 从整理区**放量突破**。整理通常持续 2 周-2 个月。
- 筛选：扫 1 月 / 3 月 / 6 月涨幅前 1-2% 的票。Deepvue 精确设置（`ADR≥3%`、`Price≥1`、`Perf 6M≥20%`、`Price×avg vol 30D≥500K`）见 `references/screening.md`。

**EP（Episodic Pivot 事件驱动转折）** —— 意外利好（多为财报）点燃的多月行情：
- **跳空 ≥ 10%** + **大成交量**（盘前没有，则开盘 5-30 分钟内必须放量到日均量级）；
- 财报型需有**强劲增长**（EPS/营收中高双位甚至三位数，显著超预期）；
- **该股过去 3-6 个月最好没怎么涨过**——涨过了就不算"意外"了。
- Deepvue 精确设置（`Pre-mkt gap≥10%` + earnings date + EPS/Revenue growth）见 `references/screening.md`。

两者**进场方式相同**：在**开盘区间高点（ORH）**买入——可用首根 1/5/60 分钟 K 线高点（60 分钟首根实际是 9:30-10:00）。也可只看日线在突破启动时进。

## 进场 / 止损 / 止盈速查

- **进场**：开盘区间高点（ORH）突破。盘前/盘中准备好 watchlist 和 alert，想好买多少股。
- **止损**：永远是**当日低点**，且止损宽度 **≤ 股票 ADR/ATR**（ADR 5% → 止损不超过 5%）。用市价止损，不用限价止损。
- **止盈（分批）**：
  - 进场后 **3-5 天卖 1/3~1/2**，同时把止损上移到**成本之上**（这笔从此稳赚，心里有底才拿得住，让利润奔跑）；
  - 余仓用 **EMA10（快票）或 EMA20/EMA50（慢票）trailing**，等**收盘价首次跌破**该均线再卖；新手统一用 EMA10。（本方法的核心均线组按培训统一记为 **EMA 9/21/50**，文中 EMA10/20/50 即指这一组。）
- 黄哥的细化止盈（可选参考）：到 3R 卖 25%；过度延伸（距 EMA50 > ~10×ATR/ADR）卖 25%；从高点回落 1.5×ADR/ATR 卖 25%；收盘破 EMA10/EMA21 卖最后 25%。

## R 与仓位（动手算时务必用 TradingView Long Position 工具）

- **R = 单笔止损金额**。账户 1 万、单笔风险 1% → 1R = $100。用 R 衡量交易，不用百分比或金额。
- **单笔账户风险**：黄哥 ≤ 0.5%；Qullamaggie 多为 0.3-0.5%，极少 > 1%。
- **单笔股价止损幅度**：≤ 5%，绝大多数 ≤ 3%。
- **单仓位**：账户的 5-25%，多数 10-15%。**隔夜任何单票/ETF 不超过 30%**。
- 仓位反推：`股数 = (账户 × 单笔风险%) / (进场价 − 止损价)`。在 TradingView 先设好 Account Size 和 Account Risk，用 **Long Position 工具**拖出进场/止损/止盈，系统自动算仓位、盈亏比——抓住稍纵即逝的机会。

详见 `references/risk-and-exits.md`。

## 心态与纪律（Rule No.1: Never lose money）

- 不亏钱能解决交易中绝大多数心理问题。痛苦排序：亏 10% > 回撤少赚 10% > 赚 10% 的快乐。
- 不带情绪交易，不上头梭哈，不报复性交易。低胜率是常态，把过程做对，结果自然跟上。
- 删掉财经新闻 App——新闻和社媒是 trading 的干扰。决策依据只有：市场环境、热门主题、相对强度(RS)、ADR、以及最关键的 **Setup**。
- 持续复盘（PDCA），记交易日记，长期主义，享受复利。

## 参考文件

- `references/screening.md` —— 选股：Breakout/EP 的 **Deepvue 精确选股器设置** + TradingView 内置 screener 映射 + 选股总流程 + Stage 2 判定。要找票/建 watchlist 时读。配图 `assets/screeners/`。
- `references/setups.md` —— Breakout 与 EP 的完整定义、筛选、进场、止损、止盈、吸筹 vs 派发、突破后资金时间线、原文案例（NVDA/FSLR/TSLA 等）。需要精确套规则或举例时读。
- `references/risk-and-exits.md` —— R/盈亏比数学（含 E>0、止损↔R 抛物线关系、真实统计）、仓位反推、分批止盈细则、Edge 清单（RS、AVWAP、Inside bar、放量突破、Stage/波浪、RSI 背离）。
- `references/tradingview-setup.md` —— TradingView 实操：连券商、画 PDH、分钟线切换、Long Position 工具用法、装 ADR 指标、装并使用 Market Environment 指标（`assets/market-environment.pine`）。
- `assets/market-environment.pine` —— Pine v6 市场环境指标源码，复制到 TradingView Pine 编辑器即可用。
- `assets/screeners/breakout-screener.png`、`assets/screeners/ep-screener.png` —— 培训里 Breakout/EP 选股器的原始截图，照着在 Deepvue 里摆 filter。
