# -*- coding: utf-8 -*-
"""cc-switch 供应商用量看板适配器：读本地 SQLite → 标准化 DATA + 图表声明。

用法: python sources/ccswitch.py [--demo] > boards/cc-switch.html
"""
import argparse, json, os, random, sqlite3, sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from core import render  # noqa: E402

HOME = os.path.expanduser("~")
DB = os.path.join(HOME, ".cc-switch", "cc-switch.db")


def build_real():
    db = sqlite3.connect(DB)
    daily = {}
    for r in db.execute("""
    SELECT date, SUM(request_count), SUM(success_count),
           SUM(input_tokens), SUM(output_tokens), SUM(cache_read_tokens), SUM(cache_creation_tokens),
           SUM(cost)
    FROM (
      SELECT date, request_count, success_count, input_tokens, output_tokens,
             cache_read_tokens, cache_creation_tokens, CAST(total_cost_usd AS REAL) AS cost
      FROM usage_daily_rollups
      UNION ALL
      SELECT date(created_at,'unixepoch','localtime'), 1, CASE WHEN status_code<400 THEN 1 ELSE 0 END,
             input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
             CAST(total_cost_usd AS REAL)
      FROM proxy_request_logs
    ) GROUP BY date ORDER BY date"""):
        daily[r[0]] = dict(d=r[0], requests=r[1] or 0, success=r[2] or 0,
                           in_tok=r[3] or 0, out_tok=r[4] or 0,
                           cache_read=r[5] or 0, cache_create=r[6] or 0,
                           cost=round(r[7] or 0, 4))
    daily = list(daily.values())

    dm = {}
    for r in db.execute("""
    SELECT date, model, SUM(request_count), SUM(input_tokens), SUM(output_tokens),
           SUM(cache_read_tokens), SUM(cache_creation_tokens), SUM(cost)
    FROM (
      SELECT date, model, request_count, input_tokens, output_tokens,
             cache_read_tokens, cache_creation_tokens, CAST(total_cost_usd AS REAL) AS cost
      FROM usage_daily_rollups
      UNION ALL
      SELECT date(created_at,'unixepoch','localtime'), model, 1, input_tokens, output_tokens,
             cache_read_tokens, cache_creation_tokens, CAST(total_cost_usd AS REAL)
      FROM proxy_request_logs
    ) GROUP BY date, model"""):
        dm[(r[0], r[1])] = dict(d=r[0], model=r[1], requests=r[2] or 0, in_tok=r[3] or 0,
                                out_tok=r[4] or 0, cache_read=r[5] or 0, cache_create=r[6] or 0,
                                cost=round(r[7] or 0, 4))

    wd_hour = [[0] * 24 for _ in range(7)]
    for wd, h, c in db.execute("""
    SELECT (CAST(strftime('%w', created_at,'unixepoch','localtime') AS INT)+6)%7,
           CAST(strftime('%H', created_at,'unixepoch','localtime') AS INT), COUNT(*)
    FROM proxy_request_logs GROUP BY 1,2"""):
        wd_hour[wd][h] = c

    recent = {}
    for r in db.execute("""
    SELECT date(created_at,'unixepoch','localtime'), COUNT(*),
           SUM(CASE WHEN status_code<400 THEN 1 ELSE 0 END),
           SUM(CAST(total_cost_usd AS REAL))
    FROM proxy_request_logs GROUP BY 1"""):
        recent[r[0]] = dict(date=r[0], requests=r[1], ok=r[2], cost=round(r[3] or 0, 4), latency=0.0)
    for r in db.execute("""
    SELECT date(created_at,'unixepoch','localtime'), AVG(latency_ms)
    FROM proxy_request_logs WHERE data_source='proxy' AND latency_ms>0 GROUP BY 1"""):
        if r[0] in recent:
            recent[r[0]]["latency"] = round(r[1] / 1000, 2)

    status = [{"code": str(r[0]), "count": r[1]} for r in db.execute(
        "SELECT status_code, COUNT(*) FROM proxy_request_logs WHERE data_source='proxy' GROUP BY 1 ORDER BY 2 DESC")]
    providers = []
    for r in db.execute("""
    SELECT COALESCE(p.name, l.provider_id) AS name, SUM(CAST(l.total_cost_usd AS REAL)) AS cost, COUNT(*)
    FROM proxy_request_logs l LEFT JOIN providers p ON p.id=l.provider_id AND p.app_type=l.app_type
    GROUP BY 1 ORDER BY cost DESC LIMIT 8"""):
        providers.append({"name": r[0][:18], "cost": round(r[1] or 0, 2), "requests": r[2]})

    raw_dates = sorted(recent)
    db.close()
    return dict(
        meta=dict(generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
                  start=daily[0]["d"], end=daily[-1]["d"], days=len(daily),
                  raw_window=f"{raw_dates[0]} ~ {raw_dates[-1]}", rawStart=raw_dates[0]),
        daily=daily, daily_model=list(dm.values()), wd_hour=wd_hour,
        recent=sorted(recent.values(), key=lambda x: x["date"])[-30:],
        status=status, providers=providers)


