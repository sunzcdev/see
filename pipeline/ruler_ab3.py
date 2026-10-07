#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
尺子裁判 v3：趋势检验 + 分半复现（防「格子多就好看」）
只测有真实梯度的域：财（基线凶率 39.7%，吉凶都有）
Cochran-Armitage 趋势检验：对分档做加权线性趋势，比「低档 vs 高档」两两比更省样本
分半复现：奇/偶 case_id 各跑一遍，方向不一致 = 不稳，不认
"""
import sqlite3, json, math

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
con = sqlite3.connect(DB)

rows = []
for cid, sc, sq, vd in con.execute(
        "select case_id,shishen_config,shishen_quan,verdict_domains from case_features where verdict_domains!=''"):
    try:
        rows.append((cid, json.loads(sc or '{}'), json.loads(sq or '{}'), json.loads(vd)))
    except Exception:
        pass

GODS = ["比肩", "劫财", "食神", "伤官", "正财", "偏财", "正官", "七杀", "正印", "偏印"]
DOM = "财"


def trend(pairs):
    """pairs=[(bucket, n, x)] → (N, 凶率, z趋势)"""
    N = sum(n for _, n, _ in pairs)
    X = sum(x for _, _, x in pairs)
    if N == 0:
        return 0, 0, 0
    p = X / N
    if p in (0, 1):
        return N, p, 0
    Sw = sum(n * b for b, n, _ in pairs)
    Sww = sum(n * b * b for b, n, _ in pairs)
    Swx = sum(b * x for b, _, x in pairs)
    denom = p * (1 - p) * (Sww - Sw * Sw / N)
    if denom <= 0:
        return N, p, 0
    z = (Swx - p * Sw) / math.sqrt(denom)
    return N, p, z


def run(sel, label):
    print(f"\n{label}")
    print(f"{'十神':<5}{'尺':<9}{'分档凶率（n）':<58}{'N':>5}{'趋势z':>8}  分半")
    for god in GODS:
        for ui, rname in ((1, "天干口径"), (2, "8字口径")):
            buckets = {}
            for cid, sc, sq, vd in rows:
                if DOM not in vd or not sel(cid):
                    continue
                k = min(sc.get(god, 0) if ui == 1 else sq.get(god, 0), 3)
                b = buckets.setdefault(k, [0, 0])
                b[1] += 1
                if vd[DOM]["pol"] == "凶":
                    b[0] += 1
            pairs = [(k, v[1], v[0]) for k, v in sorted(buckets.items()) if v[1] >= 8]
            if len(pairs) < 2:
                continue
            N, p, z = trend(pairs)
            # 分半
            hs = []
            for parity in (0, 1):
                p2 = [(k, v[1], v[0]) for k, v in sorted(buckets.items())
                      if v[1] >= 4 and (k % 2) == parity or True]
                tmp = {}
                for cid, sc, sq, vd in rows:
                    if DOM not in vd or not sel(cid) or (cid % 2) != parity:
                        continue
                    k = min(sc.get(god, 0) if ui == 1 else sq.get(god, 0), 3)
                    b = tmp.setdefault(k, [0, 0])
                    b[1] += 1
                    if vd[DOM]["pol"] == "凶":
                        b[0] += 1
                pr = [(k, v[1], v[0]) for k, v in sorted(tmp.items()) if v[1] >= 6]
                hs.append(trend(pr)[2] if len(pr) >= 2 else 0)
            same = "同" if (hs[0] > 0) == (hs[1] > 0) and hs[0] != 0 and hs[1] != 0 else "✗"
            star = "★" if abs(z) > 1.96 and same == "同" else ""
            cells = " ".join(f"{k}:{v[0]/v[1]*100:.0f}%({v[1]})" for k, v in sorted(buckets.items()) if v[1] >= 8)
            print(f"{god:<5}{rname:<9}{cells:<58}{N:>5}{z:>8.2f}  {hs[0]:+.1f}/{hs[1]:+.1f} {same}{star}")


run(lambda cid: True, "【全样本】财域 凶率 分档 × 趋势检验")
run(lambda cid: cid % 2 == 0, "【半样本·偶】")
run(lambda cid: cid % 2 == 1, "【半样本·奇】")
con.close()
