"""Re-solve the centre-screen pose for the VIEW: the whole screen must sit above the 2D bottom bars
(bottom-left corner <= y 855, bottom-right <= y 892 on a 1600x900 view) while keeping >= 12 mm of
cabin clearance (same test as place_cs.py), with the top edge as low as possible (least windshield
occlusion). The cockpit camera (pitch/yaw) was fitted to measured click->artboard picks (2.6 px).
usage: place_cs_view.py"""
import math
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import make_car as mc  # noqa: E402

W, H = 0.21, 0.28
YAW = -0.52
X = 0.115
EYE = np.array([-0.37, 1.13, 0.22])
CAM_PITCH, CAM_YAW = math.radians(0.5), math.radians(0.5)   # fitted
YFOV = math.radians(68)


def l2c(q, pos, yaw, pitch):
    x, y, z = q[:, 0], q[:, 1], q[:, 2]
    cp, sp = math.cos(pitch), math.sin(pitch)
    y2 = y * cp - z * sp
    z2 = y * sp + z * cp
    cy, sy = math.cos(yaw), math.sin(yaw)
    return np.stack([x * cy + z2 * sy, y2, -x * sy + z2 * cy], -1) + np.array(pos)


def proj(P, w=1600, h=900):
    d = P - EYE
    cy, sy = math.cos(CAM_YAW), math.sin(CAM_YAW)
    x = d[:, 0] * cy + d[:, 2] * sy
    z = d[:, 2] * cy - d[:, 0] * sy
    y = d[:, 1]
    cp, sp = math.cos(CAM_PITCH), math.sin(CAM_PITCH)
    y2 = y * cp + z * sp
    zf = -z * cp + y * sp
    t = math.tan(YFOV / 2)
    return np.stack([(x / (zf * t * w / h) * 0.5 + 0.5) * w, (0.5 - y2 / (zf * t) * 0.5) * h], -1)


C = np.array([[0, 0], [720, 0], [0, 960], [720, 960]], float)
QC = np.stack([(C[:, 0] / 720 - 0.5) * W, (0.5 - C[:, 1] / 960) * H, np.zeros(4)], -1)
gx, gy = np.meshgrid(np.linspace(-W / 2 - 0.015, W / 2 + 0.015, 13), np.linspace(-H / 2 - 0.015, H / 2 + 0.015, 13))
PTS = np.concatenate([np.stack([gx.ravel(), gy.ravel(), np.full(gx.size, zz)], -1) for zz in (0.0, -0.022, -0.045)])

print("current", np.round(proj(l2c(QC, (X, 0.8425, -0.37), YAW, -0.20))).astype(int).tolist())
res = []
for pitch in np.arange(-0.40, 0.11, 0.05):
    for z in np.arange(-0.46, -0.299, 0.02):
        for y in np.arange(0.84, 1.02, 0.005):
            S = proj(l2c(QC, (X, y, z), YAW, pitch))
            if S[2, 1] > 855 or S[3, 1] > 892 or S[:, 0].max() > 1590:
                continue
            cl = mc.cabin_scene(l2c(PTS, (X, y, z), YAW, pitch)).min()
            if cl < 0.012:
                continue
            res.append((-(S[0, 1] + S[1, 1]) / 2, round(pitch, 2), round(z, 2), round(y, 3), round(cl * 1000, 1),
                        np.round(S).astype(int).tolist()))
            break
res.sort()
for r in res[:10]:
    print(r)
print(len(res), "feasible")
