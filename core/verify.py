# -*- coding: utf-8 -*-
"""看板验收助手：无头 Chrome 截图 + 控制台错误检查。
用法: python core/verify.py <html绝对路径> [窗口高度] [hash锚点]
输出: preview/<html文件名>.png，控制台有错误则以非零码退出。
"""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def main():
    html = os.path.abspath(sys.argv[1])
    height = sys.argv[2] if len(sys.argv) > 2 else "1600"
    anchor = sys.argv[3] if len(sys.argv) > 3 else "#kpis"
    name = os.path.splitext(os.path.basename(html))[0]
    out_dir = os.path.join(os.path.dirname(HERE), "preview")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{name}.png")
    url = "file:///" + quote(Path(html).as_posix()) + (anchor if anchor else "")
    tmp = tempfile.mkdtemp()
    proc = subprocess.run([
        CHROME, "--headless=new", "--disable-gpu",
        f"--user-data-dir={tmp}", "--hide-scrollbars",
        "--force-device-scale-factor=1", "--force-prefers-reduced-motion",
        f"--window-size=1920,{height}", "--virtual-time-budget=6000",
        "--enable-logging=stderr", "--v=0",
        f"--screenshot={out}", url,
    ], capture_output=True, text=True, errors="ignore")
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    errs = [l for l in (proc.stderr or "").splitlines()
            if re.search(r'CONSOLE.*(error|uncaught)', l, re.I)]
    ok = os.path.exists(out) and os.path.getsize(out) > 50000 and not errs
    print(f"截图: {out} ({os.path.getsize(out) if os.path.exists(out) else 0} bytes)")
    for l in errs:
        print("控制台错误:", l[:200])
    print("结论:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
