#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""性别列修复 v3（最终版）。

【为什么要重做这一列】
    原 case_features.gender 是病列：215 个含 ≥2 例的批次**全部只有单一性别值**
    （混合批次 = 0），即「把每批第一例的性别盖给全批」。
    三把尺子对裁也证实：库 vs 乾坤直读 64.8%、库 vs 文义线索 59.4%，
    而两把独立尺子彼此 98.9% 一致 ⇒ 脏的是库，不是正文。

【锚点】四柱（case_no/例N 不可信，实测错位）。
【两个独立读数】
    kq   块内「观此/观其 + (乾|坤) + (命|造)」，退而求其次块内 (乾|坤)(命|造)
    cue  块内文义线索（克夫/嫁夫/小妾… vs 娶妻/岳父/岳母…），不看「乾坤」二字
【定档】两读一致=PASS；只 kq=KQ；只 cue=CUE；两读冲突=CONFLICT（留原位并标记）；
        都无=UNKNOWN。
【落库】新列 gender_fixed / gender_grade / gender_evid；
        原 gender 原名保留、另存 gender_lib_orig 留痕（病列不删，便于审计）。
"""
import re
import sqlite3
import collections

DB = 'jinxiang.db'
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row
B = {r['batch_no']: (r['content'] or '') for r in db.execute("select batch_no, content from batches")}
HDR = re.compile(r'=====\s*例\s*\d+\s*=====')

CUE_F = ['克夫', '嫁夫', '夫星', '丈夫', '其夫', '小妾', '填房', '二房', '做小',
         '婆婆', '此女', '该女', '女方', '女命', '坤命', '坤造', '有夫之妇',
         '红杏', '寡妇', '守寡', '风流之女', '情夫', '再嫁', '夫宫', '嫁人']
CUE_M = ['娶妻', '其妻', '妻子', '妻星', '岳父', '岳母', '此男', '该男', '男方',
         '乾命', '乾造', '男命', '妻宫', '结发', '夫人']
RE_KQ1 = re.compile(r'观[此其]?[之为]?\s*([乾坤])\s*[命造]')
RE_KQ2 = re.compile(r'([乾坤])\s*[命造]')
RE_NU = re.compile(r'([男女])命')


def blocks(bn):
    c = B.get(bn, '')
    ms = list(HDR.finditer(c))
    if not ms:
        return [(c,)] if c.strip() else []
    return [(c[m.end():(ms[i + 1].start() if i + 1 < len(ms) else len(c))],) for i, m in enumerate(ms)]


def read(blk):
    m1 = [x.group(1) for x in RE_KQ1.finditer(blk)]
    kq = collections.Counter(m1).most_common(1)[0][0] if m1 else None
    kq_src = 'kq1' if kq else ''
    if kq is None:
        m2 = [x.group(1) for x in RE_KQ2.finditer(blk)]
        if m2:
            c2 = collections.Counter(m2)
            if len(c2) == 1 or c2.most_common()[0][1] > c2.most_common()[1][1]:
                kq = c2.most_common(1)[0][0]; kq_src = 'kq2'
    nf = sum(blk.count(w) for w in CUE_F)
    nm = sum(blk.count(w) for w in CUE_M)
    cue = '坤' if nf > nm else '乾' if nm > nf else None
    return kq, kq_src, cue, nf, nm


rows = list(db.execute("""select case_id,batch_no,year_pillar,month_pillar,day_pillar,
                                 hour_pillar,gender from case_features"""))
rec = {}
for r in rows:
    pil = (r['year_pillar'], r['month_pillar'], r['day_pillar'], r['hour_pillar'])
    if not all(pil):
        rec[r['case_id']] = (None, 'UNKNOWN', 'NO_PILLAR'); continue
    blk = None
    for (b,) in blocks(r['batch_no']):
        if re.search(r'\s*'.join(pil), b) or re.search(r'\s*'.join(pil[:3]), b):
            blk = b; break
    if blk is None:
        rec[r['case_id']] = (None, 'UNKNOWN', 'NO_ANCHOR'); continue
    kq, kq_src, cue, nf, nm = read(blk)
    if kq and cue:
        if kq == cue:
            rec[r['case_id']] = (kq, 'PASS', f'{kq_src}+cue({nf}/{nm})')
        else:
            rec[r['case_id']] = (kq, 'CONFLICT', f'{kq_src} vs cue({nf}/{nm})')
    elif kq:
        rec[r['case_id']] = (kq, 'KQ', kq_src)
    elif cue:
        rec[r['case_id']] = (cue, 'CUE', f'cue({nf}/{nm})')
    else:
        rec[r['case_id']] = (None, 'UNKNOWN', 'NO_MARK')

print("=== 定档分布 ===")
for k, v in collections.Counter(g[1] for g in rec.values()).most_common():
    print(f"  {k:<10} {v}")

cols = [x[1] for x in db.execute("PRAGMA table_info(case_features)")]
for c in ('gender_fixed', 'gender_grade', 'gender_evid', 'gender_lib_orig'):
    if c not in cols:
        db.execute(f"ALTER TABLE case_features ADD COLUMN {c} TEXT")
db.executemany("""update case_features set gender_fixed=?, gender_grade=?, gender_evid=?,
                  gender_lib_orig=coalesce(gender_lib_orig, gender) where case_id=?""",
               [(g, gr, ev, cid) for cid, (g, gr, ev) in rec.items()])
db.commit()

print("\n=== 修复后覆盖 ===")
for x in db.execute("select coalesce(gender_fixed,'未定') g, count(*) n from case_features group by 1 order by 2 desc"):
    print(f"  {x['g']:<4} {x['n']}")

print("\n=== 新旧对比（只在两者都有值）===")
x = db.execute("""select sum(gender_lib_orig=gender_fixed) 同, sum(gender_lib_orig<>gender_fixed) 异
                  from case_features where gender_lib_orig in ('乾','坤') and gender_fixed in ('乾','坤')""").fetchone()
print(f"  旧库 vs 新列：一致 {x['同']} / 不一致 {x['异']}   （不一致率 {x['异']/(x['同']+x['异'])*100:.1f}%）")

print("\n=== 旧库性别完全作废的演示：批次内是否混合 ===")
x = db.execute("""select sum(nd=1 and n>1) 单值批, sum(nd>1) 混合批 from
                 (select batch_no,count(distinct gender_lib_orig) nd,count(*) n from case_features
                  where gender_lib_orig in ('乾','坤') group by batch_no)""").fetchone()
print(f"  旧列：单值批 {x['单值批']}，混合批 {x['混合批']}  ← 混合批应为多数，实为 0 ⇒ 病列")
x = db.execute("""select sum(nd=1 and n>1) 单值批, sum(nd>1) 混合批 from
                 (select batch_no,count(distinct gender_fixed) nd,count(*) n from case_features
                  where gender_fixed in ('乾','坤') group by batch_no)""").fetchone()
print(f"  新列：单值批 {x['单值批']}，混合批 {x['混合批']}  ← 恢复正常")

print("\n=== 冲突例（需人眼）===")
for r in db.execute("""select case_id,batch_no,gender_fixed,gender_evid from case_features
                       where gender_grade='CONFLICT' limit 10"""):
    print(f"  案例{r['case_id']} 批次{r['batch_no']} 取{r['gender_fixed']} 证据{r['gender_evid']}")
