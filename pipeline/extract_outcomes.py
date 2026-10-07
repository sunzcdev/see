#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
建「素材层」结局表 case_outcomes —— 从 batches.content（巾箱原文）抽结局。

为什么必须换源：
  回复层（batches.reply）的"结局"63% 取自【方法论·铁律归属】= 我们自己写的批注。
  拿它检验命理＝循环。
  素材层（batches.content）的 [原文首段] 是**源作者**写的，含真实人生事实
  （"流年庚申，父亲因肺病住院""流年癸亥，患眼病致使左眼失明""流年戊寅结婚"），
  独立于我们的判断。坤造 102 例早已按此口径抽过（见 kunzao-extraction-audit.md），
  本次全库照办。

坑（已踩）：
  ① 内层查询若复用外层 cursor，SQLite 会把外层迭代打断 → 必须 fetchall 先物化
  ② case_no 跨批复用 → 禁止用它配 case_id；用「批内块序 + 四柱校验」
  ③ 诀言诗句必须挖掉，否则"亥子多见防目凶"会被当成结局断语
"""
import sqlite3, re, json, sys
from collections import Counter, defaultdict

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute("drop table if exists case_outcomes")
cur.execute("""create table case_outcomes(
  case_id integer primary key, batch_no integer, block_no integer,
  pillars text, pil_ok integer, n_clause integer, verdict text, level text,
  fact_text text, n_quote integer)""")
cur.execute("delete from case_outcomes")

sys.path.insert(0, "/home/ubuntu/projects/jinxiang-kucun")
from verdict_lex import classify

BLOCK = re.compile(r'=====\s*例\s*(\d+)\s*=====')
PIL = re.compile(r'([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])')
QUOTE = re.compile(r'[“"”「]([^”"」]{4,})[”"」]')
FACT = re.compile(r'流年|大运|此年|该年|此运|实际|此造|岁')
EVENT = re.compile(r'住院|失明|失聪|结婚|离婚|再婚|入狱|坐牢|判刑|被捕|去世|病故|身亡|夭折|'
                   r'生子|生女|考大学|参加工作|提干|升任|升迁|官居|任职|发财|破产|破财|丧')

# —— 一次物化，避免 cursor 复用踩坑 ——
cases_by_batch = defaultdict(list)
for bn_, cn_, cid, y, mo, d, h in cur.execute(
        "select batch_no,case_no,case_id,year_pillar,month_pillar,day_pillar,hour_pillar from case_features"):
    cases_by_batch[str(bn_).strip()].append((cn_, cid, (y, mo, d, h)))
for k in cases_by_batch:
    cases_by_batch[k].sort(key=lambda t: (t[0] is None, t[0]))
batch_rows = cur.execute(
    "select batch_no,content from batches where content!='' and content is not null").fetchall()

stat = Counter(); out = []
for bn, content in batch_rows:
    marks = list(BLOCK.finditer(content))
    lst = cases_by_batch.get(str(bn).strip(), [])
    if not marks:
        stat['批无块'] += 1
        if lst:                                     # 无块标记 → 整批当一块
            marks = None
        else:
            continue
    blocks = []
    if marks:
        for k, m in enumerate(marks):
            blocks.append((k, m.group(1),
                           content[m.end():marks[k + 1].start() if k + 1 < len(marks) else len(content)]))
    else:
        blocks = [(0, str(lst[0][0]), content)]

    for k, tag, blk in blocks:
        head = blk.split('[原文首段]')[0][:400]
        ps = PIL.findall(head)
        pil = tuple(ps[:4]) if len(ps) >= 4 else None
        cid, pilok = None, 0
        # ① 批内块序配对
        if k < len(lst):
            cid = lst[k][1]
            pilok = 1 if (pil and lst[k][2] == pil) else 0
        # ② 例号直配兜底
        if cid is None:
            hit = [t[1] for t in lst if str(t[0]) == str(tag)]
            if hit:
                cid = hit[0]; pilok = 2
        if cid is None:
            stat['未配对'] += 1
            continue
        stat['配对'] += 1
        if pilok == 1:
            stat['四柱校验通过'] += 1
        elif pilok == 0:
            stat['四柱不符' if pil else '无四柱'] += 1
        else:
            stat['例号兜底'] += 1

        s = blk.find('[原文首段]')
        src = blk[s + 6:] if s >= 0 else blk
        src = re.split(r'=====', src)[0]
        quotes = QUOTE.findall(src)
        clean = QUOTE.sub('□' * 6, src)
        clauses = [c.strip() for c in re.split(r'[。；\n]', clean) if len(c.strip()) >= 4]
        factcl = [c for c in clauses if FACT.search(c) or EVENT.search(c)]
        facttext = '。'.join(factcl)[:600]
        vd = classify(facttext)
        lv = {}
        if vd:
            try:
                for kk, vv in json.loads(vd).items():
                    if 'lvl' in vv:
                        lv[kk] = vv['lvl']
            except Exception:
                pass
        out.append((cid, bn, int(tag) if str(tag).isdigit() else k + 1,
                    ' '.join(pil) if pil else '', pilok, len(clauses),
                    vd, json.dumps(lv, ensure_ascii=False) if lv else '', facttext, len(quotes)))
        if factcl:
            stat['有事实句'] += 1

cur.executemany("insert or replace into case_outcomes values(?,?,?,?,?,?,?,?,?,?)", out)
con.commit()
n = cur.execute("select count(*) from case_outcomes").fetchone()[0]
nv = cur.execute("select count(*) from case_outcomes where verdict!='' and verdict is not null").fetchone()[0]
nl = cur.execute("select count(*) from case_outcomes where level!=''").fetchone()[0]
nf = cur.execute("select count(*) from case_outcomes where length(fact_text)>20").fetchone()[0]
print("配对:", json.dumps(stat, ensure_ascii=False))
print(f"素材层结局 {n} 例（覆盖 {n/2322*100:.0f}%）｜可分类 {nv}｜有等级 {nl}｜有事实句 {nf}")
print("\n事类分布：")
dd = Counter()
for (v,) in cur.execute("select verdict from case_outcomes where verdict!='' and verdict is not null"):
    try:
        for kk in json.loads(v):
            dd[kk] += 1
    except Exception:
        pass
for k, v in dd.most_common():
    print(f"   {k:<10}{v}")
print("\n样本（含事实句，前 8）：")
for r in cur.execute("select case_id,batch_no,substr(fact_text,1,80),verdict from case_outcomes "
                     "where length(fact_text)>25 limit 8"):
    print(f"  #{r[0]:<5} 批{r[1]:<4} {r[2]}")
    print(f"        → {r[3][:130] if r[3] else '(无)'}")
con.close()
