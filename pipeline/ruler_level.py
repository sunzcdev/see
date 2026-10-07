#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
尺子裁判 v4：结局改用「等级出口」（序数），替代已单极化的吉/凶出口。
统计量：linear-by-linear 关联 z（序数×序数，等价秩相关）
        z = (Σb·y - Sb·Sy/N) / sqrt( (Sbb-Sb²/N)(Syy-Sy²/N)/(N-1) )
分半复现 + Bonferroni 校正（K 个检验，红线 z=Φ⁻¹(1-0.025/K)）
"""
import sqlite3, json, math
from collections import defaultdict

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
con = sqlite3.connect(DB)

rows = []
for cid, sc, sq, vd, vl in con.execute(
        "select case_id,shishen_config,shishen_quan,verdict_domains,verdict_level from case_features "
        "where verdict_domains!=''"):
    try:
        rows.append((cid, json.loads(sc or '{}'), json.loads(sq or '{}'),
                     json.loads(vd), json.loads(vl or '{}')))
    except Exception:
        pass

GODS = ["比肩", "劫财", "食神", "伤官", "正财", "偏财", "正官", "七杀", "正印", "偏印"]
DOMS = ["功名事业", "财", "婚姻", "寿元健康"]
RULERS = [(1, "天干"), (2, "8字")]


def z_ll(samples):
    """samples=[(b,y)] 序数×序数 → z"""
    N = len(samples)
    if N < 12:
        return 0.0
    Sb = sum(b for b, _ in samples); Sy = sum(y for _, y in samples)
    Sbb = sum(b * b for b, _ in samples); Syy = sum(y * y for _, y in samples)
    Sby = sum(b * y for b, y in samples)
    var = (Sbb - Sb * Sb / N) * (Syy - Sy * Sy / N) / (N - 1)
    if var <= 0:
        return 0.0
    return (Sby - Sb * Sy / N) / math.sqrt(var)


def collect(god, ui, dom, sel=None):
    out = []
    for cid, sc, sq, vd, vl in rows:
        if sel and not sel(cid):
            continue
        if dom not in vl:
            continue
        src = sc if ui == 1 else sq
        b = min(src.get(god, 0), 3)
        out.append((b, vl[dom]))
    return out


K = len(DOMS) * len(GODS) * len(RULERS)
# Φ⁻¹(1-0.025/K) 近似（Acklam 有理逼近）
def norm_ppf(p):
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl = 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > 1 - pl:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5; r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


RED = norm_ppf(1 - 0.025 / K)
print(f"检验数 K={K}；Bonferroni 红线 z={RED:.2f}；名义线 1.96\n")

survivors = []
for dom in DOMS:
    print("=" * 96)
    print(f"【{dom}】等级出口（0=最下 … 5=最上）")
    print("=" * 96)
    print(f"{'十神':<5}{'尺':<6}{'分档 均值(等级) n':<46}{'N':>5}{'z':>7}  分半")
    for god in GODS:
        for ui, rn in RULERS:
            s = collect(god, ui, dom)
            if len(s) < 12:
                continue
            bk = defaultdict(list)
            for b, y in s:
                bk[b].append(y)
            bk = {k: v for k, v in bk.items() if len(v) >= 6}
            if len(bk) < 2:
                continue
            z = z_ll(s)
            # 分半按 case_id 奇偶
            sub = [[], []]
            for cid, sc, sq, vd, vl in rows:
                if dom not in vl:
                    continue
                src = sc if ui == 1 else sq
                sub[cid % 2].append((min(src.get(god, 0), 3), vl[dom]))
            hs = [z_ll(x) for x in sub]
            cells = " ".join(f"{k}:{sum(v)/len(v):.1f}({(len(v))})" for k, v in sorted(bk.items()))
            same = "同" if (hs[0] > 0) == (hs[1] > 0) and min(abs(hs[0]), abs(hs[1])) > 0.5 else "✗"
            mark = ""
            if abs(z) > RED and same == "同":
                mark = " ★过校正线"
            elif abs(z) > 1.96 and same == "同":
                mark = " ○名义过（未过校正）"
            print(f"{god:<5}{rn:<6}{cells:<46}{len(s):>5}{z:>7.2f}  {hs[0]:+.1f}/{hs[1]:+.1f} {same}{mark}")
            if abs(z) > 1.96:
                survivors.append((dom, god, rn, len(s), z, hs, same))
    print()

print("=" * 96)
print("名义显著清单（|z|>1.96）")
print("=" * 96)
for dom, god, rn, n, z, hs, same in sorted(survivors, key=lambda x: -abs(x[4])):
    verdict = "过校正线" if abs(z) > RED and same == "同" else ("分半不稳→假阳性" if same == "✗" else "待观察")
    print(f"{dom:<8}{god:<5}{rn:<5} n={n:<4} z={z:+.2f}  半{hs[0]:+.1f}/{hs[1]:+.1f}  → {verdict}")
con.close()
