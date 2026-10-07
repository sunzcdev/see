#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""偏财→财 的切细实验（探索性：在已选中的唯一假设上叠条件，不新增检验数）。
切法：全字个数 → 有没有根 → 根落在哪（年/月 vs 日/时）→ 根数梯度。
判据：全库跑，两源并看；z 升即为切细有效。探索性结果须前瞻确认。
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_entries import load, z_linlin

F = load()

def posof(f, ss):
    tg = f.get('tg') or {}
    ps = tg.get(ss, [])
    if isinstance(ps, str): ps = [ps]
    return [p for p in ps if p]

def cnt(f, ss):
    return (f.get('ss') or {}).get(ss, 0)

def test(name, fn, dom='财'):
    row = [name]
    for outc in ('L', 'X'):
        for sname in ('A', 'B'):
            b, y = [], []
            for cid, f in F.items():
                v = fn(f)
                if v is None: continue
                pol, lvl = f[sname].get(dom, (None, None))
                if outc == 'L':
                    if lvl is None: continue
                    yv = lvl
                else:
                    if pol is None: continue
                    yv = 1 if pol == '凶' else 0
                b.append(v); y.append(yv)
            z, n, why = z_linlin(b, y)
            row.append("—" if z is None else f"{z:+.2f} n={n}")
    print(f"{row[0]:<28} L:A {row[1]:<16} L:B {row[2]:<16} X:A {row[3]:<16} X:B {row[4]}")

print("=== 偏财 → 财 切细（全库 2322；L=等级↑ X=凶率↓ ⇒ X 负号=好）===")
test("0 基线：偏财个数", lambda f: cnt(f, '偏财'))
test("1 阴性对照：正财个数", lambda f: cnt(f, '正财'))
test("2 偏财有根(0/1)", lambda f: 1 if posof(f, '偏财') else 0)
test("3 偏财根在年月(年月根数)", lambda f: len([p for p in posof(f, '偏财') if p in ('年', '月')]))
test("4 偏财根在日时(日时根数)", lambda f: len([p for p in posof(f, '偏财') if p in ('日', '时')]))
test("5 偏财根数梯度", lambda f: min(len([p for p in posof(f, '偏财') if p in ('年', '月', '日', '时')]), 3))
test("6 有偏财且有根(0/1/2)", lambda f: 0 if cnt(f, '偏财') == 0 else (2 if posof(f, '偏财') else 1))
print()
print("=== 对照：比肩/劫财 同样切 ===")
test("7 比肩个数", lambda f: cnt(f, '比肩'))
test("8 比肩有根(0/1)", lambda f: 1 if posof(f, '比肩') else 0)
print()
print("=== 位置键核对（前 5 例耳机偏财落位）===")
k = 0
for cid, f in F.items():
    if cnt(f, '偏财') > 0 and k < 5:
        print(f"  #{cid} 偏财个数={cnt(f,'偏财')} 根位={posof(f,'偏财')} 全部tg键={sorted((f.get('tg') or {}).keys())}")
        k += 1
