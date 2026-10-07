#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压缩法实验：**同一条格局，换三档收紧的口径**，看压缩率（|z|）是否上升。

这是对方法论本身（而非某条理论）的检验：
  压缩法主张「宽域压不动时，不要撤回条目，要去切条件；压不动 = 域切得不够细」。
  三档口径天然构成「域由宽到窄」：
    L1 天干尺     —— 只算 4 个天干（最宽：任何盘都有天干十神）
    L2 八字尺     —— 8 字含藏干（当前主尺）
    L3 本气尺     —— 只算地支本气（最严：藏干杂气全不算）
判据：若「切域提升压缩率」为真，则 命中率 应 递减、而 |z| 应 递增。
"""
import sqlite3, json, math

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
con = sqlite3.connect(DB)


def gg(s, *names):
    return sum(s.get(n, 0) for n in names)


PREREG = [
    ("官印相生", "功名事业", +1, lambda s: gg(s, "正官", "七杀") >= 1 and gg(s, "正印", "偏印") >= 1),
    ("官印相生-严", "功名事业", +1, lambda s: gg(s, "正官", "七杀") >= 2 and gg(s, "正印", "偏印") >= 2),
    ("杀印相生", "功名事业", +1, lambda s: s.get("七杀", 0) >= 1 and gg(s, "正印", "偏印") >= 1),
    ("财旺生官", "功名事业", +1, lambda s: gg(s, "正财", "偏财") >= 2 and gg(s, "正官", "七杀") >= 1),
    ("财官双美-严", "功名事业", +1, lambda s: gg(s, "正财", "偏财") >= 2 and gg(s, "正官", "七杀") >= 2),
    ("比劫夺财", "财", -1, lambda s: gg(s, "比肩", "劫财") >= 2 and gg(s, "正财", "偏财") >= 1),
    ("比劫夺财-严", "财", -1, lambda s: gg(s, "比肩", "劫财") >= 3 and gg(s, "正财", "偏财") >= 1),
    ("食神生财", "财", +1, lambda s: s.get("食神", 0) >= 1 and gg(s, "正财", "偏财") >= 1),
    ("伤官生财", "财", +1, lambda s: s.get("伤官", 0) >= 1 and gg(s, "正财", "偏财") >= 2),
    ("伤官见官", "婚姻", -1, lambda s: s.get("伤官", 0) >= 1 and s.get("正官", 0) >= 1),
    ("伤官见官-严", "婚姻", -1, lambda s: s.get("伤官", 0) >= 2 and s.get("正官", 0) >= 1),
]


def z_ll(s):
    N = len(s)
    if N < 12:
        return 0.0
    Sb = sum(b for b, _ in s); Sy = sum(y for _, y in s)
    Sbb = sum(b*b for b, _ in s); Syy = sum(y*y for _, y in s)
    Sby = sum(b*y for b, y in s)
    var = (Sbb - Sb*Sb/N) * (Syy - Sy*Sy/N) / (N - 1)
    if var <= 0:
        return 0.0
    return (Sby - Sb*Sy/N) / math.sqrt(var)


SRC = {}
for cid, vd, vl in con.execute("select case_id,verdict,level from case_outcomes"):
    if vd:
        try:
            SRC[cid] = json.loads(vl or '{}')
        except Exception:
            pass

# 三档口径
KJ = {"L1天干": "shishen_config", "L2八字": "shishen_quan", "L3本气": "shishen_benqi"}
SH = {k: {} for k in KJ}
for k, col in KJ.items():
    for cid, sq in con.execute(f"select case_id,{col} from case_features"):
        try:
            SH[k][cid] = json.loads(sq or '{}')
        except Exception:
            pass

print(f"源：素材层（巾箱原文）{len(SRC)} 例")
print("检验：「切域提升压缩率」——同一格局换三档口径，命中率应降、|z| 应升\n")
print(f"{'格局':<14}{'域':<6}{'口径':<8}{'命中率':>7}{'n1':>5}{'Δ等级':>8}{'z':>7}")
print("-" * 70)

summary = []
for name, dom, exp, pred in PREREG:
    line = []
    for k in KJ:
        s = []
        for cid, lv in SRC.items():
            if dom not in lv or cid not in SH[k]:
                continue
            s.append((1 if pred(SH[k][cid]) else 0, lv[dom]))
        n1 = sum(b for b, _ in s)
        n0 = len(s) - n1
        if n1 < 8 or n0 < 8:
            line.append((k, None, n1, len(s), None, None))
            continue
        m1 = sum(y for b, y in s if b == 1)/n1
        m0 = sum(y for b, y in s if b == 0)/n0
        line.append((k, n1/len(s), n1, len(s), m1-m0, z_ll(s)))
    for k, hr, n1, nn, d, z in line:
        if z is None:
            print(f"{name:<14}{dom:<6}{k:<8}{'—':>7}{n1:>5}{'样本不足':>8}")
        else:
            tag = " ★" if abs(z) > 2.81 else (" ○" if abs(z) > 1.96 else "")
            print(f"{name:<14}{dom:<6}{k:<8}{hr:>7.1%}{n1:>5}{d:>+8.2f}{z:>7.2f}{tag}")
    zs = [x[5] for x in line if x[5] is not None]
    hrs = [x[1] for x in line if x[1] is not None]
    if len(zs) >= 2:
        up = abs(zs[-1]) > abs(zs[0])
        down = hrs[-1] < hrs[0]
        summary.append((name, hrs, zs, up, down))
    print()

print("=" * 70)
print("压缩率是否随口径收紧而上升？")
print("=" * 70)
up_n = down_n = tot = 0
for name, hrs, zs, up, down in summary:
    tot += 1
    up_n += up; down_n += down
    print(f"  {name:<14}命中率 {'→'.join(f'{h:.0%}' for h in hrs):<22}|z| {'→'.join(f'{abs(z):.2f}' for z in zs):<22}"
          f"{'压缩↑' if up else '压缩↓'}{'｜条件收窄' if down else '｜条件没收窄'}")
print(f"\n  {tot} 条中：条件确实收窄 {down_n} 条；|z| 上升 {up_n} 条")
con.close()
