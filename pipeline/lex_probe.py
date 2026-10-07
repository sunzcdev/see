#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""词表单极化诊断：①干滤后的漏词 n-gram ②反向极性探针（语料里有没有另一半）③抽读未分类句"""
import sqlite3, re, random, sys
from collections import Counter, defaultdict
sys.path.insert(0, "/home/ubuntu/projects/jinxiang-kucun")
from verdict_lex import classify

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
con = sqlite3.connect(DB); cur = con.cursor()
raws = [r[0] for r in cur.execute("select verdict_raw from case_features where verdict_raw!=''")]
uncls = [r for r in raws if not classify(r)]

GAN = set("甲乙丙丁戊己庚辛壬癸")
ZHI = set("子丑寅卯辰巳午未申酉戌亥")
NOISE = set("农历公历诀言新铁律与旧修正存疑素材图谱批甲乙反馈全对排盘抽样全录累计通过正确修正 年月日时".split()) | {""}

print("=" * 74)
print("① 干滤后漏词 n-gram（2-4 字，df≥4，剔除纯干支/噪声）")
print("=" * 74)
CJK = re.compile(r'[\u4e00-\u9fff]+')
df = Counter()
for s in uncls:
    seen = set()
    for seg in CJK.findall(s):
        for L in (2, 3, 4):
            for i in range(len(seg) - L + 1):
                g = seg[i:i + L]
                if all(ch in GAN or ch in ZHI for ch in g):
                    continue
                if g in NOISE or any(n in g for n in ("农历", "公历", "诀言", "铁律", "批")):
                    continue
                seen.add(g)
    for g in seen:
        df[g] += 1
top = [(g, c) for g, c in df.most_common(600) if c >= 4]
rep = [(g, c) for g, c in sorted(top, key=lambda x: -x[1])
       if not any(g != h and g in h for h, _ in top)]
for g, c in rep[:90]:
    print(f"{c:>4}  {g}")

print()
print("=" * 74)
print("② 反向极性探针：语料里有没有「另一半」（全库 1945 句原文统计）")
print("=" * 74)
PROBE = {
    "刑灾·吉向": ["无罪", "免刑", "平反", "脱险", "释放", "澄清", "免祸", "化解", "逢凶化吉", "无官非", "无牢狱", "不受", "清白", "昭雪", "减刑"],
    "寿元·吉向": ["康健", "长寿", "寿高", "无恙", "康复", "痊愈", "病愈", "平安", "无病", "安享", "矍铄", "硬朗", "寿元长", "健在", "延寿"],
    "功名·凶向": ["失意", "潦倒", "无成", "不遇", "失业", "无业", "务农", "种地", "落魄", "寒儒", "教书", "穷儒", "布衣", "不第", "落榜", "终身不仕", "平民"],
    "婚姻·吉向": ["恩爱", "和顺", "美满", "白头", "携老", "夫妻和", "情笃", "相敬", "贤内助", "偕老", "幸福", "美满婚姻"],
    "六亲·吉向": ["父贵", "母贤", "父荫", "得荫", "双全", "有荫", "家世好", "父援", "兄弟助", "得力兄弟"],
    "子女·吉向": ["儿女双全", "得子", "有子", "子孝", "子女多", "子秀", "子贵", "生子"],
    "特殊·吉向": ["高僧", "名僧", "得道", "修道有成", "仙风", "有道行", "有名师"],
    "功名·等级": ["知县", "知府", "侍郎", "尚书", "宰相", "翰林", "进士", "举人", "秀才", "状元", "将军", "提督", "巡抚", "总督", "县丞", "主簿", "科级", "处级", "部级", "正团", "市长"],
    "财·等级": ["亿万", "巨富", "大富", "富翁", "小康", "温饱", "家财", "薄财", "中产", "殷实"],
}
for dom, ws in PROBE.items():
    hits = {w: sum(1 for s in raws if w in s) for w in ws}
    tot = sum(hits.values())
    live = {w: c for w, c in hits.items() if c}
    print(f"\n【{dom}】合计命中 {tot}")
    if live:
        print("   " + "  ".join(f"{w}×{c}" for w, c in sorted(live.items(), key=lambda x: -x[1])))
    else:
        print("   ⛔ 全部 0 —— 语料里根本没有这半边")

print()
print("=" * 74)
print("③ 未分类原句抽读（每 14 句取一，共 42 句）")
print("=" * 74)
random.seed(20261007)
for i, s in enumerate(uncls[::14][:42]):
    print(f"[{i:02d}] {s[:190]}")
con.close()
