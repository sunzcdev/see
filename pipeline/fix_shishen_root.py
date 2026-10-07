#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
十神口径修根：**日主不计入十神**。

病因（build_ruler8.py 第 79 行）：`for g in gs` 把四柱天干全拿去数，
其中 gs[2] 是**日干自己**，而 ss(rz, rz) 恒等于「比肩」⇒
全库每一例都比肩 ≥1，「比肩=0」「比劫=0」这类条件**永远不成立**。
其余九神各有 23%~30% 的 0 组 —— 只有比肩没有，就是这个原因。

处置（不覆盖证据）：
  · 新增列 `bijian_v1`         = 旧比肩数（原口径含日主的读数，留档）
  · 新增列 `shishen_tiangan`   = **天干口径**（表；日主已排除），首次入库
  · 重写  `shishen_quan`       = 全字口径（干支＋地支藏干；日主排除）
  · 重写  `shishen_benqi`      = 本气口径（干＋支本气；日主排除）
  · `shishen_ruler_ver` = 2

不变式（本脚本会核对）：日干只会被算成比肩，故新旧的差
**只体现在比肩 = 旧值 − 1**，其余九神与各槽位总和同步减 1。
"""
import sqlite3, json

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

have = {r[1] for r in cur.execute("PRAGMA table_info(case_features)")}
for col, typ in [("bijian_v1", "INTEGER"), ("shishen_tiangan", "TEXT")]:
    if col not in have:
        cur.execute(f"ALTER TABLE case_features ADD COLUMN {col} {typ}")
        print(f"加列 {col}")
con.commit()

rows = cur.execute(
    "select rowid, year_pillar, month_pillar, day_pillar, hour_pillar, shishen_quan "
    "from case_features"
).fetchall()

ok = bad = swapped = 0
diff_other = 0
for rowid, y, m, d, h, oldq in rows:
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
    for i, g in enumerate(gs):
        if i == 2:            # ← 修根：日干是参照点，不给它安十神
            continue
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
            tg.setdefault(k, []).append(POS[i])

    # 核对不变式：旧值应恰为 新值 + (比肩 1)
    if oldq:
        o = json.loads(oldq)
        for k in SS10:
            exp = o.get(k, 0) - (1 if k == "比肩" else 0)
            if exp != quan[k]:
                diff_other += 1
    cur.execute(
        "update case_features set bijian_v1=?, shishen_tiangan=?, shishen_quan=?, "
        "shishen_benqi=?, tonggen=?, shishen_ruler_ver=2 where rowid=?",
        (json.loads(oldq).get("比肩", 0) if oldq else None,
         json.dumps(tian, ensure_ascii=False), json.dumps(quan, ensure_ascii=False),
         json.dumps(benqi, ensure_ascii=False), json.dumps(tg, ensure_ascii=False), rowid),
    )
    ok += 1

con.commit()
print(f"已重算 {ok} 例（ruler_ver=2），跳过四柱残缺 {bad} 例")
print(f"不变式核对：不符（除比肩外还有别的差异）的槽位 = {diff_other}  ← 应为 0")

print("\n=== 修复后：各神 0 组例数 ===")
z = {k: 0 for k in SS10}
N = 0
tot = []
for (q,) in cur.execute("select shishen_quan from case_features where shishen_quan is not null"):
    dd = json.loads(q)
    N += 1
    tot.append(sum(dd.values()))
    for k in SS10:
        if dd.get(k, 0) == 0:
            z[k] += 1
for k in SS10:
    print(f"  {k}: 0组={z[k]:5d} ({z[k]/N*100:5.1f}%)")
print(f"槽位总和: min={min(tot)} max={max(tot)} 中位={sorted(tot)[N//2]}")

print("\n=== 抽样对照（旧含日主 vs 新排除日主）===")
for y, m, d, h, b1, q in cur.execute(
    "select year_pillar,month_pillar,day_pillar,hour_pillar,bijian_v1,shishen_quan "
    "from case_features where shishen_ruler_ver=2 limit 3"
):
    qq = json.loads(q)
    print(f"{y} {m} {d} {h}  比肩 {b1} → {qq['比肩']}   全字: {q}")
con.close()
