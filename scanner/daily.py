#!/usr/bin/env python3
# 三合一日报：一次全市场扫描 → 一份 YYYY-MM-DD.md（市场环境 + 目录 + 主题热力图[在前] + 可买清单 + 全市场突破榜）。
# 每只命中带 TradingView 日K图 + 形态健康度(数值[TV量能+Yahoo逐K] + 可选AI看图)。每天只开这一份、按板块找。
#   跑法：python3 ~/.deepvue/daily.py   （TOPN=25 全市场条数；CHARTS=0 关图；HEALTH=0/VISION=0 关形态）
import datetime, statistics, os
from qmag_core import *
from charts import ensure_charts
from health import health_for, health_line

N=int(os.environ.get("TOPN","25"))
enabled={k:v for k,v in cfg["themes"].items() if v.get("enabled")}
theme_tickers={k:list(dict.fromkeys(v["tickers"])) for k,v in enabled.items()}
idx_themes={}
for k,ts in theme_tickers.items():
    for t in ts: idx_themes.setdefault(t,[]).append(k)
theme_set=set(idx_themes)

M=fetch(None)                                              # 一次全市场，三视图共用
flags={t:(is_breakout(m),is_ep(m)) for t,m in M.items()}
unresolved={k:[t for t in ts if t not in M] for k,ts in theme_tickers.items()}
unresolved={k:v for k,v in unresolved.items() if v}

ready_all=[m for m in M.values() if is_ready(m) and (m.get("type") in ("stock","dr") or m.get("type") is None)]
ready_all.sort(key=ready_key, reverse=True)
mkt_ready=ready_all[:10]; theme_ready=[m for m in ready_all if m["ticker"] in theme_set][:10]
nbk_all=sum(1 for m in M.values() if is_breakout(m))
whole=[m for m in M.values() if is_breakout(m) and (m.get("type") in ("stock","dr") or m.get("type") is None)]
whole.sort(key=lambda m:(m["p6"] if m["p6"] is not None else -9), reverse=True); whole=whole[:N]
theme_hits=[t for t in theme_set if t in M and (flags[t][0] or flags[t][1])]

date_str=os.environ.get("REPORT_DATE") or datetime.datetime.now().strftime("%Y-%m-%d")   # REPORT_DATE 覆盖：改码后用当天缓存重生成旧报告，不重抓
run_ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
show={}
for t in theme_hits: show[t]=M[t]
for m in (mkt_ready+theme_ready+whole): show[m["ticker"]]=m
print(f"配图（TradingView 日K截图）… 待展示 {len(show)} 只")
cm=ensure_charts({t:tv_symbol(m) for t,m in show.items()}, date_str, print)
print("形态健康度（数值[TV量能+Yahoo逐K] + 可选AI看图）…")
hm=health_for(list(show.values()), cm, date_str, print)

def emb(t):                                               # 图 + 形态行（作为该股的子项）
    out=[]; rel=cm.get(t)
    if rel: out.append(f"  - ![{t} 日K]({rel})")
    hl=health_line(hm.get(t))
    if hl: out.append(hl)
    return out

reg=regime_lines()
md=[f"# 每日盯盘 · {date_str}"]
md.append(f"\n> 运行：{run_ts} ｜ 后端：**{BACKEND}** ｜ 全市场 {len(M)} ｜ 主题命中 {len(theme_hits)} ｜ 可买 {len(ready_all)} ｜ Breakout {nbk_all}")
md+=reg

# —— 目录 ——
md.append("\n## 目录")
md.append("- 板块（主题热力图）：" + " · ".join(f"[{k}](#{k})" for k in enabled))
md.append("- [可买清单](#可买清单)　|　[全市场突破榜](#全市场突破榜)　|　**[⚡ 可快速入手·精选（今日结论）](#-可快速入手--精选今日结论)**")
md.append("> 标记：**✓**Breakout **⚡**EP **⭐**可买。**形态**：🟢吸筹收紧 / 🟡中性 / 🔴派发疑虑（数值=TV量能+Yahoo逐K；👁AI=看图复核）。数值与 AI 皆**辅助**，关键仓位仍自己看图。\n")

