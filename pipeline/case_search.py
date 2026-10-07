#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""case_search.py — 跨单元检索（同类盘查找）【定版】

为什么需要它：库内有的日柱/月令只有 1–2 例（庚子、己巳…），单看一个盘看不出规律。
要形成判断，得把**同结构**的盘凑在一起比——这就是「跨单元检索」：不按批号，按**盘的结构**。

三处口径修正（2026-10-09；旧 `retrieval_api.py` 三个病）：
  ① 十神尺：旧用 `shishen_config`（只数天干 ∧ **日主计入比肩**＝病）⇒ 改 `shishen_quan`（全字·日主不计）。
  ② 相似度：旧把十神**二值化**（有/无），丢掉「重不重」——而「偏重/缺位」正是要信息量最大的那一维。改为**原始计数余弦**。
  ③ 输出：旧只给一句 `verdict`（看不出是哪来的）⇒ 现在**必须带 `verdict_layer`**：
     「测量层」＝句子里有可核查事件（能当证据）；「批注层」＝我方批注（只能参考）。

用法：
  python3 scripts/case_search.py --case-id 123 --top 8
  python3 scripts/case_search.py --pillars "丁卯 辛亥 戊子 癸丑" --top 8
  python3 scripts/case_search.py --tags 杀印相生,财偏重 --ri 戊 --top 8
  python3 scripts/case_search.py --case-id 123 --json /tmp/r.json
