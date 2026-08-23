#!/usr/bin/env python3
from pathlib import Path
import re
from PIL import Image, ImageDraw

source = Path(".tmp/axian-bom/render4")
files = sorted(source.glob("page-*.png"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1)))
thumb_w = 360
label_h = 28
gap = 16
cols = 3
thumbs = []
for path in files:
    image = Image.open(path).convert("RGB")
    height = round(image.height * thumb_w / image.width)
    thumbs.append((path, image.resize((thumb_w, height))))
cell_h = max(image.height for _, image in thumbs) + label_h
rows = (len(thumbs) + cols - 1) // cols
canvas = Image.new("RGB", (cols * (thumb_w + gap) + gap, rows * (cell_h + gap) + gap), "white")
draw = ImageDraw.Draw(canvas)
for index, (path, image) in enumerate(thumbs):
    row, col = divmod(index, cols)
    x = gap + col * (thumb_w + gap)
    y = gap + row * (cell_h + gap)
    draw.text((x, y), path.stem, fill="black")
    canvas.paste(image, (x, y + label_h))
canvas.save(".tmp/axian-bom/contact4.png")
