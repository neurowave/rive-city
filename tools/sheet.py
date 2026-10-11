#!/usr/bin/env python3
"""Contact sheet: sheet.py out.jpg cols scale img1 img2 ..."""
import sys
from PIL import Image

out, cols, scale = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
ims = []
for p in sys.argv[4:]:
    im = Image.open(p).convert("RGBA")
    bg = Image.new("RGBA", im.size, (40, 40, 40, 255))
    bg.alpha_composite(im)
    ims.append(bg.convert("RGB").resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS))
w, h = ims[0].size
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (w * cols, h * rows), (0, 0, 0))
for i, im in enumerate(ims):
    sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.save(out, quality=90)
print(out, sheet.size)
