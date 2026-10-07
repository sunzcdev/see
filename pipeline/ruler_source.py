#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双源裁判：同一条假设，在两个数据源上并排测。
  源A 回复层（batches.reply → verdict_domains/verdict_level）＝ **循环源**
       63% 结局取自我们自己写的【方法论·铁律归属】批注
  源B 素材层（batches.content → case_outcomes）＝ **独立源**
       巾箱源作者写的真实人生事实

判据（按「撒网自我惩罚」教训，**只测预注册的少数候选**，不撒 80 格）：
  预注册 K 条 → Bonferroni 红线；两源同向且同过线 =「跨源复现」，才算数。
"""
import sqlite3, json, math
from collections import defaultdict

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
con = sqlite3.connect(DB)

GODS = ["比肩", "劫财", "食神", "伤官", "正财", "偏财", "正官", "七杀", "正印", "偏印"]

# —— 预注册候选（机制先行：巾箱条件 + 道秀做功路径 + 子平骨架，圈定后才测）——
PREREG = [
    ("劫财", "财", "天干劫财≥1 → 财等级下降"),
    ("劫财", "财", "8字劫财≥1 → 财等级下降"),
    ("偏财", "财", "8字偏财≥1 → 财等级上升"),
    ("正财", "财", "8字正财≥1 → 财等级下降"),
    ("正官", "功名事业", "8字正官≥1 → 功名等级上升"),
    ("官印相生", "功名事业", "正官≥1且正印≥1 → 功名等级上升"),
    ("伤官", "婚姻", "8字伤官≥1 → 婚姻等级下降"),
    ("七杀", "刑灾官非", "8字七杀≥1 → 刑灾凶"),
]


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


def z_ll(samples):
    N = len(samples)
    if N < 12:
        return 0.0
    Sb = sum(b for b, _ in samples); Sy = sum(y for _, y in samples)
    Sbb = sum(b*b for b, _ in samples); Syy = sum(y*y for _, y in samples)
    Sby = sum(b*y for b, y in samples)
    var = (Sbb - Sb*Sb/N) * (Syy - Sy*Sy/N) / (N - 1)
    if var <= 0:
        return 0.0
    return (Sby - Sb*Sy/N) / math.sqrt(var)


# —— 载入两源 ——
A, B = {}, {}     # case_id -> {dom: level}
for cid, vd, vl in con.execute("select case_id,verdict_domains,verdict_level from case_features"):
    if vd:
        try:
            A[cid] = json.loads(vl or '{}')
        except Exception:
            pass
for cid, vd, vl in con.execute("select case_id,verdict,level from case_outcomes"):
    if vd:
        try:
            B[cid] = json.loads(vl or '{}')
        except Exception:
            pass
SH = {}
for cid, sc, sq in con.execute("select case_id,shishen_config,shishen_quan from case_features"):
    try:
        SH[cid] = (json.loads(sc or '{}'), json.loads(sq or '{}'))
    except Exception:
        pass

print(f"源A 回复层（循环源）可测 {len(A)} 例｜源B 素材层（独立源）可测 {len(B)} 例")
K = len(PREREG)
RED = norm_ppf(1 - 0.025 / K)
print(f"预注册 K={K}；Bonferroni 红线 z={RED:.2f}（名义 1.96）\n")


def binarize(god, sq):
    """十神 → 二分档（有/无），避免小样本分档抖动；官印相生为组合档"""
    if god == "官印相生":
        return 1 if (sq.get("正官", 0) >= 1 and sq.get("正印", 0) >= 1) else 0
    return 1 if sq.get(god, 0) >= 1 else 0


def run(src, god, dom, ruler):
    out = []
    for cid, lv in src.items():
        if dom not in lv or cid not in SH:
            continue
        sc, sq = SH[cid]
        s = sc if ruler == "天干" else sq
        out.append((binarize(god, s), lv[dom]))
    return out


print(f"{'假设':<40}{'nA':>5}{'zA':>7}{'nB':>5}{'zB':>7}  判读")
print("-" * 96)
rows_out = []
for god, dom, desc in PREREG:
    ruler = "天干" if "天干" in desc else "8字"
    cat = "官印相生" if god == "官印相生" else ("劫财" if god == "劫财" else god)
    sa = run(A, god, dom, ruler)
    sb = run(B, god, dom, ruler)
    za, zb = z_ll(sa), z_ll(sb)

    def half(src):
        h = [[], []]
        for cid, lv in src.items():
            if dom not in lv or cid not in SH:
                continue
            sc, sq = SH[cid]
            s = sc if ruler == "天干" else sq
            h[cid % 2].append((binarize(god, s), lv[dom]))
        return [z_ll(x) for x in h]

    ha, hb = half(A), half(B)
    okA = abs(za) > RED and (ha[0] > 0) == (ha[1] > 0)
    okB = abs(zb) > RED and (hb[0] > 0) == (hb[1] > 0)
    same = (za > 0) == (zb > 0) and min(abs(za), abs(zb)) > 0.5
    if okB and same:
        v = "★跨源复现（独立源过线+同向）"
    elif okB:
        v = "★只独立源过线（方向分歧）"
    elif okA and same:
        v = "○仅循环源过线（独立源未复现）"
    elif abs(zb) > 1.96 and same:
        v = "○独立源名义显著（未过校正）"
    else:
        v = "· 无"
    print(f"{desc:<40}{len(sa):>5}{za:>7.2f}{len(sb):>5}{zb:>7.2f}  {v}")
    rows_out.append((desc, za, zb, ha, hb, v, len(sa), len(sb)))

print("\n" + "=" * 96)
print("分档均值细看（源B 素材层：0=无 1=有 → 该域平均等级）")
print("=" * 96)
for god, dom, desc in PREREG:
    ruler = "天干" if "天干" in desc else "8字"
    sb = run(B, god, dom, ruler)
    g = defaultdict(list)
    for b, y in sb:
        g[b].append(y)
    cells = " ".join(f"{k}:{sum(v)/len(v):.2f}(n{len(v)})" for k, v in sorted(g.items()))
    print(f"  {dom:<6}{desc:<34}{cells}")
con.close()
