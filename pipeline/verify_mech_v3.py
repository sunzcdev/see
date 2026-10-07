#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""机制标签 v3 闸门（可复跑）—— 加「旺衰结构层」不许动既有结果

v3 干的事：给机制标签加一层**旺衰结构标签**（偏重/缺位/均平），专治 470 例无标签。
但「加东西」最容易出的错是**悄悄改了旧结果**（主标签被新标签挤掉、阈值被顺手改）。
所以纪律写成闸门，两关：

  闸1 **机制层等价**：关掉结构层重算，必须与库里留档的 v2（`mech_primary_v2`/`mech_aux_v2`）**逐例逐字相同**。
  闸2 **主标签不变式**：开着结构层重算，**凡 v2 有主标签的例，主标签必须一个字都不变**；
                       v2 无标签的例，必须全部拿到主标签（新层只补空白，不抢座位）。

用法：python3 scripts/verify_mech_v3.py
"""
import os, sys, json, sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

os.environ.setdefault("MECH_SS_COL", "shishen_quan")
import mechanism_tag as M

DB = os.path.join(ROOT, "jinxiang.db")


def load_rows():
    c = sqlite3.connect(DB)
    return c.execute("""SELECT case_id, rizhu, yueling, shishen_quan, di_zhi_freq,
                               pattern_switches, mech_primary_v2, mech_aux_v2
                        FROM case_features""").fetchall()


def calc(ss, zhis, rz, yl, ps, structural):
    tags = M.calc_tags(ss, zhis, rz, yl)
    if structural:
        tags = tags + M.calc_structural(ss)
    ordered = M.pick_primary(tags, yl, ps)
    return (ordered[0] if ordered else ''), json.dumps(ordered[1:4], ensure_ascii=False)


def main():
    rows = load_rows()
    fail = []
    # 闸1：机制层等价（关结构层 vs 库里 v2）
    d1 = 0
    for cid, rz, yl, ssq, dzq, psq, p2, a2 in rows:
        ss, dz, ps = json.loads(ssq or '{}'), json.loads(dzq or '{}'), json.loads(psq or '[]')
        p, a = calc(ss, [z for z, c in dz.items() if c > 0], rz, yl, ps, structural=False)
        if p != (p2 or '') or a != (a2 or '[]'):
            d1 += 1
            if d1 <= 5:
                print(f"   闸1 不一致 case {cid}: 重算 {p}/{a} vs v2 {p2}/{a2}")
    print(f"闸1 机制层等价（vs 库内 v2 留档）: {len(rows)} 例 ｜ 不一致 {d1} " + ("✅" if d1 == 0 else "❌"))
    if d1:
        fail.append(f"闸1 机制层与 v2 不一致 {d1} 例")

    # 闸2：主标签不变式
    kept = changed = filled = still_empty = 0
    empties = []
    for cid, rz, yl, ssq, dzq, psq, p2, a2 in rows:
        ss, dz, ps = json.loads(ssq or '{}'), json.loads(dzq or '{}'), json.loads(psq or '[]')
        p, a = calc(ss, [z for z, c in dz.items() if c > 0], rz, yl, ps, structural=True)
        if p2:
            if p == p2:
                kept += 1
            else:
                changed += 1
                if changed <= 5:
                    print(f"   闸2 主标签被动 case {cid}: v2={p2} → v3={p}")
        else:
            if p:
                filled += 1
            else:
                still_empty += 1
                empties.append(cid)
    print(f"闸2 主标签不变式：v2 有标签 {kept + changed} 例 ⇒ 保持不变 {kept}、被动 {changed} "
          + ("✅" if changed == 0 else "❌"))
    print(f"                 v2 无标签 470 例 ⇒ 补上 {filled}、仍空 {still_empty} "
          + ("✅" if still_empty == 0 else "❌"))
    if changed:
        fail.append(f"闸2 有 {changed} 例既有主标签被改动")
    if still_empty:
        fail.append(f"闸2 仍有 {still_empty} 例无标签（{empties[:5]}…）")
    if not fail:
        print("\n覆盖率：1852 → 2322（100%）；结构层单独消掉 470 例空白")
    if fail:
        print("\n❌ 闸门未过：")
        for x in fail:
            print("  -", x)
        sys.exit(1)
    print("✅ 两关全过：机制层零变动 · 主标签只补不改")


if __name__ == "__main__":
    main()
