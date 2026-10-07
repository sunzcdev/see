#!/usr/bin/env python3
# 出口家底审计：「出口先于条目」——把两个结果出口的「能测清单」列出来
# 源A = case_features.verdict_domains（回复层，抽取变量）
# 源B = case_outcomes.verdict / level（素材层，原文直取）
import sqlite3, json, math
from collections import Counter, defaultdict

DB = '/home/ubuntu/projects/jinxiang-kucun/jinxiang.db'
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row

g = {}
for r in con.execute("select case_id, gender_fixed from case_features"):
    g[r['case_id']] = (r['gender_fixed'] or '未定')

def H(c):
    n = sum(c.values())
    if n == 0: return 0.0
    return -sum((v/n)*math.log2(v/n) for v in c.values() if v)

def line(n, p0):
    return 2.8*math.sqrt(2*p0*(1-p0)/n) if n > 0 else float('nan')

def scan(rows, pol_key='pol'):
    per = defaultdict(lambda: {'n':0,'pol':Counter(),'lvl':Counter(),'g':Counter()})
    bad = 0
    for cid, js in rows:
        if not js: continue
        try: d = json.loads(js)
        except Exception: bad += 1; continue
        if not isinstance(d, dict): bad += 1; continue
        for dom, v in d.items():
            if not isinstance(v, dict): continue
            p = per[dom]; p['n'] += 1
            pol = v.get(pol_key) or v.get('pol') or v.get('polarity')
            if pol: p['pol'][pol] += 1
            lv = v.get('lvl', v.get('level'))
            if lv is not None:
                try: p['lvl'][int(lv)] += 1
                except Exception: pass
            p['g'][g.get(cid,'?')] += 1
    return per, bad

A = list(con.execute("select case_id, verdict_domains from case_features"))
B = list(con.execute("select case_id, verdict from case_outcomes"))
BL = list(con.execute("select case_id, level from case_outcomes"))

out = []
w = out.append
w("=" * 78)
w("出口家底审计（出口先于条目）")
w("=" * 78)
tot = len(A)
w(f"库里案例总数 {tot}；源A 有 verdict_domains 的 {sum(1 for _,j in A if j)}；")
w(f"源B 有 verdict 的 {sum(1 for _,j in B if j)}；源B 有 level 的 {sum(1 for _,j in BL if j)}")
w("")

for label, rows in [("源A　回复层（抽取变量：verdict_domains）", A),
                    ("源B　素材层（原文直取：case_outcomes.verdict）", B)]:
    per, bad = scan(rows)
    w("-" * 78)
    w(f"【{label}】  解析失败 {bad}")
    w(f"{'域':<14}{'n':>6}{'乾':>6}{'坤':>6}{'吉':>6}{'凶':>6}{'有等级':>7}{'等级档':>8}{'H/Hmax':>8}{'单极?':>7}")
    for dom, p in sorted(per.items(), key=lambda kv: -kv[1]['n']):
        ji = p['pol'].get('吉', 0); xi = p['pol'].get('凶', 0)
        nl = sum(p['lvl'].values())
        k = len(p['lvl'])
        hh = H(p['lvl'])/math.log2(k) if k > 1 else 0.0
        mono = '单极' if (ji == 0 or xi == 0) else ''
        w(f"{dom:<14}{p['n']:>6}{p['g'].get('乾',0):>6}{p['g'].get('坤',0):>6}"
          f"{ji:>6}{xi:>6}{nl:>7}{k:>8}{hh:>8.3f}{mono:>7}")
    w("")

# 双源配对：同域同时有两源的例数
perA, _ = scan(A); perB, _ = scan(B)
w("-" * 78)
w("【双源配对】同一域上「两源都有」的例数（配对出口 = 能否出结论的前提）")
a_ids = defaultdict(set); b_ids = defaultdict(set)
for cid, js in A:
    if not js: continue
    try: d = json.loads(js)
    except Exception: continue
    if isinstance(d, dict):
        for dom in d: a_ids[dom].add(cid)
for cid, js in B:
    if not js: continue
    try: d = json.loads(js)
    except Exception: continue
    if isinstance(d, dict):
        for dom in d: b_ids[dom].add(cid)
doms = sorted(set(a_ids) | set(b_ids), key=lambda d: -len(b_ids[d]))
for dom in doms:
    pa = len(a_ids[dom]); pb = len(b_ids[dom]); both = len(a_ids[dom] & b_ids[dom])
    w(f"{dom:<14} 源A {pa:>5}｜源B {pb:>5}｜两源都有 {both:>5}")

open('/home/ubuntu/projects/jinxiang-kucun/outlet-audit.txt','w').write("\n".join(out))
print("\n".join(out))
