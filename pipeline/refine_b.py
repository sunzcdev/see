#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B 档条目切细（探索性：在已选中的条目上叠条件，不新增检验数）。
纪律：全库跑，两源并看，两出口并看；n 小 ⇒ 只读方向与梯度，不读显著性。
"""
import sys, os, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_entries import load, z_linlin, cnt, has, tgpos, fem

F = load()


def cell(ids, dom):
    """返回 {(源,出口): (n, 均值)} + z"""
    out = {}
    for sname in ('A', 'B'):
        for outc in ('L', 'X'):
            v, p = [], []
            for cid in ids:
                pol, lvl = F[cid][sname].get(dom, (None, None))
                if outc == 'L':
                    if lvl is None: continue
                    v.append(lvl)
                else:
                    if pol is None: continue
                    p.append(1 if pol == '凶' else 0)
            out[(sname, outc)] = (len(v), statistics.mean(v) if v else None,
                                  len(p), statistics.mean(p) if p else None)
    return out


def show(title, groups, dom):
    print(f"\n### {title}（域={dom}）")
    print(f"{'组':<26}{'A:等级均(n)':<18}{'A:凶率(n)':<18}{'B:等级均(n)':<18}{'B:凶率(n)':<18}")
    for name, ids in groups:
        c = cell(ids, dom)
        row = f"{name:<26}"
        for key in (('A', 'L'), ('A', 'X'), ('B', 'L'), ('B', 'X')):
            n, nm, pn, pm = c[key]
            if key[1] == 'L':
                row += f"{(f'{nm:.2f}' if nm is not None else '—')+'('+str(n)+')':<18}"
            else:
                row += f"{(f'{pm:.3f}' if pm is not None else '—')+'('+str(pn)+')':<18}"
        print(row)


def flux(groups, dom):
    """组间 z（把组序当序数预测子）"""
    print("  组序 z：", end="")
    for sname in ('A', 'B'):
        for outc in ('L', 'X'):
            b, y = [], []
            for gi, (_, ids) in enumerate(groups):
                for cid in ids:
                    pol, lvl = F[cid][sname].get(dom, (None, None))
                    if outc == 'L':
                        if lvl is None: continue
                        yv = lvl
                    else:
                        if pol is None: continue
                        yv = 1 if pol == '凶' else 0
                    b.append(gi); y.append(yv)
            z, n, why = z_linlin(b, y)
            print(f" {sname}{outc}:" + (f"z={z:+.2f} n={n}" if z is not None else why), end="")
    print()


KUN = [c for c in F if fem(F[c])]
ALL = list(F)
print(f"库 {len(F)} 例，其中坤造 {len(KUN)} 例")

# ── AX09-04 伤官见官（坤造）→ 婚姻 ──────────────────────────────
base = [c for c in KUN if cnt(F[c], '伤官') >= 1 and cnt(F[c], '正官') >= 1]
g1 = [c for c in base if cnt(F[c], '正印', '偏印') >= 1]
g2 = [c for c in base if cnt(F[c], '正财', '偏财') >= 1]
g3 = [c for c in base if not cnt(F[c], '正印', '偏印') and not cnt(F[c], '正财', '偏财')]
ctrl = [c for c in KUN if c not in base]
show("AX09-04 伤官见官·坤造 → 婚姻", [
    ("对照：其余坤造", ctrl),
    ("见官格全部", base),
    ("＋有印（印制伤）", g1),
    ("＋有财（财通关）", g2),
    ("＋无印无财（无制无化）", g3),
], '婚姻')

# ── AX01-06 正官 → 功名 ───────────────────────────────────────
show("AX01-06 正官 → 功名", [
    ("无正官", [c for c in ALL if cnt(F[c], '正官') == 0]),
    ("正官≥1", [c for c in ALL if cnt(F[c], '正官') >= 1]),
    ("正官≥2", [c for c in ALL if cnt(F[c], '正官') >= 2]),
    ("正官有根（支）", [c for c in ALL if cnt(F[c], '正官') >= 1 and tgpos(F[c], '正官')]),
    ("正官只在干无根", [c for c in ALL if cnt(F[c], '正官') >= 1 and not tgpos(F[c], '正官')]),
], '功名事业')

# ── AX01-05 比肩 → 财 ─────────────────────────────────────────
# 口径更正：库内 shishen_quan 把**日干本身**计为比肩 ⇒ 真比肩数 = 库值 − 1
def rb(f): return f['ss'].get('比肩', 0) - 1
def bp(f, where):
    return len([p for p in (f['tg'].get('比肩') or []) if p in where])

show("AX01-05 比肩（已校正含日主）→ 财", [
    ("真比肩=0（仅日主）", [c for c in ALL if rb(F[c]) == 0]),
    ("真比肩=1", [c for c in ALL if rb(F[c]) == 1]),
    ("真比肩≥2", [c for c in ALL if rb(F[c]) >= 2]),
    ("有真比肩 且根在年月", [c for c in ALL if rb(F[c]) >= 1 and bp(F[c], ('年', '月')) and not bp(F[c], ('日', '时'))]),
    ("有真比肩 且根在日时", [c for c in ALL if rb(F[c]) >= 1 and bp(F[c], ('日', '时'))]),
], '财')
print("   tg 口径抽查:", {k: v for k, v in list(F[list(F)[0]]['tg'].items()) if k in ('比肩', '偏财')})

# ── AX02-06 财生官 → 功名 ─────────────────────────────────────
ca = [c for c in ALL if cnt(F[c], '正财', '偏财') >= 1 and cnt(F[c], '正官', '七杀') >= 1]
show("AX02-06 财生官 → 功名", [
    ("无财或无官", [c for c in ALL if c not in ca]),
    ("财+官全", ca),
    ("财+官 且官有根", [c for c in ca if tgpos(F[c], '正官', '七杀')]),
    ("财+官 且无印", [c for c in ca if cnt(F[c], '正印', '偏印') == 0]),
], '功名事业')

# ── 岁运应期层可用性 ─────────────────────────────────────────
import sqlite3
HERE = os.path.dirname(os.path.abspath(__file__))
db = sqlite3.connect(os.path.join(HERE, "..", "jinxiang.db"))
n_ev = db.execute("select count(*) from case_events").fetchone()[0]
n_cs = db.execute("select count(distinct case_id) from case_events").fetchone()[0]
print(f"\n### AX-10 岁运应期层：case_events 共 {n_ev} 条事件，覆盖 {n_cs} 例")
print("   ⇒ 单例平均不到 1 条，无法做格内频率；只能做案例级读法（个案应期对照），不进统计层。")
