#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⛔ 已废弃（2026-10-07）—— 本脚本含**产线 bug**，勿再运行。
   第 79 行 `for g in gs` 把四柱天干全拿去数，其中 gs[2] 是**日干自己**，
   而 ss(rz, rz) 恒等于「比肩」⇒ 全库每例比肩 ≥1、「比肩/比劫=0」条件不可测。
   正确版本见 `fix_shishen_root.py`（日主排除，ruler_ver=2，另存 bijian_v1 证据）。
   若确需重跑本脚本，它会写回 v1 口径并覆盖 shishen_quan —— 请先备份。

干支双尺落地：给 case_features 增补 8 字口径十神字段（不覆盖旧字段）
旧字段 shishen_config 保留 = 「表」（天干）；新增 = 「里」（含地支根）
增量、可回滚；旧字段一律不动。
"""
import sqlite3, json, sys

print("⛔ build_ruler8.py 已废弃：它把日干算作比肩（ruler_ver=1）。")
print("   请改用 fix_shishen_root.py（日主排除，ruler_ver=2）。")
if "--force-v1" not in sys.argv:
    sys.exit(1)

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
WX = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
      "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
YANG = set("甲丙戊庚壬")
CANGGAN = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"],
    "卯": ["乙"], "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"], "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"],
    "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
SS10 = ["比肩", "劫财", "食神", "伤官", "正财", "偏财", "正官", "七杀", "正印", "偏印"]
POS = ["年", "月", "日", "时"]


def ss(rz, t):
    if t not in WX:
        return None
    a, b = WX[rz], WX[t]
    same = (rz in YANG) == (t in YANG)
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
cur = con.cursor()

# --- 1. 加列（幂等）---
have = {r[1] for r in cur.execute("PRAGMA table_info(case_features)")}
for col, typ in [("shishen_quan", "TEXT"), ("shishen_benqi", "TEXT"),
                 ("tonggen", "TEXT"), ("shishen_ruler_ver", "INTEGER DEFAULT 0")]:
    if col not in have:
        cur.execute(f"ALTER TABLE case_features ADD COLUMN {col} {typ}")
        print(f"加列 {col}")
con.commit()

rows = cur.execute(
    "select rowid, year_pillar, month_pillar, day_pillar, hour_pillar from case_features"
).fetchall()

ok = bad = 0
for rowid, y, m, d, h in rows:
    gs, zs = [], []
    good = True
    for p in (y, m, d, h):
        p = (p or "").strip()
        if len(p) < 2 or p[0] not in WX or p[1] not in CANGGAN:
            good = False
            break
        gs.append(p[0])
        zs.append(p[1])
    if not good:
        bad += 1
        continue
    rz = gs[2]
    tian = {k: 0 for k in SS10}
    quan = {k: 0 for k in SS10}
    benqi = {k: 0 for k in SS10}
    tg = {}
    for g in gs:
        k = ss(rz, g)
        if k:
            tian[k] += 1
            quan[k] += 1
            benqi[k] += 1
    for i, z in enumerate(zs):
        for j, cg in enumerate(CANGGAN[z]):
            k = ss(rz, cg)
            if not k:
                continue
            quan[k] += 1
            if j == 0:
                benqi[k] += 1
            tg.setdefault(k, []).append(POS[i])  # 日支也计（夫妻宫/自身宫），用 POS 过滤
    cur.execute(
        "update case_features set shishen_quan=?, shishen_benqi=?, tonggen=?, shishen_ruler_ver=1 where rowid=?",
        (json.dumps(quan, ensure_ascii=False), json.dumps(benqi, ensure_ascii=False),
         json.dumps(tg, ensure_ascii=False), rowid),
    )
    ok += 1

con.commit()
print(f"已填 {ok} 例，跳过（四柱残缺）{bad} 例")

# --- 验证：抽 3 例对照 ---
print("\n=== 验证抽样 ===")
for rowid, y, m, d, h, old, nq, tg in cur.execute(
    "select rowid,year_pillar,month_pillar,day_pillar,hour_pillar,shishen_config,shishen_quan,tonggen "
    "from case_features where shishen_ruler_ver=1 limit 3"
):
    print(f"{y} {m} {d} {h}")
    print(f"  天干(旧): {old}")
    print(f"  8字(新): {nq}")
    print(f"  通根位  : {tg}")
con.close()
