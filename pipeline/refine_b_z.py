#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组间对比 z（group vs 其余），替眼估。
探索性：这些条目已在首轮被选中，此处只做切细，不计入多重比较 K。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_entries import load, z_linlin, cnt, tgpos, fem

F = load()
ALL = list(F)


def contrast(name, dom, inG, universe=None, useA=True):
    U = universe if universe is not None else ALL
    row = f"{name:<30}"
    for sname in ('A', 'B'):
        for outc in ('L', 'X'):
            b, y = [], []
            for cid in U:
                pol, lvl = F[cid][sname].get(dom, (None, None))
                if outc == 'L':
                    if lvl is None: continue
                    yv = lvl
                else:
                    if pol is None: continue
                    yv = 1 if pol == '凶' else 0
                b.append(1 if inG(F[cid]) else 0); y.append(yv)
            z, n, why = z_linlin(b, y)
            cell = f"z={z:+.2f}(n={n})" if z is not None else f"{why}"
            row += f"{cell:<18}"
    print(row)


def hasdom(dom, sname):
    return [c for c in ALL if dom in F[c][sname]]

print(f"{'组 vs 其余（全库）':<30}{'A:等级':<18}{'A:凶率':<18}{'B:等级':<18}{'B:凶率':<18}")
print("-" * 102)

# 正官 → 功名事业
print("【正官 → 功名事业】")
contrast("正官≥1", '功名事业', lambda f: cnt(f, '正官') >= 1)
contrast("正官≥2", '功名事业', lambda f: cnt(f, '正官') >= 2)
contrast("正官≥3", '功名事业', lambda f: cnt(f, '正官') >= 3)

# 财生官 → 功名事业
print("【财+官 → 功名事业】")
contrast("财≥1∧官≥1", '功名事业', lambda f: cnt(f, '正财', '偏财') >= 1 and cnt(f, '正官', '七杀') >= 1)
contrast("财≥1∧正官≥1", '功名事业', lambda f: cnt(f, '正财', '偏财') >= 1 and cnt(f, '正官') >= 1)

# 比肩 → 财（走 cnt()，已按 ruler_ver 自动校正：ver=2 库值本身已排除日主）
# 注：2026-10-07 前此处硬编码「−1」，修根后若仍减 1 会**双重扣减**。
print("【比肩 → 财（真比肩＝不含日主）】")
contrast("真比肩≥1", '财', lambda f: cnt(f, '比肩') >= 1)
contrast("真比肩≥2（成势）", '财', lambda f: cnt(f, '比肩') >= 2)
contrast("真比肩≥3", '财', lambda f: cnt(f, '比肩') >= 3)
contrast("偏财≥1（对照，应显著）", '财', lambda f: cnt(f, '偏财') >= 1)

# 位置条：偏财落年月 vs 落日时
print("【位置条（只在 偏财≥1 内部）】")
U = [c for c in ALL if cnt(F[c], '偏财') >= 1]
contrast("偏财透干在年月", '财', lambda f: bool(set(f['tg'].get('偏财') or []) & {'年', '月'}), U)
contrast("偏财透干在日时", '财', lambda f: bool(set(f['tg'].get('偏财') or []) & {'日', '时'}), U)
contrast("偏财藏支（不透）", '财', lambda f: not (f['tg'].get('偏财') or []), U)

# 女命轴单看（坤造仅 106）
print("【女命轴（宇宙=坤造 106 例）】")
K = [c for c in ALL if fem(F[c])]
contrast("伤官见官（坤造内）", '婚姻', lambda f: cnt(f, '伤官') >= 1 and cnt(f, '正官') >= 1, K)
contrast("正官∧七杀混杂", '婚姻', lambda f: cnt(f, '正官') >= 1 and cnt(f, '七杀') >= 1, K)
contrast("夫星不透干", '婚姻', lambda f: cnt(f, '正官', '七杀') > 0 and not (tgpos(f, '正官', '七杀') & {'日', '时'}), K)