# —— 主题热力图（在前）——
md.append("## 主题热力图")
for name in enabled:
    rows=[M[t] for t in theme_tickers[name] if t in M]
    rows.sort(key=lambda m:(m["p6"] if m["p6"] is not None else -9), reverse=True)
    nbk=sum(1 for m in rows if flags[m["ticker"]][0]); nep=sum(1 for m in rows if flags[m["ticker"]][1])
    p6s=[m["p6"] for m in rows if m["p6"] is not None]; medv=statistics.median(p6s) if p6s else None
    md.append(f"\n### {name}")
    md.append(f"*{len(rows)}只 · {nbk}✓ · {nep}⚡ · 中位6M {pct(medv)}*" + (f"　{enabled[name]['note']}" if enabled[name].get("note") else ""))
    md.append("\n| | Tkr | Last | ADR | 6M | 3M | 1M | 离高 | St2 | Gap | RV | $Vol |")
    md.append("|--|--|--:|--:|--:|--:|--:|--:|:--:|--:|--:|--:|")
    for m in rows:
        fb,fe=flags[m["ticker"]]; mk=("✓" if fb else "")+("⚡" if fe else "")+("⭐" if is_ready(m) else "")
        md.append(f"| {mk} | **{m['ticker']}** | {fp(m['last'])} | {fadr(m['adr'])} | {pct(m['p6'])} | {pct(m['p3'])} | {pct(m['p1'])} | {pct(m['off_high'])} | {st2(m)} | {pct1(m['gap'])} | {frv(m['relvol'])} | {fvol(m['dollar_vol'])} |")
    hits=[m for m in rows if flags[m["ticker"]][0] or flags[m["ticker"]][1]]
    if hits:
        md.append("\n**命中逐只：**")
        for m in hits:
            md.append(analysis(m, idx_themes.get(m["ticker"],[]), *flags[m["ticker"]])); md+=emb(m["ticker"])
    else:
        md.append("\n*本主题今日无命中。*")

# —— 可买清单 ——
md.append("\n## 可买清单")
md.append("> Breakout 命中里再筛'就绪/可买'（贴52周高+近月整理+流动性），按就绪度排序。**先看形态行**确认是吸筹收紧而非派发。**今日'可快速入手'结论见文末精选表。**")
def ready_block(title, rows):
    md.append(f"\n### {title}（{len(rows)}）")
    if not rows: md.append("_今日无_"); return
    md.append("| # | Tkr | 6M | 3M | 1M | 离高 | ADR | $Vol | Sector |")
    md.append("|--:|--|--:|--:|--:|--:|--:|--:|--|")
    for i,m in enumerate(rows,1):
        thm=("｜"+"/".join(idx_themes[m["ticker"]])) if m["ticker"] in theme_set else ""
        md.append(f"| {i} | **{m['ticker']}** | {pct(m['p6'])} | {pct(m['p3'])} | {pct(m['p1'])} | {pct(m['off_high'])} | {fadr(m['adr'])} | {fvol(m['dollar_vol'])} | {m['sector']}{thm} |")
    md.append("")
    for m in rows:
        md.append(analysis(m, idx_themes.get(m["ticker"],[]), True, is_ep(m))); md.extend(emb(m["ticker"]))
ready_block("全市场可买", mkt_ready)
ready_block("主题内可买", theme_ready)

# —— 全市场突破榜 ——
md.append("\n## 全市场突破榜")
md.append(f"> 全市场 Breakout {nbk_all} 只按6M取前 {len(whole)}（个股、排除杠杆ETF）。")
md.append("\n| # | Tkr | Last | ADR | 6M | 3M | 1M | 离高 | St2 | $Vol | Sector |")
md.append("|--:|--|--:|--:|--:|--:|--:|--:|:--:|--:|--|")
for i,m in enumerate(whole,1):
    md.append(f"| {i} | **{m['ticker']}** | {fp(m['last'])} | {fadr(m['adr'])} | {pct(m['p6'])} | {pct(m['p3'])} | {pct(m['p1'])} | {pct(m['off_high'])} | {st2(m)} | {fvol(m['dollar_vol'])} | {m['sector']} |")
