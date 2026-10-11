"""Solve the centre-screen placement: the lowest mount (least windshield
occlusion) where the whole screen + housing clears the dash and the door
cards by >= CLEAR metres. Prints the pose and where a neck meets the dash."""
import math
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import make_car as mc  # noqa: E402

W, H = 0.21, 0.28
YAW, PITCH = -0.52, -0.20
X = 0.115
CLEAR = 0.012


def local_to_car(q, pos, yaw=YAW, pitch=PITCH):
    x, y, z = q[:, 0], q[:, 1], q[:, 2]
    cp, sp = math.cos(pitch), math.sin(pitch)
    y2 = y * cp - z * sp
    z2 = y * sp + z * cp
    cy, sy = math.cos(yaw), math.sin(yaw)
    x3 = x * cy + z2 * sy
    z3 = -x * sy + z2 * cy
    return np.stack([x3, y2, z3], -1) + np.array(pos)


gx, gy = np.meshgrid(np.linspace(-W / 2 - 0.015, W / 2 + 0.015, 17), np.linspace(-H / 2 - 0.015, H / 2 + 0.015, 17))
pts = np.concatenate([np.stack([gx.ravel(), gy.ravel(), np.full(gx.size, zz)], -1) for zz in (0.0, -0.022, -0.045)])

best = None
TABLE = []
for z in np.arange(-0.62, -0.299, 0.01):
    for y in np.arange(0.80, 1.10, 0.0025):
        cp = local_to_car(pts, (X, y, z))
        cl = mc.cabin_scene(cp).min()
        if cl >= CLEAR:
            TABLE.append((round(z, 3), round(y, 4)))
            if best is None or y < best[1] - 1e-9:
                best = (z, y, cl)
            break
print(TABLE)
if len(sys.argv) > 1:
    z = float(sys.argv[1])
    y = dict(TABLE)[round(z, 3)]
    cl = mc.cabin_scene(local_to_car(pts, (X, y, z))).min()
else:
    z, y, cl = best
print(f"pose x={X} y={y:.4f} z={z:.3f} clearance={cl * 1000:.1f}mm")
# neck: from the housing back centre straight forward (car -z) into the dash face
top = local_to_car(np.array([[0.0, -0.02, -0.04]]), (X, y, z))[0]
for dz in np.arange(0, 0.5, 0.002):
    p = top - np.array([0, 0, dz])
    if mc.cabin_scene(p[None])[0] < -0.015:
        break
print("neck_top", np.round(top, 4).tolist(), "neck_bottom", np.round(p, 4).tolist())
