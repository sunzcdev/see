#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""词表审计：①每域吉/凶词数 ②分类后极性分布（找单极化） ③未分类句 n-gram 挖漏词"""
import sqlite3, re, json, sys
from collections import defaultdict, Counter
sys.path.insert(0, "/home/ubuntu/projects/jinxiang-kucun")
from verdict_lex import LEX, classify, strip_noise

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
con = sqlite3.connect(DB); cur = con.cursor()

print("=" * 70)
print("① 词表规模（吉/凶 词数）")
print("=" * 70)
print(f"{'域':<10}{'吉词':>6}{'凶词':>6}   失衡")
for dom, pols in LEX.items():
    g, x = len(pols.get("吉", [])), len(pols.get("凶", []))
    flag = ""
    if g == 0 or x == 0:
        flag = "⛔ 单极（无反向词）"
    elif max(g, x) / max(1, min(g, x)) >= 4:
        flag = "⚠️ 严重失衡"
    print(f"{dom:<10}{g:>6}{x:>6}   {flag}")

print()
print("=" * 70)
print("② 分类后极性分布（verdict_domains）")
print("=" * 70)
rows = cur.execute("select verdict_domains from case_features where verdict_domains!=''").fetchall()
cnt = defaultdict(lambda: Counter())
for (js,) in rows:
    try:
        d = json.loads(js)
    except Exception:
        continue
    for dom, v in d.items():
        cnt[dom][v.get("pol", "?")] += 1
print(f"{'域':<10}{'n':>6}{'吉':>6}{'凶':>6}{'混':>6}   凶率(去混)")
for dom, c in sorted(cnt.items(), key=lambda x: -sum(x[1].values())):
    n = sum(c.values()); g, x, m = c["吉"], c["凶"], c["混"]
    pure = g + x
    rate = f"{x / pure * 100:.1f}%" if pure else "—"
    flag = "  ⛔单极化" if pure and (g == 0 or x == 0) else ("  ⚠️极端" if pure and (x / pure > 0.9 or x / pure < 0.1) else "")
    print(f"{dom:<10}{n:>6}{g:>6}{x:>6}{m:>6}   {rate:>7}{flag}")

print()
print("=" * 70)
print("③ 未分类句 n-gram 挖漏词（2-4 字，df≥5，按 df 降序）")
print("=" * 70)
raws = [r[0] for r in cur.execute("select verdict_raw from case_features where verdict_raw!=''")]
uncls = [r for r in raws if not classify(r)]
print(f"有原文 {len(raws)}；未分类 {len(uncls)}（{len(uncls)/max(1,len(raws))*100:.1f}%）\n")
CJK = re.compile(r'[\u4e00-\u9fff]+')
df = Counter()
for s in uncls:
    grams = set()
    for seg in CJK.findall(s):
        for L in (2, 3, 4):
            for i in range(len(seg) - L + 1):
                grams.add(seg[i:i + L])
    for g in grams:
        df[g] += 1
top = [(g, c) for g, c in df.most_common(400) if c >= 5]
# 去掉被更长高频词包含的短词（只留最长的代表）
sett = {g for g, _ in top}
rep = []
for g, c in sorted(top, key=lambda x: -x[1]):
    if any(g != h and g in h for h, _ in top):
        continue
    rep.append((g, c))
for g, c in rep[:120]:
    print(f"{c:>4}  {g}")
con.close()