"""
import argparse, json, os, sqlite3, sys
from collections import Counter

DB = os.environ.get("JINXIANG_DB", "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db")
GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
SHISHEN = ["比肩", "劫财", "食神", "伤官", "正财", "偏财", "正官", "七杀", "正印", "偏印"]
AXES = {"比劫": ("比肩", "劫财"), "财": ("正财", "偏财"), "官杀": ("正官", "七杀"),
        "印": ("正印", "偏印"), "食伤": ("食神", "伤官")}
W = {"shishen": 0.34, "wx": 0.22, "char": 0.16, "hechong": 0.13, "struct": 0.15}
FOCUS_GE = 4          # 与 mech_thresholds.json 的 structural.focus_ge 保持一致（分位 q80）


def J(x, d):
    try:
        v = json.loads(x or "")
        return v if v is not None else d
    except Exception:
        return d


def cos(a, b, keys):
    va = [a.get(k, 0) for k in keys]; vb = [b.get(k, 0) for k in keys]
    na = sum(x * x for x in va) ** .5; nb = sum(y * y for y in vb) ** .5
    return (sum(x * y for x, y in zip(va, vb)) / (na * nb)) if na and nb else 0.0


def jac(a, b):
    a, b = set(a), set(b)
    if not a and not b:
        return 0.5
    return len(a & b) / len(a | b) if (a | b) else 0.5


def hechong(q, c):
    tot = 0.0
    for col in ("he_list", "chong_list", "hui_list", "xing_list"):
        qh, ch = bool(J(q[col], [])), bool(J(c[col], []))
        tot += 0.7 if (qh and ch) else (0.2 if (qh or ch) else 0.5)
    return tot / (4 * 0.7)


def axes_of(ss):
    return {k: sum(ss.get(g, 0) for g in v) for k, v in AXES.items()}


def struct_tags(ss):
    """与 mechanism_tag.calc_structural 同一口径（偏重≥4／缺位=0／否则均平）"""
    ax = axes_of(ss)
    out = [f"{k}偏重" for k, v in ax.items() if v >= FOCUS_GE]
    if not out:
        out = [f"{k}缺" for k, v in ax.items() if v == 0] or ["十神均平"]
    return out


def sim(q, c):
    q_ss, c_ss = J(q["shishen_quan"], {}), J(c["shishen_quan"], {})
    wxs, ss = jac(J(q["wx_consensus"], []), J(c["wx_consensus"], [])), cos(q_ss, c_ss, SHISHEN)
    char = cos({**J(q["tian_gan_freq"], {}), **J(q["di_zhi_freq"], {})},
               {**J(c["tian_gan_freq"], {}), **J(c["di_zhi_freq"], {})}, list(GAN + ZHI))
    hc = hechong(q, c)
    st = jac(struct_tags(q_ss), struct_tags(c_ss))
    s = W["shishen"] * ss + W["wx"] * wxs + W["char"] * char + W["hechong"] * hc + W["struct"] * st
    return s, {"十神": round(ss, 3), "五行": round(wxs, 3), "干支": round(char, 3),
               "合冲": round(hc, 3), "结构": round(st, 3)}


COLS = ("case_id,batch_no,case_no,gender,rizhu,yueling,year_pillar,month_pillar,day_pillar,"
        "hour_pillar,shishen_quan,wx_consensus,tian_gan_freq,di_zhi_freq,he_list,chong_list,"
        "hui_list,xing_list,verdict_raw,verdict_layer,verdict_domains,mech_primary,mech_aux,"
        "pattern_switches,verdict_conf")


def load_all(con):
    return [dict(r) for r in con.execute(f"select {COLS} from case_features")]


def filter_only(a, rows):
    """无参考盘时的纯过滤清单：按 case_id 排序，不评分"""
    pool = list(rows)
    if a.tags:
        want = [t.strip() for t in a.tags.split(",") if t.strip()]
        pool = [r for r in pool if all(t in ([r["mech_primary"]] + J(r["mech_aux"], [])) for t in want)]
    if a.ri:
        pool = [r for r in pool if (r["rizhu"] or "")[:1] == a.ri]
    if a.yue:
        pool = [r for r in pool if r["yueling"] == a.yue]
    return pool


def resolve_query(con, a, rows):
    if a.case_id:
        q = next((r for r in rows if r["case_id"] == a.case_id), None)
        return q, (f"case_id={a.case_id}" if q else f"❌ case_id {a.case_id} 不存在")
    if a.pillars:
        p = a.pillars.split()
        if len(p) != 4:
            return None, "❌ --pillars 需要 4 个（年 月 日 时）"
        q = next((r for r in rows if [r["year_pillar"], r["month_pillar"], r["day_pillar"],
                                      r["hour_pillar"]] == p), None)
        if q:
            return q, f"四柱命中 case_id={q['case_id']}"
        return None, "❌ 库内无此四柱（库是他人命例集，不是排盘工具；排盘请用 mingyu）"
    return None, "❌ 需要 --case-id 或 --pillars"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-id", type=int)
    ap.add_argument("--pillars")
    ap.add_argument("--tags", help="逗号分隔的机制/结构标签（筛选候选池，非查询盘）")
    ap.add_argument("--ri", help="日主天干（筛选）")
    ap.add_argument("--yue", help="月令地支（筛选）")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--json")
    a = ap.parse_args()
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    rows = load_all(con)
    q, why = resolve_query(con, a, rows)
    if not q and (a.tags or a.ri or a.yue):        # 纯过滤模式
        pool = filter_only(a, rows)
        print(f"过滤清单：{' '.join(x for x in [a.tags, ('日主' + a.ri) if a.ri else '', ('月令' + a.yue) if a.yue else ''] if x)}"
              f" ⇒ 命中 {len(pool)} 例（按 case_id 排序，未评分）")
        print(f"{'#':<3}{'case_id':<8}{'四柱':<20}{'日主':<5}{'月令':<5}标签 / 出口层")
        for i, c in enumerate(sorted(pool, key=lambda r: r["case_id"])[:a.top], 1):
            pil = f"{c['year_pillar']} {c['month_pillar']} {c['day_pillar']} {c['hour_pillar']}"
            tags = "/".join([c["mech_primary"]] + J(c["mech_aux"], []))[:32]
            layer = c["verdict_layer"] or "—"
            print(f"{i:<3}{c['case_id']:<8}{pil:<20}{(c['rizhu'] or '')[:1]:<5}{(c['yueling'] or ''):<5}{tags}  [{layer}]")
        print(f"\n（要按相似度排序，请再加 --case-id 或 --pillars 指定参考盘）")
        return
    if not q:
        print(why); sys.exit(1)
    pool = [r for r in rows if r["case_id"] != q["case_id"]]
    if a.tags:
        want = [t.strip() for t in a.tags.split(",") if t.strip()]
        pool = [r for r in pool if all(t in ([r["mech_primary"]] + J(r["mech_aux"], [])) for t in want)]
    if a.ri:
        pool = [r for r in pool if (r["rizhu"] or "")[:1] == a.ri]   # rizhu 存的是「日柱」两字
    if a.yue:
        pool = [r for r in pool if r["yueling"] == a.yue]
    scored = []
    for c in pool:
        s, br = sim(q, c)
        scored.append((s, br, c))
    scored.sort(key=lambda x: -x[0])
    q_ss = J(q["shishen_quan"], {})
    print(f"查询：{q['year_pillar']} {q['month_pillar']} {q['day_pillar']} {q['hour_pillar']}"
          f"（{q['gender']} 日主{q['rizhu']} 月令{q['yueling']}）｜{why}")
    print(f"主标签 {q['mech_primary'] or '—'} ｜ 结构 {','.join(struct_tags(q_ss)) or '—'}"
          f" ｜ 候选池 {len(pool)} 例 → 取前 {a.top}")
    print(f"权重 {W}\n")
    print(f"{'#':<3}{'case_id':<8}{'四柱':<20}{'总分':>6}  成分(十神/五行/干支/合冲/结构)  标签 / 出口层")
    out = []
    for i, (s, br, c) in enumerate(scored[:a.top], 1):
        pil = f"{c['year_pillar']} {c['month_pillar']} {c['day_pillar']} {c['hour_pillar']}"
        tags = "/".join([c["mech_primary"]] + J(c["mech_aux"], []))[:34]
        layer = c["verdict_layer"] or "—"
        flag = "✔测量层" if layer == "测量层" else ("批注层*" if layer == "批注层" else layer)
        print(f"{i:<3}{c['case_id']:<8}{pil:<20}{s:>6.3f}  "
              f"{br['十神']:.2f}/{br['五行']:.2f}/{br['干支']:.2f}/{br['合冲']:.2f}/{br['结构']:.2f}  "
              f"{tags}  [{flag}]")
        out.append({"rank": i, "score": round(s, 4), "case_id": c["case_id"],
                    "batch_no": c["batch_no"], "case_no": c["case_no"], "pillars": pil,
                    "gender": c["gender"], "rizhu": c["rizhu"], "yueling": c["yueling"],
                    "mech_primary": c["mech_primary"], "mech_aux": J(c["mech_aux"], []),
                    "struct": struct_tags(J(c["shishen_quan"], {})), "breakdown": br,
                    "verdict_raw": (c["verdict_raw"] or "")[:200],
                    "verdict_layer": layer, "verdict_domains": c["verdict_domains"] or "",
                    "pattern_switches": J(c["pattern_switches"], [])})
    print("\n* 批注层＝我方批注（只能参考）；只有「测量层」带可核查事件，可当证据。")
    if a.json:
        json.dump({"query": {"case_id": q["case_id"], "pillars": " ".join(
            [q["year_pillar"], q["month_pillar"], q["day_pillar"], q["hour_pillar"]]),
            "mech_primary": q["mech_primary"], "struct": struct_tags(q_ss)},
            "weights": W, "results": out}, open(a.json, "w", encoding="utf-8"),
            ensure_ascii=False, indent=1)
        print(f"→ {a.json}")
    con.close()


if __name__ == "__main__":
    main()
