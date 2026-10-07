#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
尺子裁判 v2：用「分事类结果」重跑 天干口径 vs 8字口径（含地支根）
v1 教训：拿粗「凶率」当判据 → 出口糊，测不出。现出口已修（verdict_domains 事类×极性）。
本 v2 做两件：
  A. 嵌套比较（核心）：天干有X 且 地支有根 vs 无根 → 看对应事类的凶率差
  B. 双尺并列：天干口径 X 计数分档 vs 8字口径 X 计数分档 → 谁的超额更大
判据仍是压缩法：哪个尺子把可能性空间压得更小（超额更大 + 过可检出线）。
"""
import sqlite3, json, math
from collections import defaultdict

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
con = sqlite3.connect(DB)

# 十神 → 对应事类（经典说法所在域）
PAIR = [("正官", "功名事业"), ("七杀", "功名事业"), ("正印", "功名事业"), ("偏印", "功名事业"),
        ("正财", "财"), ("偏财", "财"), ("伤官", "婚姻"), ("伤官", "刑灾官非"),
        ("食神", "寿元健康"), ("七杀", "刑灾官非")]

rows = []
for cid, sc, sq, tg, vd in con.execute(
        "select case_id,shishen_config,shishen_quan,tonggen,verdict_domains from case_features where verdict_domains!=''"):
    try:
        rows.append((json.loads(sc or '{}'), json.loads(sq or '{}'),
                     json.loads(tg or '{}'), json.loads(vd)))
    except Exception:
        pass
print(f"可用样本（有分级结局）{len(rows)}\n")


def wilson_baseline(dom):
    n = sum(1 for *_, vd in rows if dom in vd)
    x = sum(1 for *_, vd in rows if dom in vd and vd[dom]["pol"] == "凶")
    return (x / n if n else 0), n


def check(dom, sel):
    """sel(row)->bool ；返回 (n, 凶率)"""
    n = x = 0
    for sc, sq, tg, vd in rows:
        if dom in vd and sel((sc, sq, tg, vd)):
            n += 1
            if vd[dom]["pol"] == "凶":
                x += 1
    return n, (x / n if n else 0)


def ztest(a, na, b, nb):
    if not na or not nb:
        return 0
    p = (a * na + b * nb) / (na + nb)
    se = math.sqrt(p * (1 - p) * (1 / na + 1 / nb))
    return (a - b) / se if se else 0


def detect_line(base, p0):
    return 2.8 * math.sqrt(2 * p0 * (1 - p0) / 117)

print("【A】嵌套比较：天干有X，再切「地支有无根」→ 对应事类凶率")
print(f"{'十神':<5}{'事类':<9}{'基线':>7}{'有根n':>7}{'有根凶率':>9}{'无根n':>7}{'无根凶率':>9}{'差':>8}{'z':>7}")
for god, dom in PAIR:
    b, bn = wilson_baseline(dom)
    n1, p1 = check(dom, lambda r: r[0].get(god, 0) > 0 and r[2].get(god))
    n0, p0 = check(dom, lambda r: r[0].get(god, 0) > 0 and not r[2].get(god))
    if n1 < 8 or n0 < 8:
        continue
    d = (p1 - p0) * 100
    z = ztest(p1, n1, p0, n0)
    flag = "★" if abs(z) > 1.96 else " "
    print(f"{god:<5}{dom:<9}{b*100:>6.1f}%{n1:>7}{p1*100:>8.1f}%{n0:>7}{p0*100:>8.1f}%{d:>+7.1f}pp{z:>7.2f}{flag}")
print(f"（可检出线参考：以 p0≈0.4、每臂 117 计 ≈ {detect_line(0.4,0.4)*100:.1f}pp）\n")

print("【B】双尺并列：X 计数分档 → 对应事类凶率（看谁单调/谁压得动）")
for god, dom in PAIR:
    print(f"\n-- {god} × {dom} --")
    for name, key in (("天干口径", 0), ("8字口径", 1)):
        buckets = defaultdict(lambda: [0, 0])
        for sc, sq, tg, vd in rows:
            if dom not in vd:
                continue
            k = min(sc.get(god, 0) if key == 0 else sq.get(god, 0), 3)
            buckets[k][1] += 1
            if vd[dom]["pol"] == "凶":
                buckets[k][0] += 1
        cells = [f"{k}档:{v[0]/v[1]*100:.0f}%(n={v[1]})" for k, v in sorted(buckets.items()) if v[1] >= 15]
        print(f"   {name}: " + "  ".join(cells))
con.close()
