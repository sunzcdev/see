#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
格局层扫描：把巾箱的 n=1 窄口诀「合并」成跨日柱的十神格局粗条件，在原文层测。

为什么走这一层：
  巾箱体例 = (日柱 × 月令) 单例断言 ⇒ 720 格分 2322 例，每格 n≈3，统计上无解。
  这是 iron_laws 全表「支持 1 / 反例 0」的真正原因：**不是没核验，是域窄到测不动。**
  ⇒ 出路 = 用户要的「合并」：把窄口诀归纳成十神格局类（粗条件），域宽到能测。

纪律：
  预注册 K=10（机制先行，非撒网）→ Bonferroni 红线 z≈2.81
  源B（素材层=巾箱原文）为判据源；源A（回复层=我的批注）仅作对照
  源B 过线 且 分半同向 才算「跨源站住」
"""
import sqlite3, json, math
from collections import defaultdict

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
con = sqlite3.connect(DB)

# —— 预注册：古典格局 → 本命域 + 预期方向 ——
# pred(shishen_quan_8字, tian_gan_4干)
def g(sq, g_):
    return sq.get(g_, 0)
def gg(sq, *names):
    return sum(sq.get(n, 0) for n in names) if False else sum(sq.get(n, 0) for n in names)

PREREG = [
    ("官印相生",    "功名事业", +1, "正官或七杀≥1 且 正印或偏印≥1",
     lambda s, t: gg(s, "正官", "七杀") >= 1 and gg(s, "正印", "偏印") >= 1),
    ("杀印相生",    "功名事业", +1, "七杀≥1 且 印(正/偏)≥1",
     lambda s, t: g(s, "七杀") >= 1 and gg(s, "正印", "偏印") >= 1),
    ("财旺生官",    "功名事业", +1, "财(正/偏)≥2 且 官杀≥1",
     lambda s, t: gg(s, "正财", "偏财") >= 2 and gg(s, "正官", "七杀") >= 1),
    ("伤官配印",    "功名事业", +1, "伤官≥1 且 印≥1",
     lambda s, t: g(s, "伤官") >= 1 and gg(s, "正印", "偏印") >= 1),
    ("官杀混杂",    "功名事业", -1, "正官≥1 且 七杀≥1",
     lambda s, t: g(s, "正官") >= 1 and g(s, "七杀") >= 1),
    ("伤官见官",    "婚姻",     -1, "伤官≥1 且 正官≥1",
     lambda s, t: g(s, "伤官") >= 1 and g(s, "正官") >= 1),
    ("比劫夺财",    "财",       -1, "比肩+劫财≥2 且 财≥1",
     lambda s, t: gg(s, "比肩", "劫财") >= 2 and gg(s, "正财", "偏财") >= 1),
    ("食神生财",    "财",       +1, "食神≥1 且 财≥1",
     lambda s, t: g(s, "食神") >= 1 and gg(s, "正财", "偏财") >= 1),
    ("财多身弱",    "财",       -1, "财≥3 且 (比劫+印)≤1",
     lambda s, t: gg(s, "正财", "偏财") >= 3 and (gg(s, "比肩", "劫财") + gg(s, "正印", "偏印")) <= 1),
    ("食神制杀",    "寿元健康", +1, "食神≥1 且 七杀≥1",
     lambda s, t: g(s, "食神") >= 1 and g(s, "七杀") >= 1),
]


def norm_ppf(p):
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609579822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
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
    q = p - 0.5; r = q*q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


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


SH = {}
for cid, sq in con.execute("select case_id,shishen_quan from case_features"):
    try:
        SH[cid] = json.loads(sq or '{}')
    except Exception:
        pass
A, B = {}, {}
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

K = len(PREREG)
RED = norm_ppf(1 - 0.025/K)
print(f"源A 回复层(循环源) {len(A)} 例｜源B 素材层(原文,独立源) {len(B)} 例")
print(f"预注册 K={K} → Bonferroni 红线 z={RED:.2f}\n")
print(f"{'格局':<12}{'域':<6}{'预期':<5}{'nA':>5}{'zA':>7}{'nB':>5}{'zB':>7}  {'分半B':<12}判读")
print("-" * 104)


def run(src, pred, dom):
    out = []
    for cid, lv in src.items():
        if dom not in lv or cid not in SH:
            continue
        out.append((1 if pred(SH[cid], None) else 0, lv[dom]))
    return out


res = []
for name, dom, exp, desc, pred in PREREG:
    sa, sb = run(A, pred, dom), run(B, pred, dom)
    za, zb = z_ll(sa), z_ll(sb)
    h = [[], []]
    for cid, lv in B.items():
        if dom not in lv or cid not in SH:
            continue
        h[cid % 2].append((1 if pred(SH[cid], None) else 0, lv[dom]))
    hs = [z_ll(x) for x in h]
    halfok = (hs[0] > 0) == (hs[1] > 0) and min(abs(hs[0]), abs(hs[1])) > 0.5
    signok = (zb > 0) == (exp > 0) and zb != 0
    if abs(zb) > RED and halfok and signok:
        v = "★ 站住（原文层过线+分半+符号对）"
    elif abs(zb) > 1.96 and halfok and signok:
        v = "○ 名义过（未过校正）"
    elif abs(zb) > 1.96 and not signok:
        v = "✗ 显著但方向反"
    elif abs(zb) > 1.96 and not halfok:
        v = "✗ 显著但分半不稳"
    else:
        v = "· 无"
    print(f"{name:<12}{dom:<6}{'+' if exp>0 else '-':<5}{len(sa):>5}{za:>7.2f}{len(sb):>5}{zb:>7.2f}  {hs[0]:+.1f}/{hs[1]:+.1f}{'同' if halfok else '✗':<4}{v}")
    res.append((name, dom, sa, sb, zb, v))

print("\n" + "=" * 104)
print("格局命中率与域均值（源B 素材层）")
print("=" * 104)
for name, dom, exp, desc, pred in PREREG:
    sb = run(B, pred, dom)
    n1 = sum(b for b, _ in sb)
    if n1 < 5 or len(sb) - n1 < 5:
        print(f"  {name:<12}{dom:<6}命中 {n1}/{len(sb)} —— 样本不足，略")
        continue
    m1 = sum(y for b, y in sb if b == 1) / n1
    m0 = sum(y for b, y in sb if b == 0) / (len(sb) - n1)
    print(f"  {name:<12}{dom:<6}命中率 {n1/len(sb):>5.1%}  等级均值 {m0:.2f}(n{len(sb)-n1}) → {m1:.2f}(n{n1})  Δ{m1-m0:+.2f}")
con.close()
