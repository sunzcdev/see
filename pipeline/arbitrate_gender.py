#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""性别三把尺子对裁：库 gender vs 乾坤直读(M1) vs 文义线索(cue)。

背景：把「正文说乾坤」与「库 gender」逐例比对，只有 65% 吻合；人眼抽查 3 条
      不符例，**全部是正文对、库错**。故需要第三个独立测量来裁谁可信。

三把尺子互相独立（信息来源不同）：
  lib  库 case_features.gender      —— 前一轮抽取器写的（来源不明，疑似有病）
  kq   块内「观此/观其 + 乾|坤 + 命|造」—— 正文直说
  cue  块内文义线索（克夫/嫁/小妾 vs 娶妻/岳父…）—— 不看乾坤二字

若 cue 与 kq 的一致率远高于 cue 与 lib，则 lib 是脏的。
"""
import re
import sqlite3
import collections

db = sqlite3.connect('jinxiang.db')
db.row_factory = sqlite3.Row
B = {r['batch_no']: (r['content'] or '') for r in db.execute("select batch_no, content from batches")}
HDR = re.compile(r'=====\s*例\s*\d+\s*=====')

CUE_F = ['克夫', '嫁夫', '夫星', '丈夫', '其夫', '小妾', '填房', '二房', '做小',
         '婆婆', '此女', '该女', '女方', '女命', '坤命', '坤造', '有夫之妇',
         '红杏', '寡妇', '守寡', '风流之女', '情夫', '再嫁', '夫宫', '嫁人']
CUE_M = ['娶妻', '其妻', '妻子', '妻星', '岳父', '岳母', '此男', '该男', '男方',
         '乾命', '乾造', '男命', '妻宫', '结发', '夫人']


def blocks(bn):
    c = B.get(bn, '')
    ms = list(HDR.finditer(c))
    if not ms:
        return [(c,)] if c.strip() else []
    out = []
    for i, m in enumerate(ms):
        e = ms[i + 1].start() if i + 1 < len(ms) else len(c)
        out.append((c[m.end():e],))
    return out


RE_M1 = re.compile(r'观[此其]?[之为]?\s*([乾坤])\s*[命造]')
RE_M4 = re.compile(r'([乾坤])\s*[命造]')
RE_M3 = re.compile(r'([男女])命')


def read(blk):
    res = {}
    m1 = [x.group(1) for x in RE_M1.finditer(blk)]
    res['kq'] = collections.Counter(m1).most_common(1)[0][0] if m1 else (
        collections.Counter(x.group(1) for x in RE_M4.finditer(blk)).most_common(1)[0][0]
        if RE_M4.search(blk) else None)
    nf = sum(blk.count(w) for w in CUE_F)
    nm = sum(blk.count(w) for w in CUE_M)
    res['cue'] = ('坤' if nf > nm else '乾' if nm > nf else None)
    res['cue_n'] = nf + nm
    m3 = [x.group(1) for x in RE_M3.finditer(blk)]
    res['mx'] = collections.Counter(m3).most_common(1)[0][0] if m3 else None
    return res


rows = list(db.execute("""select case_id,batch_no,year_pillar,month_pillar,day_pillar,
                                 hour_pillar,gender from case_features"""))
tab = collections.Counter()
detail = []
for r in rows:
    pil = (r['year_pillar'], r['month_pillar'], r['day_pillar'], r['hour_pillar'])
    blk = None
    if all(pil):
        for (b,) in blocks(r['batch_no']):
            if re.search(r'\s*'.join(pil), b) or re.search(r'\s*'.join(pil[:3]), b):
                blk = b; break
    if blk is None:
        continue
    d = read(blk)
    lib = r['gender'] if r['gender'] in ('乾', '坤') else None
    if lib and d['kq']:
        tab[('lib', 'kq', lib == d['kq'])] += 1
    if lib and d['cue'] and d['cue_n'] >= 2:
        tab[('lib', 'cue', lib == d['cue'])] += 1
    if d['kq'] and d['cue'] and d['cue_n'] >= 2:
        tab[('kq', 'cue', d['kq'] == d['cue'])] += 1
    if lib and d['cue'] and d['cue_n'] >= 2:
        detail.append((r['case_id'], lib, d['kq'], d['cue'], d['cue_n']))

print("=== 三把尺子两两一致率（只在双方都有结论的例上）===")
for a, b in (('lib', 'kq'), ('lib', 'cue'), ('kq', 'cue')):
    y = tab[(a, b, True)]; n = tab[(a, b, False)]
    tot = y + n
    print(f"  {a:<4} vs {b:<4}  一致 {y:>4} / 不一致 {n:>4}   一致率 {y/tot*100 if tot else 0:5.1f}%  (n={tot})")

print("\n=== 库 与 cue 不符的样例（看谁离谱）===")
for x in detail[:15]:
    tag = '库错?' if x[1] != x[3] else ''
    print(f"  案例{x[0]:<5} 库={x[1]} 乾坤直读={x[2]} 文义={x[3]}(n={x[4]}) {tag}")
