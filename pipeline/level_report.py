#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""等级出口报告：各域 等级分布 + 与吉凶出口的对照（看梯度是否恢复）"""
import sqlite3, json
from collections import defaultdict, Counter

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
con = sqlite3.connect(DB); cur = con.cursor()

pol = defaultdict(Counter)
lvl = defaultdict(Counter)
for (d, l) in cur.execute("select verdict_domains, verdict_level from case_features where verdict_domains!=''"):
    try:
        dj = json.loads(d)
    except Exception:
        continue
    try:
        lj = json.loads(l) if l else {}
    except Exception:
        lj = {}
    for k, v in dj.items():
        pol[k][v.get("pol", "?")] += 1
        if k in lj:
            lvl[k][lj[k]] += 1

print("=" * 72)
print("域        吉/凶出口              等级出口（0=最下 … 5=最上）")
print("=" * 72)
for k in sorted(pol, key=lambda x: -sum(pol[x].values())):
    c = pol[k]
    g, x, m = c["吉"], c["凶"], c["混"]
    pure = g + x
    rate = f"{x / pure * 100:.0f}%凶" if pure else "—"
    L = lvl.get(k)
    if L:
        tot = sum(L.values())
        dist = " ".join(f"{i}:{L.get(i, 0)}" for i in range(0, 6) if L.get(i, 0))
        # 分布是否真有梯度：非零档位数 + 最高档占比
        nz = len([i for i in range(6) if L.get(i, 0)])
        top = max(L, key=lambda i: L[i])
        print(f"{k:<9} n={sum(c.values()):<4} {rate:<7}   n={tot:<3} 档位{nz}/6  {dist}   众数={top}")
    else:
        print(f"{k:<9} n={sum(c.values()):<4} {rate:<7}   无量表")

print()
print("=" * 72)
print("等级梯度检验：分布均匀度（熵归一化，1=完全均匀/最有信息，0=全挤一档）")
print("=" * 72)
import math
for k, L in lvl.items():
    tot = sum(L.values())
    if tot < 20:
        continue
    nz = [v for v in L.values() if v]
    H = -sum((v / tot) * math.log(v / tot) for v in nz)
    Hmax = math.log(6)
    print(f"{k:<9} n={tot:<4} H/Hmax={H/Hmax:.3f}  众数占{max(nz)/tot*100:.0f}%")
con.close()
