#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""机制标签阈值重标定（calibrate_mech.py）

问题：`mechanism_tag.py` 的 18 条规则阈值（「印≥3」「比劫≥3」…）是在**老尺**
（`shishen_config`＝只数天干，且日主计入比肩 ⇒ 病）上标定的。
换到**正确尺**（`shishen_quan`＝全字含藏干、日主不计）后，十神计数密度差约 4 倍
（老尺每例 0.3 个/十神，新尺 1.2–1.34），**照搬阈值 ⇒ 规则饱和**（人人命中 ⇒ 标签无区分度）。

做法：**按选择性对齐**——对每个原子判据，在新尺上找一条阈值，使**命中率与老尺持平**。
  这不是拍数字，是保「这条规则筛掉多少人」的信息量不变；换尺只换坐标。

输出：`mech_thresholds.json`（数据而非代码 ⇒ 下次换尺只改这份文件）
"""
import sqlite3, json, os, sys, datetime

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jinxiang.db')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mech_thresholds.json')

def vec(ss):
    """把十神 dict 归约成规则所需的变量"""
    g = lambda k: ss.get(k, 0)
    return {
        'sha': g('七杀'), 'guan': g('正官'),
        'yin': g('正印') + g('偏印'),
        'shi': g('食神'), 'shang': g('伤官'),
        'cai': g('正财') + g('偏财'),
        'bi': g('比肩') + g('劫财'),
        'shishang': g('食神') + g('伤官'),
        'guansha': g('正官') + g('七杀'),
    }

# 规则里用到的原子判据：(变量, 比较, 老尺阈值)
SPECS = [
    ('sha', 'ge', 1), ('guan', 'ge', 1), ('yin', 'ge', 1), ('shi', 'ge', 1),
    ('shang', 'ge', 1), ('cai', 'ge', 1), ('yin', 'ge', 2), ('yin', 'ge', 3),
    ('cai', 'ge', 3), ('bi', 'ge', 3), ('bi', 'lt', 2),
    ('shishang', 'ge', 1), ('guansha', 'ge', 1),
]

def rate(vals, op, t):
    if op == 'ge':
        hit = sum(1 for v in vals if v >= t)
    else:  # 'lt'
        hit = sum(1 for v in vals if v < t)
    return hit / len(vals)

def main():
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT shishen_config, shishen_quan FROM case_features").fetchall()
    old_vecs, new_vecs = [], []
    for o, n in rows:
        old_vecs.append(vec(json.loads(o or '{}')))
        new_vecs.append(vec(json.loads(n or '{}')))
    N = len(rows)

    table, out = [], {}
    for var, op, thr in SPECS:
        ov = [d[var] for d in old_vecs]
        nv = [d[var] for d in new_vecs]
        old_rate = rate(ov, op, thr)
        # 在新尺上找阈值使命中率最接近
        cands = range(0, max(nv) + 2)
        best, best_d = None, 9
        for t in cands:
            r = rate(nv, op, t)
            if abs(r - old_rate) < best_d:
                best, best_d, best_r = t, abs(r - old_rate), r
        table.append((f'{var} {">=" if op=="ge" else "<"} {thr}', old_rate, best, best_r, best_r - old_rate))
        out.setdefault(var, {})[f'{op}_{thr}'] = best

    print(f'样本 {N} 例 ｜ 按选择性对齐（新尺阈值使命中率≈老尺）\n')
    print(f'{"判据（老尺写法）":<18}{"老尺命中率":>10}{"新尺阈值":>10}{"新尺命中率":>11}{"偏差":>9}')
    print('-' * 60)
    for name, orr, t, nrr, d in table:
        flag = '' if abs(d) <= 0.03 else ('  ⚠' if abs(d) <= 0.08 else '  ⚠⚠')
        print(f'{name:<18}{orr:>9.1%}{t:>10}{nrr:>10.1%}{d:>+9.1%}{flag}')

    meta = {
        'ver': 2,
        'ruler': 'shishen_quan',
        'ruler_note': '全字含藏干、日主不计十神（ruler_ver=2）；替换老尺 shishen_config（只数天干、日主计入比肩）',
        'method': '选择性对齐：对新尺逐阈值求命中率，取与老尺命中率最接近者',
        'matched_at': datetime.date.today().isoformat(),
        'n_cases': N,
        'thresholds': out,
        'audit_table': [
            {'pred': name, 'old_rate': round(orr, 4), 'new_thr': t,
             'new_rate': round(nrr, 4), 'delta': round(d, 4)}
            for name, orr, t, nrr, d in table
        ],
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f'\n已写出 {OUT}')
    worst = max(table, key=lambda x: abs(x[4]))
    print(f'最大偏差：{worst[0]} ｜ {worst[4]:+.1%}')
    conn.close()

if __name__ == '__main__':
    main()
