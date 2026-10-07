#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verdict 重抽 v5（定版思路，词表外置）
v3 教训：想"抽出结局短语"，结果把日期换算(农历=x=公历y)、大运序列(壬寅8→癸卯18→)
        全当结局抓走。→ 改正：**保留整句，让分类器去读**，不做有损抽取。
v5 变更：LEX/classify/strip_noise 移到 verdict_lex.py（唯一真源），本脚本只跑管线。
三步：① 段落优选 ② 取整句（锚→下一例/换行，限 320 字）剥噪 ③ 分事类×极性打标
"""
import sqlite3, re, json
from collections import defaultdict
from verdict_lex import classify, strip_noise

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
con = sqlite3.connect(DB); cur = con.cursor()
for col in ("verdict_domains", "verdict_sect", "verdict_level", "verdict_fact"):
    if col not in {r[1] for r in cur.execute("PRAGMA table_info(case_features)")}:
        cur.execute(f"ALTER TABLE case_features ADD COLUMN {col} TEXT DEFAULT ''")
con.commit()

# 段落优先级（2026-10-07 修正二）：**客观事实段 > 命理批注段 > 排盘日历**。
# 库版式实测：标准结构 =【排盘核验】→【方法论·铁律归属】→【资产】。
# 旧序把 63% 的"结局"取自【方法论·铁律归属】——那是**我们自己写的命理批注**
# （93% 含命理术语）⇒ 拿命理结论验证命理结论＝循环。
# 结论：**回复层整体不是测量层**，只能做参考；真正的测量层是 batches.content（巾箱原文）。
SECTIONS = [("断语回溯", 5), ("先断后核", 4), ("先断", 4), ("事实", 4),
            ("重点发现", 3), ("方法论", 2), ("排盘核验", 0)]
# 可当测量用的段落（含可核查的客观事件）；【方法论】只作参考，不得用于检验
FACT_SECT = {"断语回溯", "事实", "先断后核", "先断"}
EVENT = re.compile(r'\(\d{4}\)|\d{4}\s*年|住院|失明|失聪|结婚|离婚|再婚|入狱|坐牢|判刑|'
                   r'去世|病故|身亡|夭折|生子|生女|中举|进士|升任|升迁|处级|厅级|破产|破财')


def pick_clause(reply, cn, idx, pillars):
    """按段落优先级取该例整句"""
    cands = []
    for head, pri in SECTIONS:
        s = reply.find(head)
        if s < 0:
            continue
        e = reply.find("【", s + len(head))
        seg = reply[s:e if e > 0 else s + 4000]
        pos = end = None; mode = ''
        if cn and cn not in ('0', ''):
            m = re.search(r'例\s*' + re.escape(str(cn)) + r'(?!\d)', seg)
            if m: pos, end, mode = m.start(), m.end(), '例号'
        if pos is None and idx:
            m = re.search(r'例\s*' + str(idx) + r'(?!\d)', seg)
            if m: pos, end, mode = m.start(), m.end(), '序号'
        if pos is None and pillars and len(pillars) == 4:
            flat = ''.join(pillars); p = seg.find(flat)
            if p < 0 and ' '.join(pillars) in seg: p = seg.find(' '.join(pillars))
            if p >= 0: pos, end, mode = p, p + len(flat), '四柱'
        if pos is not None:
            tail = seg[end:end + 320]
            m_nxt = re.search(r'例\s*\d+', tail)                 # 下一个例
            m_nl = re.search(r'\n', tail)                        # 或换行（方法论段一例一行）
            cut = min([m.start() for m in (m_nxt, m_nl) if m], default=320)
            clause = seg[pos:end + cut]
            cands.append((pri, head, mode, strip_noise(clause)[:320]))
    if not cands:
        return '', '', ''
    cands.sort(key=lambda x: -x[0])
    return cands[0][3], cands[0][1], cands[0][2]


rows = cur.execute("select case_id,batch_no,case_no,year_pillar,month_pillar,day_pillar,hour_pillar from case_features").fetchall()
replies = dict(cur.execute("select batch_no,reply from batches"))
order = defaultdict(list)
for r in rows:
    order[r[1]].append(r[2])

stat = defaultdict(int); samples = []
for case_id, bn, cn, y, mo, dd, h in rows:
    reply = replies.get(bn, '') or ''
    raw = sect = mode = ''
    if reply:
        idx = (order[bn].index(cn) + 1) if cn in order[bn] else 0
        pil = [x for x in (y, mo, dd, h) if x]
        raw, sect, mode = pick_clause(reply, cn, idx, pil)
    dom = classify(raw)
    lvls = {}
    if dom:
        try:
            for k, v in json.loads(dom).items():
                if "lvl" in v:
                    lvls[k] = v["lvl"]
        except Exception:
            pass
    fact = raw if (sect in FACT_SECT and EVENT.search(raw)) else ''
    stat['有原文'] += 1 if raw else 0
    stat['有分类'] += 1 if dom else 0
    stat['有等级'] += 1 if lvls else 0
    stat['事实层'] += 1 if fact else 0
    stat['段落_' + sect] += 1 if sect else 0
    cur.execute("update case_features set verdict_raw=?,verdict_domains=?,verdict_level=?,verdict_fact=?,verdict_sect=?,verdict_match=? where case_id=?",
                (raw, dom, json.dumps(lvls, ensure_ascii=False) if lvls else '', fact, sect, mode, case_id))
    if dom and len(samples) < 8:
        samples.append((bn, cn, sect, raw[:150], dom))
con.commit()

print("统计:", json.dumps(stat, ensure_ascii=False, sort_keys=True))
print(f"\n有断语原文 {stat['有原文']}/2322 = {stat['有原文']/2322*100:.1f}%")
print(f"有分类结果 {stat['有分类']}/2322 = {stat['有分类']/2322*100:.1f}%")
print("\n=== 抽样 ===")
for bn, cn, sect, raw, dom in samples:
    print(f"批{bn} 例{cn} [{sect}] {raw[:130]}")
    print(f"    → {dom}")
con.close()
