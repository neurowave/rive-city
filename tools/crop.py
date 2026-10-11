#!/usr/bin/env python3
"""crop.py in.png out.jpg x0 y0 x1 y1 [scale]"""
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB")
x0, y0, x1, y1 = map(int, sys.argv[3:7])
s = float(sys.argv[7]) if len(sys.argv) > 7 else 1.0
c = im.crop((x0, y0, x1, y1))
if s != 1.0:
    c = c.resize((int(c.width * s), int(c.height * s)), Image.LANCZOS)
c.save(sys.argv[2], quality=92)
print(sys.argv[2], c.size)
