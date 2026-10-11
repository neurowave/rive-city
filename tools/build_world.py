import glob, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parts = sorted(glob.glob(os.path.join(ROOT, "tools", "world_parts", "*.as.part")))
open(os.path.join(ROOT, "world.as"), "w").write("".join(open(p).read() for p in parts))
print("world.as", sum(1 for p in parts for _ in open(p)), "lines")