md.append("\n### 日K图与形态")
for i,m in enumerate(whole,1):
    t=m["ticker"]; rel=cm.get(t)
    md.append(f"\n**{i}. {t}**　{pct(m['p6'])} 6M · ADR {fadr(m['adr'])} · 离高 {pct(m['off_high'])}")
    md.append(f"![{t} 日K]({rel})" if rel else "_(图未生成)_")
    nt=stage_note(m, True, is_ep(m))
    if nt: md.append("- **阶段与注意**：" + "；".join(nt) + "。")
    hl=health_line(hm.get(t))
    if hl: md.append(hl.lstrip())

if unresolved:
    md.append("\n---\n## ⚠️ 未取到数据的 ticker（退市/非美股/拼写）")
    for k,vv in unresolved.items(): md.append(f"- **{k}**: {', '.join(vv)}")

# —— ⚡ 可快速入手·精选（放文末作"今日结论"；阶段+形态+警示 打分，🟢第一梯队置顶）——
_STAGE_SHORT={"较理想候选":"候选·等ORH","突破后期":"后期·别追","趋势延续":"趋势·持有"}
picks=list({m["ticker"]:m for m in (mkt_ready+theme_ready)}.values())
picks=sorted(picks, key=lambda m: quick_pick(m, True, is_ep(m), hm.get(m["ticker"]))[0], reverse=True)
if picks:
    md.append("\n---\n## ⚡ 可快速入手 · 精选（今日结论）")
    md.append("> 评分 = 阶段(较理想候选+3/趋势+1/后期−2) ＋ 数值形态(吸筹+2/派发−2) ＋ AI看图(🟢+1/🔴−1) − ⚠️数。**🟢第一梯队 = 挂 ORH 突破单首选**；🟡观察 = 形态未净，再等。仍须看图终判，非投资建议。")
    md.append("\n| 梯队 | Tkr | 6M | 1M | 离高 | ADR | 阶段 | 形态 | 👁AI | ⚠️ | $Vol | 板块 |")
    md.append("|--|--|--:|--:|--:|--:|--|:--:|:--:|:--:|--:|--|")
    for m in picks:
        s,stage,tier=quick_pick(m, True, is_ep(m), hm.get(m["ticker"]))
        h=hm.get(m["ticker"],{}) or {}; num=h.get("verdict","")
        ne="🟢" if "吸筹" in num else ("🔴" if "派发" in num else "🟡")
        ai=(h.get("vision") or {}).get("emoji","—") or "—"
        warns="；".join(stage_note(m, True, is_ep(m))).count("⚠️")
        plate="/".join(idx_themes[m["ticker"]]) if m["ticker"] in theme_set else m["sector"]
        md.append(f"| {tier} | **{m['ticker']}** | {pct(m['p6'])} | {pct(m['p1'])} | {pct(m['off_high'])} | {fadr(m['adr'])} | {_STAGE_SHORT.get(stage,stage)} | {ne} | {ai} | {warns} | {fvol(m['dollar_vol'])} | {plate} |")

md.append(f"\n---\n*后端={BACKEND}；图=TradingView widget 截图；形态=TV量能+Yahoo逐K+可选AI看图（延迟/EOD）。✓/⚡/⭐与形态均为数值/AI辅助，非投资建议。*")

os.makedirs(OUTDIR, exist_ok=True); out_path=os.path.join(OUTDIR, f"{date_str}.md")
with open(out_path,"w",encoding="utf-8") as f: f.write("\n".join(md))
print(reg[0].lstrip("> ").replace("**",""))
print(f"主题命中 {len(theme_hits)} ｜ 可买 全{len(mkt_ready)}/主题{len(theme_ready)} ｜ 全市场Top {len(whole)} ｜ 配图 {sum(1 for v in cm.values() if v)} ｜ 形态 {len(hm)}")
print(f"📄 已保存（一份）: {out_path}")
