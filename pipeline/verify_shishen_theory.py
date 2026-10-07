#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_shishen_theory.py — 十神计数「独立实现对拍」（理论层自审）

为什么要自己重写一遍十神：
库里的 `shishen_quan` 是**同一套代码**算出来的；拿它去检验同源代码等于没检验。
本脚本用一张**独立抄写的藏干表**＋**独立的十神函数**，从四柱重算三个口径，逐例与库对拍：

  shishen_tiangan  其余三天干（**日主不计**——日主是参照点，不给自己安十神）
  shishen_benqi    三天干 ＋ 四支**本气**
  shishen_quan     三天干 ＋ 四支**全部藏干**（本气+中气+余气）＝条目册口径

对拍结果分三档：一致 / 规则分歧（列出来人工判）/ 库缺失。
只读，不改库。用法：python3 scripts/verify_shishen_theory.py [--show N]
"""
import argparse, json, sqlite3, sys
from collections import Counter, defaultdict

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"

# ── 独立抄写的藏干表（顺序：本气 / 中气 / 余气） ─────────────────────────────
CANGAN = {
    "子": "癸", "丑": "己癸辛", "寅": "甲丙戊", "卯": "乙",
    "辰": "戊乙癸", "巳": "丙庚戊", "午": "丁己", "未": "己丁乙",
    "申": "庚壬戊", "酉": "辛", "戌": "戊辛丁", "亥": "壬甲",
}
# 天干五行与阴阳
WX = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
      "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
YANG = set("甲丙戊庚壬")
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}   # 我生
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}      # 我克
GODS = ["比肩", "劫财", "食神", "伤官", "正财", "偏财", "正官", "七杀", "正印", "偏印"]


def god(rizhu: str, other: str) -> str:
    """独立实现：以日主为参照给 other 定十神"""
    r, o = WX[rizhu], WX[other]
    same_pol = (rizhu in YANG) == (other in YANG)
    if o == r:
        return "比肩" if same_pol else "劫财"
    if SHENG[r] == o:
        return "食神" if same_pol else "伤官"
    if KE[r] == o:
        return "偏财" if same_pol else "正财"
    if KE[o] == r:                      # 克我
        return "七杀" if same_pol else "正官"
    if SHENG[o] == r:                   # 生我
        return "偏印" if same_pol else "正印"
    raise ValueError(f"{rizhu}->{other}")


def counts(pillars, mode: str):
    """pillars=[年,月,日,时]；返回 Counter（日主不计）"""
    c = Counter()
    for i, gz in enumerate(pillars):
        g, z = gz[0], gz[1]
        if not (i == 2 and g == pillars[2][0]):
            pass
        # 天干：日干本身跳过
        if i != 2:
            c[god(pillars[2][0], g)] += 1
        if mode == "tiangan":
            continue
        hidden = CANGAN[z]
        c[god(pillars[2][0], hidden[0])] += 1          # 本气
        if mode == "quan":
            for h in hidden[1:]:
                c[god(pillars[2][0], h)] += 1
    return c


def norm(d):
    return {g: int(v) for g, v in (d or {}).items() if int(v)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--show", type=int, default=5); a = ap.parse_args()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute("""SELECT case_id, year_pillar, month_pillar, day_pillar, hour_pillar,
                                 shishen_quan, shishen_tiangan, shishen_benqi
                          FROM case_features""").fetchall()
    stat = defaultdict(int)
    bad = defaultdict(list)
    for cid, y, m, d, h, sq, st, sb in rows:
        if not all([y, m, d, h]) or len(y) < 2:
            stat["无四柱"] += 1
            continue
        pl = [y, m, d, h]
        for mode, col, key in [("quan", sq, "全字"), ("tiangan", st, "天干"), ("benqi", sb, "本气")]:
            mine = counts(pl, mode)
            theirs = norm(json.loads(col) if col else {})
            if mine == theirs:
                stat[f"{key} ✓"] += 1
            else:
                stat[f"{key} ✗"] += 1
                if len(bad[key]) < a.show:
                    bad[key].append((cid, "".join(pl), dict(mine), theirs))
    con.close()
    print("=" * 74)
    print(f"独立重算对拍：{len(rows)} 例")
    for k in ("全字", "天干", "本气"):
        ok, ng = stat[f"{k} ✓"], stat[f"{k} ✗"]
        tot = ok + ng
        print(f"  {k:<4} 一致 {ok:>4}/{tot}  ({ok/tot:.1%})  " + ("✅" if ng == 0 else f"✗ {ng} 例分歧"))
    if stat["无四柱"]:
        print(f"  （无四柱跳过 {stat['无四柱']} 例）")
    for k, lst in bad.items():
        for cid, pl, mine, theirs in lst:
            diff = {g: (mine.get(g, 0), theirs.get(g, 0)) for g in GODS
                    if mine.get(g, 0) != theirs.get(g, 0)}
            print(f"\n  [{k}] case {cid} {pl}\n     我算={ {g: v[0] for g, v in diff.items()} }\n     库里={ {g: v[1] for g, v in diff.items()} }")
    return 0 if sum(stat[f"{k} ✗"] for k in ("全字", "天干", "本气")) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