def build_demo():
    """虚构演示数据：固定种子可复现，含模型切换叙事与使用节奏。"""
    rnd = random.Random(42)  # 固定种子：演示数据可复现（非加密用途）
    END = datetime(2026, 9, 2)
    dates = [(END - timedelta(days=94 - i)).strftime("%Y-%m-%d") for i in range(95)]
    models = [
        dict(name="nova-4-flash", win=(0, 42), w=lambda t: 1.0 - 0.75 * t, unit=0.016, kin=6.5, kcr=6.0, kcc=0.20),
        dict(name="atlas-3", win=(8, 62), w=lambda t: 0.15 + 0.85 * (1 - abs(t - 0.5) * 2), unit=0.030, kin=7.2, kcr=7.5, kcc=0.30),
        dict(name="nova-4-pro", win=(22, 94), w=lambda t: 0.1 + 0.9 / (1 + 2.6 ** (-(t - 0.5) / 0.18)), unit=0.044, kin=7.8, kcr=8.2, kcc=0.32),
        dict(name="lumen-7b", win=(48, 94), w=lambda t: 0.1 + 0.5 * t, unit=0.026, kin=5.6, kcr=5.0, kcc=0.18),
        dict(name="orion-mini", win=(0, 94), w=lambda t: 0.08, unit=0.008, kin=4.8, kcr=4.2, kcc=0.15),
    ]
    wf = {0: 1.05, 1: 1.12, 2: 1.15, 3: 1.00, 4: 0.92, 5: 0.50, 6: 0.42}
    daily, daily_model = [], []
    for i, d in enumerate(dates):
        dt = END - timedelta(days=94 - i)
        g = 0.15 + 0.80 / (1 + 2.718 ** (-(i - 45) / 16))
        cost_d = (18 + 165 * g) * wf[dt.weekday()] * rnd.uniform(0.85, 1.15)
        if i in (52, 74):
            cost_d *= 1.55
        act = [(m, m["w"]((i - m["win"][0]) / max(1, m["win"][1] - m["win"][0])))
               for m in models if m["win"][0] <= i <= m["win"][1]
               and m["w"]((i - m["win"][0]) / max(1, m["win"][1] - m["win"][0])) > 0.02]
        wsum = sum(w for _, w in act)
        okr = 0.885 if i in (39, 67) else rnd.uniform(0.945, 0.99)
        agg = dict(d=d, requests=0, success=0, in_tok=0, out_tok=0, cache_read=0, cache_create=0, cost=0.0)
        for m, w in act:
            c = cost_d * w / wsum
            req = int(c / m["unit"] * rnd.uniform(0.9, 1.1))
            in_t = int(req * m["kin"] * 1000 * rnd.uniform(0.85, 1.15))
            daily_model.append(dict(d=d, model=m["name"], requests=req, in_tok=in_t,
                                    out_tok=int(req * 1100 * rnd.uniform(0.7, 1.3)),
                                    cache_read=int(in_t * m["kcr"] * rnd.uniform(0.8, 1.2)),
                                    cache_create=int(in_t * m["kcc"] * rnd.uniform(0.6, 1.4)),
                                    cost=round(c, 4)))
            agg["requests"] += req
            agg["in_tok"] += in_t
            agg["out_tok"] += int(req * 1100)
            agg["cache_read"] += int(in_t * m["kcr"])
            agg["cache_create"] += int(in_t * m["kcc"])
            agg["cost"] += c
        agg["success"] = int(agg["requests"] * okr)
        agg["cost"] = round(agg["cost"], 4)
        daily.append(agg)

    base = [30, 22, 15, 8, 5, 4, 6, 10, 18, 30, 48, 66, 72, 60, 52, 58, 64, 70, 62, 48, 40, 55, 68, 45]
    raw_reqs = sum(d["requests"] for d in daily[-28:])
    cells = [[base[h] * (0.55 if wd >= 5 and 8 <= h <= 19 else 0.85 if wd >= 5 else 1.0)
              for h in range(24)] for wd in range(7)]
    f = raw_reqs / (4 * sum(sum(r) for r in cells))
    wd_hour = [[int(c * f) for c in row] for row in cells]

    recent = [dict(date=d["d"], requests=d["requests"], ok=d["success"], cost=d["cost"],
                   latency=round((15.2 if d["d"] == dates[67] else rnd.uniform(7.2, 12.5)), 2))
              for d in daily[-28:]]
    proxy_reqs = int(raw_reqs * 0.9)
    status = [{"code": "200", "count": int(proxy_reqs * 0.925)},
              {"code": "429", "count": int(proxy_reqs * 0.043)},
              {"code": "503", "count": int(proxy_reqs * 0.010)},
              {"code": "500", "count": int(proxy_reqs * 0.012)},
              {"code": "502", "count": int(proxy_reqs * 0.007)}]
    providers = [{"name": n, "cost": round(sum(d["cost"] for d in daily[-28:]) * s, 2), "requests": int(raw_reqs * s)}
                 for n, s in [("DemoRelay", 0.46), ("NovaAPI", 0.29), ("LumaGate", 0.16), ("QuickTokens", 0.09)]]
    return dict(
        meta=dict(generated="2026-09-04 12:00", start=dates[0], end=dates[-1], days=95,
                  raw_window=f"{dates[-28]} ~ {dates[-1]}", rawStart=dates[-28],
                  source="演示数据 · 虚构 Demo", demo=True),
        daily=daily, daily_model=daily_model, wd_hour=wd_hour,
        recent=recent, status=status, providers=providers)


