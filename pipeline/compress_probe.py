#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压缩法示范：把「域」一步步切小，看可能性空间能不能被压缩。
数据：jinxiang-kucun/jinxiang.db  case_features（2322 例）
只用库里已有字段：shishen_config（十神计数）+ verdict（断事结果）
不排盘、不推演，纯统计。
"""
import sqlite3, json, re
from collections import Counter

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

rows = con.execute(
    "select case_id, gender, shishen_config, verdict, layer from case_features"
).fetchall()

print(f"总案例 {len(rows)}")

# --- 1. shishen_config 质量检查 ---
sums = Counter()
for r in rows:
    try:
        d = json.loads(r["shishen_config"] or "{}")
    except Exception:
        d = {}
    sums[sum(int(v) for v in d.values())] += 1
print("十神计数总和分布:", dict(sorted(sums.items())))

# --- 2. verdict 填充率 ---
fill = sum(1 for r in rows if (r["verdict"] or "").strip())
print(f"verdict 已填 {fill} ({fill/len(rows)*100:.1f}%)")
print("verdict 样例:", [r["verdict"] for r in rows[:12]])

# --- 3. 吉凶分桶 ---
JI = ["发贵", "贵", "富", "荣", "显达", "显贵", "科举", "中举", "进士", "功名",
      "官", "旺", "兴", "寿", "聪明", "秀", "贤", "通达", "大发", "有成", "顺"]
XIONG = ["凶", "贫", "夭", "亡", "死", "刑", "克", "败", "病", "孤", "贱",
         "灾", "祸", "破", "伤", "损", "苦", "困", "废", "疾", "滞", "荡", "淫"]

def bucket(v):
    if not (v or "").strip():
        return None
    j = sum(1 for k in JI if k in v)
    x = sum(1 for k in XIONG if k in v)
    if j > x:
        return "吉"
    if x > j:
        return "凶"
    return "中"

data = []
for r in rows:
    b = bucket(r["verdict"])
    if b is None:
        continue
    try:
        ss = json.loads(r["shishen_config"] or "{}")
    except Exception:
        ss = {}
    g = lambda k: int(ss.get(k, 0) or 0)
    data.append({
        "case_id": r["case_id"], "b": b,
        "guan": g("正官"), "sha": g("偏官"),
        "cai": g("正财") + g("偏财"),
        "yin": g("正印") + g("偏印"),
        "shishang": g("食神") + g("伤官"),
        "bijie": g("比肩") + g("劫财"),
    })

n = len(data)
print(f"\n可判定结局样本 n={n}")
if n == 0:
    raise SystemExit("无可用样本")

def rate(sel, label):
    sub = [d for d in data if sel(d)]
    if not sub:
        print(f"{label:<38} n=0")
        return None
    ji = sum(1 for d in sub if d["b"] == "吉")
    xiong = sum(1 for d in sub if d["b"] == "凶")
    p = ji / len(sub) * 100
    print(f"{label:<38} n={len(sub):<5} 吉={p:5.1f}%  凶={xiong/len(sub)*100:5.1f}%")
    return p

print("\n--- 基线 ---")
P0 = rate(lambda d: True, "全库（基线）")

print("\n--- 第1刀：官星数（域很宽）---")
for k in [0, 1, 2]:
    rate(lambda d, k=k: d["guan"] == k, f"正官={k}")
rate(lambda d: d["guan"] >= 3, "正官>=3")

print("\n--- 第2刀：在「正官=1」里面继续切域 ---")
rate(lambda d: d["guan"] == 1 and d["yin"] >= 1, "正官=1 且 印>=1")
rate(lambda d: d["guan"] == 1 and d["yin"] == 0, "正官=1 且 无印")
rate(lambda d: d["guan"] == 1 and d["cai"] >= 1, "正官=1 且 财>=1")
rate(lambda d: d["guan"] == 1 and d["shishang"] >= 2, "正官=1 且 食伤>=2")

print("\n--- 第3刀：官+杀 合看，再切印 ---")
rate(lambda d: (d["guan"] + d["sha"]) >= 2 and d["yin"] == 0, "官杀>=2 且 无印")
rate(lambda d: (d["guan"] + d["sha"]) >= 2 and d["yin"] >= 1, "官杀>=2 且 印>=1")

print("\n--- 对照：无官杀 ---")
rate(lambda d: d["guan"] + d["sha"] == 0, "官杀=0")
