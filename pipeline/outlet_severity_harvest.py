#!/usr/bin/env python3
# 严重度出口选词：把「刑灾官非/六亲/子女」三域的原文事实段做词表普查
# 目的＝拿到真实词汇表，再按传统断语层级定「先验严重度排序」（排序先定，后看分布）
import sqlite3, json, re, collections

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
c = sqlite3.connect(DB)
PUNC = re.compile(r"[，。、；：！？…—～·「」『』（）()\[\]【】《》\"'’“”\s0-9A-Za-z]+")

for DOM in ("刑灾官非", "六亲", "子女"):
    texts = []
    for (js, ft) in c.execute("select verdict, fact_text from case_outcomes"):
        if not js or not ft: continue
        try: d = json.loads(js)
        except Exception: continue
        if DOM in d:
            texts.append(ft)
    cnt = collections.Counter()
    for t in texts:
        clean = PUNC.sub("|", t)
        for seg in clean.split("|"):
            for k in (2, 3, 4):
                for i in range(len(seg) - k + 1):
                    cnt[seg[i:i+k]] += 1
    print("=" * 70)
    print(f"【{DOM}】n={len(texts)}")
    print("-- 高频 2-3 字 --")
    top = [w for w, v in cnt.most_common(400) if len(w) in (2, 3) and v >= 4]
    print("  " + "  ".join(f"{w}:{cnt[w]}" for w in top[:60]))
    print("-- 高频 4 字 --")
    top4 = [w for w, v in cnt.most_common(400) if len(w) == 4 and v >= 4]
    print("  " + "  ".join(f"{w}:{cnt[w]}" for w in top4[:40]))
    print("-- 样例 3 条 --")
    for t in texts[:3]:
        print("  ·", t[:110].replace("\n", " "))
