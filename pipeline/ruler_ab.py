#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
尺子对账：天干口径 vs 八字口径（含地支藏干）
目的：用嵌套比较回答「地支该不该进十神尺子」

设计（无过拟合偏差，因为是子集切域不是加格子）：
  基线 = 全库(有verdict)
  A  = 天干有X          ← 现状口径，域宽
  A1 = A 且 地支有X根    ← 加了地支的窄域
  A0 = A 且 地支无X根    ← 同组对照
  若 A1 与 A0 拉开 ⇒ 地支确实带信息 ⇒ 尺子必须含地支
"""
import sqlite3, json, re
from collections import Counter

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"

# ---------- 基础表 ----------
TIANGAN = "甲乙丙丁戊己庚辛壬癸"
WX = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
      "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
YANG = set("甲丙戊庚壬")

# 地支藏干（本气在前）
CANGGAN = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"],
    "卯": ["乙"], "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"], "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"],
    "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}

SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def shishen(rizhu, target):
    """target 相对 rizhu 的十神"""
    if target not in WX:
        return None
    a, b = WX[rizhu], WX[target]
    same = (rizhu in YANG) == (target in YANG)
    if a == b:
        return "比肩" if same else "劫财"
    if SHENG[a] == b:
        return "食神" if same else "伤官"
    if KE[a] == b:
        return "偏财" if same else "正财"
    if KE[b] == a:
        return "七杀" if same else "正官"
    if SHENG[b] == a:
        return "偏印" if same else "正印"
    return None


con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
rows = con.execute(
    "select case_id, year_pillar, month_pillar, day_pillar, hour_pillar, "
    "shishen_config, verdict from case_features where verdict!='' and verdict is not null"
).fetchall()

JI = ["发贵", "贵", "富", "荣", "显达", "显贵", "科举", "中举", "进士", "功名",
      "官", "旺", "兴", "寿", "聪明", "秀", "贤", "通达", "大发", "有成", "顺"]
XIONG = ["凶", "贫", "夭", "亡", "死", "刑", "克", "败", "病", "孤", "贱",
         "灾", "祸", "破", "伤", "损", "苦", "困", "废", "疾", "滞", "荡", "淫"]


def bucket(v):
    if not (v or "").strip():
        return None
    j = sum(1 for k in JI if k in v)
    x = sum(1 for k in XIONG if k in v)
    return "吉" if j > x else ("凶" if x > j else "中")


def parse(p):
    p = (p or "").strip()
    if len(p) < 2:
        return None, None
    return p[0], p[1]


data, mismatch = [], 0
for r in rows:
    b = bucket(r["verdict"])
    if b is None:
        continue
    gs, zs = [], []
    ok = True
    for col in ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"]:
        g, z = parse(r[col])
        if g is None or g not in WX or z not in CANGGAN:
            ok = False
            break
        gs.append(g)
        zs.append(z)
    if not ok or len(gs) != 4:
        continue
    rizhu = gs[2]  # 日干

    # 现状口径复现：四个天干（含日干自计比肩）
    tian = Counter(shishen(rizhu, g) for g in gs)
    try:
        old = json.loads(r["shishen_config"] or "{}")
    except Exception:
        old = {}
    if sum(int(v) for v in old.values()) == 4:
        for k, v in old.items():
            kk = "七杀" if k == "偏官" else k
            if int(v) != tian.get(kk, 0):
                mismatch += 1
                break

    # 八字口径：天干 + 地支藏干
    quan = Counter(tian)
    for z in zs:
        for cg in CANGGAN[z]:
            ss = shishen(rizhu, cg)
            if ss:
                quan[ss] += 1
    # 地支本气口径
    benqi = Counter(tian)
    for z in zs:
        ss = shishen(rizhu, CANGGAN[z][0])
        if ss:
            benqi[ss] += 1

    data.append({"b": b, "tian": tian, "quan": quan, "benqi": benqi,
                 "rizhu": rizhu, "gs": gs, "zs": zs})

print(f"可用样本 n={len(data)}   （现状口径复现不一致 {mismatch} 例）")

n = len(data)
base = Counter(d["b"] for d in data)
P0_x = base["凶"] / n * 100
P0_j = base["吉"] / n * 100
print(f"基线：凶 {P0_x:.1f}%  吉 {P0_j:.1f}%（n={n}）")


def ev(sel, label):
    sub = [d for d in data if sel(d)]
    if len(sub) < 8:
        print(f"  {label:<34} n={len(sub):<4} (样本太少)")
        return
    x = sum(1 for d in sub if d["b"] == "凶") / len(sub) * 100
    j = sum(1 for d in sub if d["b"] == "吉") / len(sub) * 100
    # 可检出最小差异
    mdd = 2.8 * (2 * (P0_x / 100) * (1 - P0_x / 100) / len(sub)) ** 0.5 * 100
    print(f"  {label:<34} n={len(sub):<4} 凶={x:5.1f}% 吉={j:5.1f}%  超额={x-P0_x:+5.1f}pp  可检出线={mdd:.1f}pp")


print("\n【裁判实验】在「天干有某十神」组内，切「地支有无该根」")
print("  判据 = 凶率；若 A1 与 A0 差距大 ⇒ 地支带信息 ⇒ 尺子必须含地支\n")

for name in ["正官", "七杀", "正印", "偏印", "正财", "偏财", "伤官", "食神"]:
    print(f"— {name} —")
    ev(lambda d, s=name: d["tian"].get(s, 0) >= 1,
       f"A  天干{name}≥1（现状口径）")
    ev(lambda d, s=name: d["tian"].get(s, 0) >= 1 and d["quan"].get(s, 0) > d["tian"].get(s, 0),
       f"A1 且地支有{name}根")
    ev(lambda d, s=name: d["tian"].get(s, 0) >= 1 and d["quan"].get(s, 0) == d["tian"].get(s, 0),
       f"A0 且地支无{name}根")
    print()

print("【尺子整体对照】8字口径（含地支藏干）下的官星数")
for k in [0, 1, 2]:
    ev(lambda d, k=k: d["quan"].get("正官", 0) == k, f"8字口径 正官={k}")
ev(lambda d: d["quan"].get("正官", 0) >= 3, "8字口径 正官≥3")
print("\n【对照】现状口径（只天干）下的官星数")
for k in [0, 1, 2]:
    ev(lambda d, k=k: d["tian"].get("正官", 0) == k, f"天干口径 正官={k}")
