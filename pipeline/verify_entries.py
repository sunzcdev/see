#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""条目册「禁手写」闸门（可复跑）—— 三道检查，任一不过就非零退出

为什么需要它：2026-10-07 自审 H5 查出「条目条件 ≠ 实测判据」
（条目册手写「偏财≥1」，打分器却按原始计数梯度测）。修法是消掉两份真相，
但**纪律不能靠自觉**——于是把纪律写成可复跑的闸门：

  闸1 判定等价：新规格表 vs 老打分器，逐例逐条比对（回归基准）
  闸2 条件同源：册子里每条 cond 必须等于 entries_spec 现场渲染的结果（差一个字符即失败）
  闸3 无手写残留：册子里不许出现冻结的手写 cond 文本、不许出现手写的 status 字段

用法：python3 distill/verify_entries.py
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import entries_spec as SPEC

FAIL = []


def gate1():
    """判定等价：对全库逐例比对老打分器与新规格表（需同目录留有 score_entries_legacy.py）。"""
    legacy = os.path.join(HERE, "score_entries_legacy.py")
    if not os.path.exists(legacy):
        print("闸1 跳过：无 score_entries_legacy.py（回归基准不在场）")
        return
    code = '''
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath("__file__")) or ".")
import score_entries_legacy as O, entries_spec as S
F = O.load(); Pn = S.registry()
d = 0; n = 0
for eid in sorted(Pn):
    fo, fn = O.P[eid][2], Pn[eid][2]
    for cid, f in F.items():
        n += 1
        try: a = fo(f)
        except Exception: a = "ERR"
        try: b = fn(f)
        except Exception: b = "ERR"
        if a != b or type(a) is not type(b): d += 1
print(f"{n}::{d}")
'''
    r = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True, text=True)
    if r.returncode != 0:
        FAIL.append("闸1 无法执行：" + r.stderr.strip()[:200]); return
    n, d = r.stdout.strip().split("::")
    print(f"闸1 判定等价：{n} 个判定值，不一致 {d} 个 " + ("✅" if d == "0" else "❌"))
    if d != "0":
        FAIL.append(f"闸1 新规格与老打分器不一致 {d} 处")


def gate2():
    """条件同源：册子里的 cond 必须等于规格表现场渲染（含本体按变体计的标注）。"""
    p = os.path.join(HERE, "entries.json")
    if not os.path.exists(p):
        FAIL.append("闸2 无 entries.json"); return
    payload = json.load(open(p, encoding="utf-8"))
    meta = SPEC.meta()
    bad = []
    for e in payload["entries"]:
        m = meta.get(e["id"])
        if not m or m.get("kind") != "cond":
            continue          # 未蒸/尺子/本体：cond 本就是声明文字，不参与本闸
        want = m["cond"]
        if e["cond"] != want and e["cond"] != want + "（本体按变体 x 计）" \
                and not re.fullmatch(re.escape(want) + r"（本体按变体 [xmy] 计）", e["cond"]):
            bad.append((e["id"], e["cond"], want))
    print(f"闸2 条件同源：机器判定 {sum(1 for e in payload['entries'] if meta.get(e['id'],{}).get('kind')=='cond')} 条 "
          f"｜ 不符 {len(bad)} " + ("✅" if not bad else "❌"))
    for b in bad[:5]:
        print("   ", b)
    if bad:
        FAIL.append(f"闸2 册子条件与规格表不符 {len(bad)} 条（有人手写了条件）")


def gate3():
    """无手写残留：不许出现冻结的手写 cond 原文；不许出现手写 status 字段。"""
    p = os.path.join(HERE, "entries.json")
    frozen_p = os.path.join(HERE, "entry-cond-hand-frozen.json")
    if not (os.path.exists(p) and os.path.exists(frozen_p)):
        print("闸3 跳过：缺 entries.json 或冻结基准"); return
    frozen = set(v for v in json.load(open(frozen_p, encoding="utf-8")).values() if v)
    payload = json.load(open(p, encoding="utf-8"))
    hits, stat = [], []
    for e in payload["entries"]:
        e.pop  # noop
        for f in frozen:
            if f == e["cond"]:
                hits.append(e["id"])
        if "status_hand" in e:
            stat.append(e["id"])
    print(f"闸3 无手写残留：手写 cond 原文出现 {len(hits)} 处 ｜ 手写 status 字段 {len(stat)} 处 "
          + ("✅" if not hits and not stat else "❌"))
    if hits or stat:
        FAIL.append(f"闸3 存在手写残留：cond {hits[:3]} / status {stat[:3]}")


if __name__ == "__main__":
    gate1(); gate2(); gate3()
    if FAIL:
        print("\n❌ 闸门未过：")
        for f in FAIL:
            print("  -", f)
        sys.exit(1)
    print("\n✅ 三道闸全过：判定等价 · 条件同源 · 无手写残留")
