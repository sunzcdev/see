#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_signals.py — 多源信号合并（叠加 / 混频）

## 为什么要这个
多术合参（八字＋六爻＋奇门＋大六壬＋梅花…）看起来给了一堆证据，但**同刻起盘必同源**：
同一时刻的同一个盘，换一种术数只是**换了一套编码**，不是换了一个信息源。
本库实测：三术一致率 **92.3%**，而若彼此独立应只有 **28.8%** ⇒ 相关性极高。
⇒ 「三个术都这么说」的信息量 ≈ 「一个术这么说」× 很小一点。
**直接相加 z 值 = 放大自信，不增加知识。**

## 模型：先分簇，再合并（两步，顺序不能反）
**第 1 步 · 簇内取平均**。`cluster` = 真正能算「一个信源」的单位（同一批数据 / 同一起盘时刻 /
同一个观察者 / 同一份材料）。簇内各条**默认完全相关**，故取**加权平均**：
`z_c = Σ w·z / Σ w`，簇的有效权重 `w_c = max(w)`（不是相加！）。簇内条数再多也**只算 1 个源**。
> 为什么不能直接用 Stouffer：Stouffer 的前提是各条**独立**——簇内恰恰不独立，用它＝重复计数。

**第 2 步 · 跨簇 Stouffer**：`Z = Σ w_c·z_c / sqrt(Σ w_c²)`；有效独立源数
`N_eff = (Σ w_c)² / Σ w_c²`（Kish，此时簇间近似独立，公式才成立）。

## 档位封顶（铁律：A 档的唯一进货口是前瞻盲测命中 ≥2）
`N_eff ≥ 2` 才允许往 A 档说；`N_eff < 2` ⇒ **不论 Z 多大，封顶 B**。
（`--gates` 另给「前瞻命中数」参数：前瞻命中 <2 直接压到 B，与 N_eff 无关。）

## 权重表（w = 独立性折扣）
| 类别 | w | 理由 |
|---|---|---|
| L4 现实回报（事后真发生 / 当事人独立确认） | 1.00 | 唯一「盲」的 |
| L3 异源异测量（不同数据源、不同测量方式同号） | 0.60 | 近似独立 |
| L2 同刻异术（同一起盘时刻的另一种术数） | 0.30 | 实测一致 92.3% |
| L2r 同库换层回看（同数据换口径/换出口） | 0.15 | 假独立，几乎纯冗余 |
| L1 自述 / 我方批注 / 我方注释 | 0.10 | 循环 |

用法：
  python3 merge_signals.py e.json [--hit 0]   # e.json=[{"name","z","cluster","wave","kind"}...]
  python3 merge_signals.py --demo
  python3 merge_signals.py --table
