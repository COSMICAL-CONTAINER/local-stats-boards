# -*- coding: utf-8 -*-
"""把 cc-switch 数据库中的用量数据导出为 CSV（打印到 stdout，重定向保存）。

用法:
  python export.py daily  > usage_daily.csv    合并后的每日汇总（日汇总表 ∪ 近30天明细）
  python export.py models > usage_models.csv   每日 × 模型汇总
  python export.py logs   > request_logs.csv   近 30 天逐请求明细

本脚本只读数据库、不写任何文件；CSV 以 UTF-8 带 BOM 输出，Excel 双击打开不乱码。
"""
import sqlite3, os, sys, io, csv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8-sig')  # 带 BOM，Excel 直开
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

HOME = os.path.expanduser("~")
DB = os.path.join(HOME, ".cc-switch", "cc-switch.db")

if not os.path.exists(DB):
    print(f"未找到 cc-switch 数据库：{DB}", file=sys.stderr)
    sys.exit(1)

SUB = sys.argv[1] if len(sys.argv) > 1 else ""
if SUB not in ("daily", "models", "logs"):
    print(__doc__, file=sys.stderr)
    sys.exit(1 if SUB else 0)

db = sqlite3.connect(DB)
w = csv.writer(sys.stdout)

if SUB == "daily":
    w.writerow(["日期", "请求数", "成功数", "成功率", "输入Token", "输出Token",
                "缓存读Token", "缓存写Token", "总Token", "费用USD"])
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
        req, ok = r[1] or 0, r[2] or 0
        w.writerow([r[0], req, ok, f"{ok/req*100:.1f}%" if req else "-",
                    r[3] or 0, r[4] or 0, r[5] or 0, r[6] or 0,
                    (r[3] or 0)+(r[4] or 0)+(r[5] or 0)+(r[6] or 0),
                    f"{(r[7] or 0):.4f}"])

elif SUB == "models":
    w.writerow(["日期", "模型", "请求数", "输入Token", "输出Token",
                "缓存读Token", "缓存写Token", "费用USD"])
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
    ) GROUP BY date, model ORDER BY date, model"""):
        w.writerow([r[0], r[1], r[2] or 0, r[3] or 0, r[4] or 0,
                    r[5] or 0, r[6] or 0, f"{(r[7] or 0):.6f}"])

elif SUB == "logs":
    w.writerow(["请求ID", "本地时间", "应用", "供应商ID", "模型", "请求模型",
                "输入Token", "输出Token", "缓存读Token", "缓存写Token",
                "费用USD", "延迟ms", "状态码", "流式", "数据来源", "会话ID"])
    for r in db.execute("""
    SELECT request_id, datetime(created_at,'unixepoch','localtime'), app_type, provider_id,
           model, request_model, input_tokens, output_tokens, cache_read_tokens,
           cache_creation_tokens, total_cost_usd, latency_ms, status_code,
           is_streaming, data_source, session_id
    FROM proxy_request_logs ORDER BY created_at"""):
        w.writerow(r)

db.close()
print(f"已输出 {SUB} 数据到 stdout", file=sys.stderr)
