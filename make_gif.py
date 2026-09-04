# -*- coding: utf-8 -*-
"""把整页演示截图按功能分组裁剪、合成多张分功能演示 GIF（输出到 demo/ 目录）。"""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FR = os.path.join(HERE, "preview", "frames")
OUT = os.path.join(HERE, "demo")
os.makedirs(OUT, exist_ok=True)
H = 810

# 每组 GIF: (文件名, [(整页图, 裁剪y, 时长ms), ...])
# 裁剪y = 各帧锚点在 1440 宽布局下的绝对偏移（template.html applyFrame 经 title OFF: 上报）
GIFS = [
    ("01-overview-range.gif", [("full0.png", 0,   2200), ("full4.png", 0,   3000)]),
    ("02-trend-zoom.gif",     [("full1.png", 448, 1600), ("full2.png", 448, 2000), ("full3.png", 448, 2200)]),
    ("03-models.gif",         [("full5.png", 940, 1600), ("full6.png", 940, 2000), ("full7.png", 940, 2200)]),
    ("04-token-provider.gif", [("full8.png", 1367, 2000), ("full9.png", 1367, 2200)]),
    ("05-rhythm-quality.gif", [("full10.png", 1794, 2200), ("full11.png", 2201, 2400)]),
    ("06-table-sort.gif",     [("full12.png", 2658, 2000), ("full13.png", 2658, 2800)]),
]

for name, frames in GIFS:
    imgs = []
    for fn, y, _ in frames:
        im = Image.open(os.path.join(FR, fn)).convert("RGB")
        imgs.append(im.crop((0, y, im.width, y + H)).quantize(colors=256, method=Image.MEDIANCUT))
    out = os.path.join(OUT, name)
    imgs[0].save(out, save_all=True, append_images=imgs[1:],
                 duration=[d for _, _, d in frames], loop=0, optimize=True)
    print("%-24s %d 帧  %.2f MB  %.1fs" % (name, len(imgs), os.path.getsize(out) / 1e6,
                                           sum(d for _, _, d in frames) / 1000))
