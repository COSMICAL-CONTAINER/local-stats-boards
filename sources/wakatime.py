# -*- coding: utf-8 -*-
"""WakaTime 编程时长看板适配器：从 Summaries API 拉全历史 → 标准化 DATA + 图表声明。

用法: python sources/wakatime.py [--since 2023-10-01] [--end 2026-09-05] > boards/wakatime.html
"""
import argparse, json, os, sys, time
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core import net, render  # noqa: E402

GAP = 1.1


def month_chunks(since, end):
    cur = since
    while cur <= end:
        last = (date(cur.year, cur.month, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        yield cur, min(last, end)
        cur = last + timedelta(days=1)


def fetch(since, end):
    """拉取 [since, end] 的每日 Summaries。返回 (daily, failed_months)。"""
    daily, failed = [], []
    for a, b in month_chunks(since, end):
        data = net.get(f"/users/current/summaries?start={a}&end={b}")
        if data is None:
            failed.append(f"{a}~{b}")
            continue
        for day in data.get("data", []):
            gt = day.get("grand_total") or {}
            daily.append({
                "d": day.get("range", {}).get("date", "")[:10],
                "s": round(gt.get("total_seconds") or 0, 1),
                "projects": {p.get("name", "?"): round(p.get("total_seconds") or 0, 1)
                             for p in day.get("projects", [])},
                "languages": {l.get("name", "?"): round(l.get("total_seconds") or 0, 1)
                              for l in day.get("languages", [])},
                "editor": (max(day.get("editors", []), key=lambda x: x.get("total_seconds", 0)).get("name")
                           if day.get("editors") else ""),
            })
        print(f"  已取 {a} ~ {b}（累计 {len(daily)} 天）", file=sys.stderr)
        time.sleep(GAP)
    return daily, failed


CONFIG_JS = r"""
window.BOARD = {
  title: 'WakaTime 编程时长看板',
  ranges: [{label:'全部',days:0},{label:'近一年',days:365},{label:'近 90 天',days:90},{label:'近 30 天',days:30}],
  subLine: D => `数据源 <b>WakaTime API · Summaries</b> · 记录区间 <b>${D.meta.start} ~ ${D.meta.end}</b> · 共 <b>${D.meta.days}</b> 天 · 生成于 <b>${D.meta.generated}</b>`,
  footerHtml: `<b>统计口径说明</b><br>· 数据来自 WakaTime 官方 Summaries API，区间内每天一条记录，时长按天求和<br>` +
              `· 时长由 WakaTime 按心跳 activity 计算，仅供参考 · 本页为纯静态单文件，数据生成后不自动更新，重跑构建脚本可刷新`,
  kpis(ds, D){
    const tot = ds.reduce((a,d)=>a+d.s,0);
    const active = ds.filter(d=>d.s>60).length;
    const proj={}, lang={};
    for (const d of ds){
      for (const [k,v] of Object.entries(d.projects||{})) proj[k]=(proj[k]||0)+v;
      for (const [k,v] of Object.entries(d.languages||{})) lang[k]=(lang[k]||0)+v;
    }
    const top = m => Object.entries(m).sort((a,b)=>b[1]-a[1])[0] || ['–',0];
    const [tp,tv]=top(proj), [tl,lv]=top(lang);
    const pc = v => tot ? (v/tot*100).toFixed(1)+'%' : '0%';
    const lastEd = (ds.filter(d=>d.editor).pop()||{editor:'–'}).editor;
    return [
      {icon:'⏱', label:'总编码时长', value:Core.fmt.hms(tot), sub:ds.length+' 天记录', c1:'#34d399', c2:'#22d3ee', vc:'#6ee7b7'},
      {icon:'📅', label:'日均编码', value:Core.fmt.hms(active?tot/active:0), sub:'按活跃天数平均', c1:'#22d3ee', c2:'#3b82f6', vc:'#67e8f9'},
      {icon:'🔥', label:'活跃天数', value:active+' 天', sub:'超过 1 分钟的天数', c1:'#a78bfa', c2:'#22d3ee', vc:'#c4b5fd'},
      {icon:'🏆', label:'Top 项目', value:tp, sub:Core.fmt.hms(tv)+' · '+pc(tv), c1:'#e879f9', c2:'#a78bfa', vc:'#f0abfc'},
      {icon:'💻', label:'Top 语言', value:tl, sub:Core.fmt.hms(lv)+' · '+pc(lv), c1:'#fbbf24', c2:'#f472b6', vc:'#fcd34d'},
      {icon:'🖥', label:'主力编辑器', value:lastEd, sub:'最近一天记录', c1:'#60a5fa', c2:'#a78bfa', vc:'#93c5fd'},
    ];
  },
  charts(ds, D){
    const proj={}, lang={};
    for (const d of ds){
      for (const [k,v] of Object.entries(d.projects||{})) proj[k]=(proj[k]||0)+v;
      for (const [k,v] of Object.entries(d.languages||{})) lang[k]=(lang[k]||0)+v;
    }
    const projItems = Object.entries(proj).sort((a,b)=>b[1]-a[1]);
    const langItems = Object.entries(lang).sort((a,b)=>b[1]-a[1]);
    return [
      {id:'trend', type:'trend', title:'每日编码时长', note:'柱 = 当日时长 · 粉线 = 7 日均线 · 支持框选缩放',
       height:400, full:true, barName:'当日时长', yName:'小时', maColor:'#f472b6',
       values: ds=>ds.map(d=>+(d.s/3600).toFixed(2)),
       tip:(ds,i,maV)=>{ const d=ds[i]; return `<b style="color:#6ee7b7">${d.d}</b><br>编码时长：<b style="color:#6ee7b7">${Core.fmt.hms(d.s)}</b><br>7 日均值：<b style="color:#f472b6">${maV!=null?Core.fmt.hms(maV*3600):''}</b>`; }},
      {id:'stack', type:'stack', title:'项目使用演进', note:'每日时长按项目堆叠 · Top 8 项目', height:360, full:true,
       names: ds=>{ const t={}; for (const d of ds) for (const [k,v] of Object.entries(d.projects||{})) t[k]=(t[k]||0)+v;
                    return Object.entries(t).sort((a,b)=>b[1]-a[1]).slice(0,8).map(e=>e[0]); },
       value:(d,n)=>((d.projects||{})[n]||0)/3600, yFmt:'{value}h', valueFmt:v=>v+'h'},
      {id:'projbar', type:'hbar', title:'项目时长排行', note:`Top ${Math.min(10,projItems.length)} · 共 ${projItems.length} 个项目`,
       c1:'#6ee7b7', c2:'rgba(34,211,238,.35)', labelColor:'#6ee7b7', labelWidth:74,
       items: ()=>projItems.slice(0,10).map(([n,v])=>[n, v/3600]).reverse(), fmt:v=>v.toFixed(1)+'h'},
      {id:'langbar', type:'hbar', title:'语言时长排行', note:`Top ${Math.min(10,langItems.length)} · 共 ${langItems.length} 种语言`,
       c1:'#f0abfc', c2:'rgba(167,139,250,.35)', labelColor:'#f0abfc', labelWidth:74,
       items: ()=>langItems.slice(0,10).map(([n,v])=>[n, v/3600]).reverse(), fmt:v=>v.toFixed(1)+'h'},
    ];
  },
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="起始日期 YYYY-MM-DD，默认=账号创建日")
    ap.add_argument("--end", help="结束日期，默认今天")
    args = ap.parse_args()

    info = net.get("/users/current")
    if not info:
        print("用户信息拉取失败", file=sys.stderr)
        sys.exit(1)
    created = info["data"]["created_at"][:10]
    end = date.fromisoformat(args.end) if args.end else date.today()
    since = date.fromisoformat(args.since) if args.since else date.fromisoformat(created)

    print(f"账号创建于 {created}，拉取 {since} ~ {end}", file=sys.stderr)
    daily, failed = fetch(since, end)
    if failed:
        print(f"以下月份拉取失败，请重跑补齐：{', '.join(failed)}", file=sys.stderr)
        sys.exit(1)
    if not daily:
        print("没有数据", file=sys.stderr)
        sys.exit(1)

    data = dict(meta=dict(source="WakaTime API · Summaries", start=daily[0]["d"], end=daily[-1]["d"],
                          days=len(daily), generated=datetime.now().strftime("%Y-%m-%d %H:%M")),
                daily=daily)
    sys.stdout.write(render.render_board("WakaTime 编程时长看板", "WAKATIME",
                                         json.dumps(data, ensure_ascii=False), CONFIG_JS))
    print(f"完成：{len(daily)} 天，总时长 {sum(d['s'] for d in daily)/3600:.1f} 小时", file=sys.stderr)


if __name__ == "__main__":
    main()
