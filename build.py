# -*- coding: utf-8 -*-
"""从 ~/.cc-switch/cc-switch.db 聚合统计数据，注入模板后把单文件看板 HTML 打到 stdout。
用法: python build.py [--demo] > 看板.html   （--demo 生成虚构演示数据，不读数据库）
本脚本只读不写文件；诊断信息走 stderr。"""
import sqlite3, json, os, sys, io, random
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')  # stdout 恒为 UTF-8（HTML），stderr 跟随控制台编码

def log(msg):
    print(msg, file=sys.stderr)

HOME = os.path.expanduser("~")
DB = os.path.join(HOME, ".cc-switch", "cc-switch.db")
HERE = os.path.dirname(os.path.abspath(__file__))


def build_real():
    """读取真实 cc-switch 数据库。"""
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
        daily[r[0]] = dict(date=r[0], requests=r[1] or 0, success=r[2] or 0,
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
        dm[(r[0], r[1])] = dict(date=r[0], model=r[1], requests=r[2] or 0, in_tok=r[3] or 0,
                                out_tok=r[4] or 0, cache_read=r[5] or 0, cache_create=r[6] or 0,
                                cost=round(r[7] or 0, 4))
    daily_model = list(dm.values())

    wd_hour = [[0]*24 for _ in range(7)]
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
            recent[r[0]]["latency"] = round(r[1]/1000, 2)
    recent = sorted(recent.values(), key=lambda x: x["date"])[-30:]

    status = [{"code": str(r[0]), "count": r[1]} for r in db.execute(
        "SELECT status_code, COUNT(*) FROM proxy_request_logs WHERE data_source='proxy' GROUP BY 1 ORDER BY 2 DESC")]

    providers = []
    for r in db.execute("""
    SELECT COALESCE(p.name, l.provider_id) AS name, SUM(CAST(l.total_cost_usd AS REAL)) AS cost, COUNT(*)
    FROM proxy_request_logs l LEFT JOIN providers p ON p.id=l.provider_id AND p.app_type=l.app_type
    GROUP BY 1 ORDER BY cost DESC LIMIT 8"""):
        providers.append({"name": r[0][:18], "cost": round(r[1] or 0, 2), "requests": r[2]})

    raw_dates = [d["date"] for d in recent]
    db.close()
    return dict(
        meta=dict(generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
                  start=daily[0]["date"], end=daily[-1]["date"], days=len(daily),
                  raw_window=f"{min(raw_dates)} ~ {max(raw_dates)}", rawStart=min(raw_dates)),
        daily=daily, daily_model=daily_model, wd_hour=wd_hour,
        recent=recent, status=status, providers=providers)


def build_demo():
    """生成虚构演示数据：固定种子可复现，含模型切换叙事与使用节奏。"""
    rnd = random.Random(42)  # 固定种子：演示数据可复现（非加密用途）
    END = datetime(2026, 9, 2)
    dates = [(END - timedelta(days=94 - i)).strftime("%Y-%m-%d") for i in range(95)]
    # 模型剧本：窗口 + 权重曲线 + 单次请求均价 + token 特征
    models = [
        dict(name="nova-4-flash", win=(0, 42),  w=lambda t: 1.0 - 0.75*t,        unit=0.016, kin=6.5, kcr=6.0, kcc=0.20),
        dict(name="atlas-3",      win=(8, 62),  w=lambda t: 0.15 + 0.85*(1-abs(t-0.5)*2), unit=0.030, kin=7.2, kcr=7.5, kcc=0.30),
        dict(name="nova-4-pro",   win=(22, 94), w=lambda t: 0.1 + 0.9/(1+2.6**(-(t-0.5)/0.18)), unit=0.044, kin=7.8, kcr=8.2, kcc=0.32),
        dict(name="lumen-7b",     win=(48, 94), w=lambda t: 0.1 + 0.5*t,         unit=0.026, kin=5.6, kcr=5.0, kcc=0.18),
        dict(name="orion-mini",   win=(0, 94),  w=lambda t: 0.08,                 unit=0.008, kin=4.8, kcr=4.2, kcc=0.15),
    ]
    wf = {0: 1.05, 1: 1.12, 2: 1.15, 3: 1.00, 4: 0.92, 5: 0.50, 6: 0.42}  # 周一..周日
    daily, daily_model = [], []
    for i, d in enumerate(dates):
        dt = END - timedelta(days=94 - i)
        g = 0.15 + 0.80 / (1 + 2.718 ** (-(i - 45) / 16))
        cost_d = (18 + 165 * g) * wf[dt.weekday()] * rnd.uniform(0.85, 1.15)
        if i in (52, 74):
            cost_d *= 1.55
        act = [(m, m["w"]((i - m["win"][0]) / max(1, m["win"][1] - m["win"][0])))
               for m in models if m["win"][0] <= i <= m["win"][1] and m["w"]((i - m["win"][0]) / max(1, m["win"][1] - m["win"][0])) > 0.02]
        wsum = sum(w for _, w in act)
        okr = 0.885 if i in (39, 67) else rnd.uniform(0.945, 0.99)
        agg = dict(date=d, requests=0, success=0, in_tok=0, out_tok=0, cache_read=0, cache_create=0, cost=0.0)
        for m, w in act:
            c = cost_d * w / wsum
            req = int(c / m["unit"] * rnd.uniform(0.9, 1.1))
            in_t = int(req * m["kin"] * 1000 * rnd.uniform(0.85, 1.15))
            daily_model.append(dict(date=d, model=m["name"], requests=req, in_tok=in_t,
                                    out_tok=int(req * 1100 * rnd.uniform(0.7, 1.3)),
                                    cache_read=int(in_t * m["kcr"] * rnd.uniform(0.8, 1.2)),
                                    cache_create=int(in_t * m["kcc"] * rnd.uniform(0.6, 1.4)),
                                    cost=round(c, 4)))
            agg["requests"] += req; agg["in_tok"] += in_t
            agg["out_tok"] += int(req * 1100); agg["cache_read"] += int(in_t * m["kcr"]); agg["cache_create"] += int(in_t * m["kcc"])
            agg["cost"] += c
        agg["success"] = int(agg["requests"] * okr)
        agg["cost"] = round(agg["cost"], 4)
        daily.append(agg)

    wd_hour_base = [30, 22, 15, 8, 5, 4, 6, 10, 18, 30, 48, 66, 72, 60, 52, 58, 64, 70, 62, 48, 40, 55, 68, 45]
    raw_reqs = sum(d["requests"] for d in daily[-28:])
    cells = [[wd_hour_base[h] * (0.55 if wd >= 5 and 8 <= h <= 19 else 0.85 if wd >= 5 else 1.0)
              for h in range(24)] for wd in range(7)]
    f = raw_reqs / (4 * sum(sum(r) for r in cells))
    wd_hour = [[int(c * f) for c in row] for row in cells]

    recent = [dict(date=d["date"], requests=d["requests"], ok=d["success"],
                   cost=d["cost"], latency=round((15.2 if d["date"] == dates[67] else rnd.uniform(7.2, 12.5)), 2))
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
                  dataSource="演示数据 · 虚构 Demo", demo=True),
        daily=daily, daily_model=daily_model, wd_hour=wd_hour,
        recent=recent, status=status, providers=providers)


data = build_demo() if "--demo" in sys.argv else build_real()

with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
    tpl = f.read()
with open(os.path.join(HERE, "echarts.min.js"), encoding="utf-8") as f:
    ech = f.read()
assert "</script>" not in ech, "echarts 含 </script>，需处理"
sys.stdout.write(tpl.replace("__ECHARTS_JS__", ech).replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False)))

tc = sum(d["cost"] for d in data["daily"]); tr = sum(d["requests"] for d in data["daily"])
log(f"模式: {'演示假数据' if data['meta'].get('demo') else '真实数据库'}")
log(f"日期 {data['meta']['start']} ~ {data['meta']['end']} ({len(data['daily'])} 天)")
log(f"总消费 ${tc:,.2f} | 总请求 {tr:,}")