CONFIG_JS = r"""
const money = n => '$' + Number(n||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const moneyS = n => n>=1000?'$'+(n/1000).toFixed(2)+'K':'$'+Number(n||0).toFixed(2);
const int = n => Number(n||0).toLocaleString('en-US');
const tok = n => n>=1e9?(n/1e9).toFixed(2)+'B':n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?(n/1e3).toFixed(1)+'K':String(Math.round(n));
const pct = n => (n*100).toFixed(1)+'%';
const WD = ['周日','周一','周二','周三','周四','周五','周六'];
const wdOf = d => WD[new Date(d+'T12:00:00').getDay()];

window.BOARD = {
  title: '用量统计中心',
  ranges: [{label:'全部',days:0},{label:'近 90 天',days:90},{label:'近 30 天',days:30},{label:'近 7 天',days:7}],
  subLine: D => `数据源 <b>${D.meta.source || '~/.cc-switch/cc-switch.db'}</b> · 统计区间 <b>${D.meta.start} ~ ${D.meta.end}</b> · 共 <b>${D.meta.days}</b> 天 · 生成于 <b>${D.meta.generated}</b>`,
  footerHtml: `<b>统计口径说明</b>${DATA.meta.demo ? '<span style="color:#fcd34d">（演示模式：本页所有数字均为虚构假数据）</span>' : ''}<br>` +
              `· ${DATA.meta.start} ~ ${DATA.meta.rawStart || ''} 来自日汇总表 <b>usage_daily_rollups</b>（会话日志导入），${DATA.meta.raw_window || ''} 来自请求明细表 <b>proxy_request_logs</b>（代理转发 + 会话日志），两段无缝衔接、不重复计数<br>` +
              `· 热力图、供应商榜、成功率与延迟基于近 30 天明细窗口；费用按 cc-switch 内置定价与倍率估算，仅供参考 · 本页为纯静态单文件，重跑构建脚本可刷新`,
  onInit(Core){ Core.registerChart('quality', renderQuality); },

  kpis(ds, D){
    const sum = k => ds.reduce((a,d)=>a+d[k],0);
    const tc=sum('cost'), tr=sum('requests'), ti=sum('in_tok'), to=sum('out_tok'), tcr=sum('cache_read'), tcc=sum('cache_create'), ok=sum('success');
    const peak = ds.reduce((a,d)=>d.cost>a.cost?d:a, ds[0]);
    const c429 = (D.status.find(s=>s.code==='429')||{count:0}).count;
    const rc = D.recent, rq = rc.reduce((a,d)=>a+d.requests,0);
    const wavg = rc.reduce((a,d)=>a+d.latency*d.requests,0)/rq;
    return [
      {icon:'💰', label:'总消费 (USD)', value:money(tc), sub:'日均 '+money(tc/ds.length), c1:'#22d3ee', c2:'#3b82f6', vc:'#67e8f9'},
      {icon:'⚡', label:'总请求数', value:int(tr), sub:'日均 '+int(Math.round(tr/ds.length))+' 次', c1:'#a78bfa', c2:'#22d3ee'},
      {icon:'📈', label:'峰值单日', value:moneyS(peak.cost), sub:peak.d+'（'+wdOf(peak.d)+'）', c1:'#e879f9', c2:'#a78bfa', vc:'#f0abfc'},
      {icon:'🧮', label:'累计 Token', value:tok(ti+to+tcr+tcc), sub:'输入 '+tok(ti)+' · 输出 '+tok(to)+' · 缓存读 '+tok(tcr), c1:'#34d399', c2:'#22d3ee'},
      {icon:'✅', label:'请求成功率', value:pct(ok/tr), sub:'明细窗口 429 限流 '+int(c429)+' 次', c1:'#fbbf24', c2:'#f472b6', vc:'#fcd34d'},
      {icon:'⏱', label:'平均响应延迟', value:wavg.toFixed(1)+' s', sub:'近 30 天 · proxy 转发口径', c1:'#60a5fa', c2:'#a78bfa', vc:'#93c5fd'},
    ];
  },

  charts(ds, D){
    const dsModels = new Set(ds.map(d=>d.d));
    const dmAgg = {};
    for (const m of D.daily_model) if (dsModels.has(m.d)) {
      const a = dmAgg[m.model] || (dmAgg[m.model] = {cost:0, requests:0});
      a.cost += m.cost; a.requests += m.requests;
    }
    const modelRank = Object.entries(dmAgg).map(([n,a])=>[n,a.cost]).sort((a,b)=>b[1]-a[1]);
    const cell = {}; for (const m of D.daily_model) if (dsModels.has(m.d)) cell[m.d+'|'+m.model] = (cell[m.d+'|'+m.model]||0)+m.cost;
    const mcnt = {}; for (const m of D.daily_model) if (dsModels.has(m.d)) mcnt[m.d] = (mcnt[m.d]||0)+1;
    const tokTot = {};
    for (const m of D.daily_model) if (dsModels.has(m.d)) {
      const t = tokTot[m.model] || (tokTot[m.model]={in_tok:0,out_tok:0,cache_read:0,cache_create:0});
      t.in_tok+=m.in_tok; t.out_tok+=m.out_tok; t.cache_read+=m.cache_read; t.cache_create+=m.cache_create;
    }
    const top8 = Object.entries(tokTot).sort((a,b)=>{const A=a[1].in_tok+a[1].out_tok+a[1].cache_read+a[1].cache_create,B=b[1].in_tok+b[1].out_tok+b[1].cache_read+b[1].cache_create;return B-A;}).slice(0,8);
    return [
      {id:'trend', type:'trend', title:'每日消费趋势', note:'柱 = 当日费用 · 粉线 = 7 日均线 · 支持框选缩放',
       height:400, full:true, barName:'当日费用', yName:'USD', yFmt:v=>'$'+v,
       values: dss=>dss.map(d=>+d.cost.toFixed(2)),
       tip:(dss,i,maV)=>{ const d=dss[i]; return `<b style="color:#67e8f9">${d.d} ${wdOf(d.d)}</b><br>当日费用：<b style="color:#67e8f9">${money(d.cost)}</b><br>7 日均线：<b style="color:#f472b6">${money(maV||0)}</b><br>请求 ${int(d.requests)} 次 · 成功率 ${pct(d.success/d.requests)}`; }},
      {id:'donut', type:'donut', title:'模型费用占比', note:'Top 6 + 其他 · 共 '+Object.keys(dmAgg).length+' 个模型',
       center:{big:moneyS(ds.reduce((a,d)=>a+d.cost,0)), sub:'区间总费用'},
       items: ds=>modelRank.map(([n,c])=>[n,c]),
       itemTip:(n,v,p)=>`<b style="color:#67e8f9">${n}</b><br>费用 <b>${money(v)}</b>（${p}%）<br>请求 ${int((dmAgg[n]||{requests:0}).requests)} 次`},
      {id:'stack', type:'stack', title:'模型使用演进', note:'每日费用堆叠 · 看清模型切换史', height:360,
       names: ()=>modelRank.slice(0,6).map(e=>e[0]),
       value:(d,n)=>cell[d.d+'|'+n]||0, yFmt:'${value}', valueFmt:v=>'$'+v},
      {id:'tokmix', type:'hstack', title:'模型 Token 构成', note:'按费用 Top 8 模型 · 对数刻度不适用于堆叠，取线性',
       categories: ()=>top8.map(e=>e[0]), fmt:tok, axisFmt:tok,
       series:[{name:'输入',color:'#22d3ee'},{name:'输出',color:'#e879f9'},{name:'缓存读',color:'#a78bfa'},{name:'缓存写',color:'#34d399'}],
       values:(ds2,s)=>top8.map(e=>tokTot[e[0]][{输入:'in_tok',输出:'out_tok',缓存读:'cache_read',缓存写:'cache_create'}[s.name]])},
      {id:'provider', type:'hbar', title:'供应商费用榜', note:'明细窗口 '+(D.meta.raw_window||''),
       c1:'#e879f9', c2:'rgba(167,139,250,.35)', labelColor:'#67e8f9', labelWidth:74, top:14,
       items: ()=>D.providers.map(p=>[p.name,p.cost]).reverse(), fmt:moneyS},
      {id:'heat', type:'heatmap', title:'使用节奏热力图', note:'星期 × 小时请求密度 · 基于明细窗口 '+(D.meta.raw_window||''),
       height:315, full:true, xLabels:Array.from({length:24},(_,i)=>String(i).padStart(2,'0')),
       yLabels:['周一','周二','周三','周四','周五','周六','周日'],
       max: Math.max(...D.wd_hour.flat()),
       data: (()=>{ const a=[]; for (let w=0;w<7;w++) for (let h=0;h<24;h++) a.push([h,w,D.wd_hour[w][h]]); return a; })(),
       tip:(h,w,v)=>`<b>${WD[(w+1)%7]} ${String(h).padStart(2,'0')}:00</b><br>请求 <b style="color:#67e8f9">${int(v)}</b> 次`},
      {id:'quality', type:'quality', title:'近 30 天请求质量', note:'', height:365, full:true},
      {id:'table', type:'table', title:'每日明细', note:`${ds[0].d} ~ ${ds[ds.length-1].d} · ${ds.length} 天 · 点表头排序`,
       height:520, full:true, initSort:{k:'d',dir:-1},
       columns:[
         {k:'d',label:'日期'},{k:'models',label:'模型数'},
         {k:'requests',label:'请求数',fmt:int},{k:'okRate',label:'成功率',fmt:v=>pct(v)},
         {k:'in_tok',label:'输入 Token',fmt:tok},{k:'out_tok',label:'输出 Token',fmt:tok},
         {k:'cache_read',label:'缓存读',fmt:tok},{k:'cache_create',label:'缓存写',fmt:tok},
         {k:'cost',label:'费用 (USD)',fmt:money,cls:'cost'}],
       rows: ds=>ds.map(d=>Object.assign({},d,{models:mcnt[d.d]||0, okRate:d.requests?d.success/d.requests:0})),
       footer: rows=>{ const g=k=>rows.reduce((a,d)=>a+d[k],0);
         return ['区间合计','—',int(g('requests')),pct(g('success')/g('requests')),tok(g('in_tok')),tok(g('out_tok')),tok(g('cache_read')),tok(g('cache_create')),money(g('cost'))]; }},
    ];
  },
};

/* 近 30 天请求质量（自定义图表：柱 + 双轴成功率/延迟折线） */
function renderQuality(ch, spec, ds, DATA, Core){
  const R = DATA.recent;
  const reqs = R.reduce((a,d)=>a+d.requests,0);
  const c429 = (DATA.status.find(s=>s.code==='429')||{count:0}).count;
  const c5xx = DATA.status.filter(s=>s.code[0]==='5').reduce((a,s)=>a+s.count,0);
  spec.note = `成功率 ${pct(R.reduce((a,d)=>a+d.ok,0)/reqs)} · 429×${int(c429)} · 5xx×${int(c5xx)} · 平均延迟 ${(R.reduce((a,d)=>a+d.latency*d.requests,0)/reqs).toFixed(1)}s`;
  ch.setOption({
    animation:false,
    tooltip: Core.tip({trigger:'axis', axisPointer:{type:'shadow'},
      formatter: ps=>{ const d=R[ps[0].dataIndex];
        return `<b style="color:#67e8f9">${d.date} ${wdOf(d.date)}</b><br>请求 <b>${int(d.requests)}</b> 次 · 失败 <b style="color:#f87171">${int(d.requests-d.ok)}</b><br>成功率 <b style="color:#4ade80">${pct(d.ok/d.requests)}</b> · 平均延迟 <b>${d.latency}s</b><br>费用 <b style="color:#67e8f9">${money(d.cost)}</b>`; }}),
    legend:{data:['请求数','成功率','平均延迟'], top:0, right:6, textStyle:{color:Core.AXT}},
    grid:{left:56, right:56, top:38, bottom:44},
    xAxis:{type:'category', data:R.map(d=>d.date.slice(5)),
      axisLine:{lineStyle:{color:'rgba(148,163,184,.28)'}}, axisLabel:{color:Core.AXT, rotate:45, fontSize:11}},
    yAxis:[
      {type:'value', axisLabel:{color:Core.AXT}, splitLine:{lineStyle:{color:Core.SPLIT}}},
      {type:'value', min:80, max:100, axisLabel:{color:Core.AXT, formatter:'{value}%'}, splitLine:{show:false}},
      {type:'value', axisLabel:{color:Core.AXT, formatter:'{value}s'}, splitLine:{show:false}}],
    series:[
      {name:'请求数', type:'bar', barMaxWidth:16, data:R.map(d=>d.requests),
       itemStyle:{borderRadius:[3,3,0,0], color:new echarts.graphic.LinearGradient(0,0,0,1,
         [{offset:0,color:'rgba(34,211,238,.85)'},{offset:1,color:'rgba(34,211,238,.12)'}])}},
      {name:'成功率', type:'line', yAxisIndex:1, smooth:.4, symbol:'circle', symbolSize:5,
       data:R.map(d=>+(d.ok/d.requests*100).toFixed(1)),
       lineStyle:{color:'#4ade80', width:2}, itemStyle:{color:'#4ade80'}},
      {name:'平均延迟', type:'line', yAxisIndex:2, smooth:.4, symbol:'none',
       data:R.map(d=>d.latency),
       lineStyle:{color:'#fbbf24', width:2, type:'dashed'}, itemStyle:{color:'#fbbf24'}}]
  }, true);
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="生成虚构演示数据（不读数据库）")
    args = ap.parse_args()

    data = build_demo() if args.demo else build_real()
    if not data["daily"]:
        print("数据库中没有用量数据", file=sys.stderr)
        sys.exit(1)
    tc = sum(d["cost"] for d in data["daily"])
    tr = sum(d["requests"] for d in data["daily"])
    print(f"模式: {'演示假数据' if data['meta'].get('demo') else '真实数据库'}", file=sys.stderr)
    print(f"日期 {data['meta']['start']} ~ {data['meta']['end']} ({data['meta']['days']} 天) | 总消费 ${tc:,.2f} | 总请求 {tr:,}",
          file=sys.stderr)
    sys.stdout.write(render.render_board("用量统计中心", "CC·SWITCH",
                                         json.dumps(data, ensure_ascii=False), CONFIG_JS))


if __name__ == "__main__":
    main()
