# TradingView 实操指南

把 Qullamaggie 方法在 TradingView 上落地。来源：群培训《趋势交易基础》第 5 节 + 黄哥分享的 Market Environment 指标。

## 一次性设置
1. **连接券商**：TradingView 里绑定自己的券商账户，可直接下单。
2. **均线模板**：在日线挂 EMA10、EMA20（EMA21）、SMA50；周线用于判断 Stage 2 趋势。
3. **保存图表布局**：日线为主、周线为辅、分钟线（≥5min）用于进场。

## 盘前 / 盘中流程
1. **画 PDH（前一日最高价）**：用水平线标出前一日高点，便于观察是否突破成功。
2. **分钟线切换进场**：进场时切到分钟线找开盘区间高点（ORH）。建议**至少 5 分钟**——1 分钟噪音太多；周期越大噪音越小但止损可能越宽。找到自己最舒服的区间。
3. 备好 watchlist + 价格 alert，想好买多少股。

## Long Position 工具（最重要！）
TradingView 的 **Long Position（多头持仓）** 画图工具，用来一眼看清盈亏比、止损、止盈、仓位：
1. **先在工具设置里填好 Account Size（总账户金额）和 Account Risk（单笔风险 %，如 0.5%）。**
2. 在图上拖出：进场价（entry）、止损价（stop / 当日低点）、止盈目标（target）。
3. 工具会**根据你设的 Account Risk 自动反推仓位（股数）**并显示盈亏比——省去手算，抓住稍纵即逝的机会。
4. 检查：止损宽度 ≤ ADR/ATR？盈亏比够不够（目标 ≥ 3R，理想 5-20R+）？不达标就放弃。

## 装 ADR 指标
TradingView 搜 "ADR (Average Daily Range)"，推荐 MikeC / TheScrutiniser 版本：
https://uk.tradingview.com/script/6KVjtmOY-ADR-Average-Daily-Range-by-MikeC-AKA-TheScrutiniser/
- 看到某票 ADR < 3% 直接跳过。

## 装并使用 Market Environment 指标（判断牛/熊/回调）
源码：本 skill 的 `assets/market-environment.pine`（Pine v6）。

**安装步骤**：
1. TradingView 底部打开 **Pine 编辑器（Pine Editor）**。
2. 把 `market-environment.pine` 全文粘贴进去（如排版乱，先粘到记事本再粘过来，或让 AI 帮忙修排版）。
3. 点 **Save** → **Add to chart**。

**读法**：背景色 = 市场状态（数据源默认 NASDAQ:NDX 日线，可在设置里改）：
- **绿色 = Bull（牛市）**：fastMA(10) > midMA(21) > slowMA(50) 连续 ≥2 根 → 可以打顺风局。
- **黄色 = Pullback（回调）**：快线下穿中线 → 谨慎，等企稳。
- **红色 = Bear（熊市）**：快线在中线下方且慢线上穿 → **不交易**。
- 三条均线（绿=快/橙=中/蓝=慢）也画在图上。
- 可设 Bull/Bear/Pullback 三个 alert 提醒状态切换。

> 指标只是辅助；最终仍以 QQQ/NDX 周线趋势和你自己的判断为准。熊市/黑天鹅恐慌期一律空仓。

## 交易日记
用 Google Sheet 或表格记录每笔：标的、setup 类型（Breakout/EP/ORH/Pullback）、进场价、止损、R、结果（几 R）、当时逻辑、复盘。黄哥分享过一个日记模板含年化收益率/盈亏比/平均盈利率计算器（白色填写、橙色自动算）。坚持 PDCA 复盘。
