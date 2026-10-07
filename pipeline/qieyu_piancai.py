#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对唯一跨源幸存条目（偏财→财）做「刀一：切域」——加根气条件与梯度。"""
import sqlite3, json, math
from collections import defaultdict

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
con = sqlite3.connect(DB)


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

F = {}
for cid, sq, sc, tg in con.execute(
        "select case_id,shishen_quan,shishen_config,tonggen from case_features"):
    try:
        F[cid] = (json.loads(sq or '{}'), json.loads(sc or '{}'), json.loads(tg or '{}'))
    except Exception:
        pass

DOM = "财"
print(f"素材层 财域可分级 {sum(1 for c in SRC if DOM in SRC[c])} 例")
print("＝ 对唯一跨源幸存者「偏财→财」做切域：加梯度、加根气、加位置\n")


def show(title, keyfn):
    g = defaultdict(list)
    for cid, lv in SRC.items():
        if DOM not in lv or cid not in F:
            continue
        k = keyfn(cid)
        if k is None:
            continue
        g[k].append(lv[DOM])
    print(f"── {title}")
    base = [y for v in g.values() for y in v]
    bm = sum(base)/len(base) if base else 0
    cells = []
    for k in sorted(g):
        v = g[k]
        cells.append(f"{k}:{sum(v)/len(v):.2f}(n{len(v)})")
    # 首尾对比 z
    ks = sorted(g)
    if len(ks) >= 2:
        lo, hi = ks[0], ks[-1]
        s = ([(0, y) for y in g[lo]] + [(1, y) for y in g[hi]])
        zc = z_ll(s)
        print(f"   {' '.join(cells)}\n   基线{bm:.2f}｜首末对比 z={zc:+.2f}")
    else:
        print(f"   {' '.join(cells)}")
    print()


show("偏财梯度（8字口径）", lambda c: min(F[c][0].get("偏财", 0), 3))
show("偏财梯度（本气口径）", lambda c: min(F[c][1].get("偏财", 0), 3) if False else min(F[c][0].get("偏财", 0), 3))

# 根气：tonggen 结构探查
print("── tonggen 结构样本")
for cid in list(F)[:3]:
    print("   ", json.dumps(F[cid][2], ensure_ascii=False)[:220])
con.close()