"""
import json, math, sys

W = {"L4": 1.00, "L3": 0.60, "L2": 0.30, "L2r": 0.15, "L1": 0.10}
DESC = {"L4": "现实回报", "L3": "异源异测量", "L2": "同刻异术", "L2r": "同库换层回看", "L1": "自述/批注"}


def merge(evs, z_crit=2.86, hit=0, verbose=True):
    # ① 打权重
    for e in evs:
        e["w"] = W.get(e.get("kind", "L1"), 0.10)
    # ② 簇内平均（同 wave 的不同术数算同一簇：同刻起盘必同源）
    clusters = {}
    for e in evs:
        key = e.get("cluster") or e.get("wave") or e.get("name")
        clusters.setdefault(key, []).append(e)
    rows = []
    for key, g in clusters.items():
        sw = sum(x["w"] for x in g) or 1e-9
        z_c = sum(x["w"] * x["z"] for x in g) / sw
        w_c = max(x["w"] for x in g)
        rows.append({"cluster": key, "n": len(g), "z_c": z_c, "w_c": w_c,
                     "members": [x.get("name", "") for x in g],
                     "avg_of": [round(x["z"], 2) for x in g]})
    sw = sum(r["w_c"] for r in rows)
    sw2 = sum(r["w_c"] ** 2 for r in rows)
    if not rows or sw2 == 0:
        return {"Z": 0.0, "N_eff": 0.0, "cap": "C", "pass_line": False, "clusters": rows}
    Z = sum(r["w_c"] * r["z_c"] for r in rows) / math.sqrt(sw2)
    N_eff = sw ** 2 / sw2
    cap = "A 敢说" if (N_eff >= 2 and hit >= 2) else ("B 方向稳" if N_eff >= 1 else "C 解释得住")
    out = {"Z": round(Z, 3), "N_eff": round(N_eff, 2), "cap": cap,
           "pass_line": bool(abs(Z) > z_crit and N_eff >= 2 and hit >= 2),
           "hit": hit, "clusters": rows}
    if verbose:
        print(f"{'簇':<22}{'条':>3}{'各条 z':<22}{'簇 z':>7}{'w_c':>6}")
        for r in rows:
            print(f"{str(r['cluster'])[:21]:<22}{r['n']:>3}{str(r['avg_of']):<22}"
                  f"{r['z_c']:>7.2f}{r['w_c']:>6.2f}")
        print(f"\n合并 Z = {out['Z']:+.3f}（红线 {z_crit}）｜有效独立源数 N_eff = {out['N_eff']}"
              f"（{len(rows)} 簇）｜前瞻命中 {hit}｜**档位封顶 = {cap}**｜过线 = {out['pass_line']}")
        print("※ 簇内取加权平均＝承认它们不独立；「三个术都说一样」只算一个源。")
        if N_eff < 2:
            print("※ N_eff<2：不论 Z 多大都不许升 A —— A 档唯一进货口是前瞻盲测命中 ≥2。")
        if hit < 2 and N_eff >= 2:
            print(f"※ 前瞻命中 {hit}<2：仍封顶 B（这是 A 档的硬门槛，不是样本量问题）。")
    return out


def demo():
    print("── 演示 1：多术合参（同一时刻，八字＋六爻＋奇门＋大六壬都同向）──")
    w = "1993-02-01T03"
    merge([{"name": "八字·杀印相生", "z": 2.2, "cluster": "同刻" + w, "kind": "L2"},
           {"name": "六爻·官鬼持世", "z": 2.0, "cluster": "同刻" + w, "kind": "L2"},
           {"name": "奇门·开门临宫", "z": 1.8, "cluster": "同刻" + w, "kind": "L2"},
           {"name": "大六壬·贵人课", "z": 1.6, "cluster": "同刻" + w, "kind": "L2"}])
    print("\n── 演示 2：同刻四术 ＋ 一条现实回报（真有回执）──")
    merge([{"name": "八字", "z": 2.2, "cluster": "同刻" + w, "kind": "L2"},
           {"name": "六爻", "z": 2.0, "cluster": "同刻" + w, "kind": "L2"},
           {"name": "现实回报", "z": 2.4, "cluster": "现实", "kind": "L4"}])
    print("\n── 演示 3：同库换层回看四条（假独立）──")
    merge([{"name": "全字口径", "z": 2.9, "cluster": "同库", "kind": "L2r"},
           {"name": "天干口径", "z": 2.7, "cluster": "同库", "kind": "L2r"},
           {"name": "回复层出口", "z": 2.5, "cluster": "同库", "kind": "L2r"},
           {"name": "素材层出口", "z": 2.6, "cluster": "同库", "kind": "L2r"}])
    print("\n── 演示 4：两条真异源（异库异测量）同号 ──")
    merge([{"name": "回复层", "z": 2.58, "cluster": "src-回复层", "kind": "L3"},
           {"name": "素材层", "z": 2.98, "cluster": "src-素材层", "kind": "L3"}])


def table():
    print(f"{'类别':<7}{'w':>6}  说明")
    for k, v in W.items():
        print(f"{k:<7}{v:>6.2f}  {DESC[k]}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "--demo":
        demo()
    elif a[0] == "--table":
        table()
    else:
        hit = int(a[a.index("--hit") + 1]) if "--hit" in a else 0
        merge(json.load(open(a[0])), hit=hit)
