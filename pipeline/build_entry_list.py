#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""压缩法 · 条目清单生成器 v2.0
产物：distill/entry-list.md（人读）+ distill/entries.json（机器读）

v2.0（2026-10-07，任务11 ／ 自审 H5「条目条件≠实测判据」）——**消掉两份真相**：
  · 条件 `cond` / 条目名 `name` / 方向 `dir` / 口径 `cal`：一律由 `entries_spec.py` **渲染**，册子不准手写；
  · 状态 `status` / 结果 `res` / 档位 `grade`：一律由 `score-splithalf.txt` **机器写入**；
  · 手写只剩「机制 / 边界 / 出处」三样散文 → `entry-prose.json`（冻结留档，不参与判定）。
  ⇒ 条件与判定出自同一份规格，**物理上不可能漂移**。

纪律（用户 2026-10-07 拍板：方法2 + 三道闸）：
  闸一 归组 —— 真正参与校正的是「轴」数，不是条目数
  闸二 两段 —— 一半发现（宽进）/ 一半确认（严出），确认不过不进「敢说清单」
  闸三 未蒸清单 —— 落不进「条件+方向+机制」三格的，登记在册，不偷丢
"""
import json, os, re, sys, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import entries_spec as SPEC

# 库当前可算字段（条件必须落在这里面，否则进未蒸清单）
FIELDS = [
    "rizhu 日柱", "yueling 月令", "四柱", "gender",
    "shishen_quan 8字十神", "shishen_benqi 本气十神", "shishen_config 天干十神(旧)",
    "tonggen 通根", "he_list 合", "chong_list 冲", "hui_list 会", "xing_list 刑",
    "wx_standard/conservative/blind/consensus 五行旺衰",
    "dayun_sequence 大运", "qiyun_age 起运", "pattern_switches 格局开关",
]
# 结局域（case_outcomes / case_features.verdict_domains）
DOMAINS = ["财(521)", "婚姻(297)", "寿元(212)", "功名(176)", "刑灾官非(~60)", "六亲(~64)"]

AXES = [
    ("AX-01", "十神单字轴", "某十神在指定口径(8字/本气/天干)的个数", "对应事类"),
    ("AX-02", "格局成破轴", "两个十神共现(成格/破格组合)", "功名/财/刑灾/婚姻"),
    ("AX-03", "强弱根气轴", "身强弱 + 有无支根 + 个数梯度", "全体事类"),
    ("AX-04", "宫位轴", "某十神落在年/月/日/时哪一柱", "六亲/事业/婚姻"),
    ("AX-05", "夫妻宫轴", "日支被合/冲/刑", "婚姻"),
    ("AX-06", "五行配置轴", "五行个数/缺失/偏枯", "寿元/性情/财"),
    ("AX-07", "墓库轴", "有无辰戌丑未 + 何五行入墓", "刑灾/事业持续性"),
    ("AX-08", "调候轴", "月令季节 × 日主 × 寒暖燥湿", "层次/健康"),
    ("AX-09", "女命夫星轴", "官杀显隐/混杂/根气", "婚姻"),
    ("AX-10", "岁运应期轴", "大运/流年与原局字的关系(填实/冲/合)", "应期(限 case_events 子集)"),
    ("AX-11", "财富载体轴", "财挂哪个载体(财<食伤<官殺/禄)", "财/功名"),
]

UNSTEAMED = [
    ("空亡类", "库无空亡字段（日支/夫星空亡等）", "先造字段，再入 AX-05/AX-09"),
    ("神煞类", "库无神煞字段（亡神/贵人/羊刃按神煞口径）", "道秀有 6+ 条神煞判据，需造字段"),
    ("象法/职业取象", "职业以自由文本存在，未结构化（土主信+官杀=信贷 等）", "需职业文本抽取，属另一条工程线"),
    ("健康域", "库无健康结局域（水多火弱→上热下寒 等）", "实盘专用，库内无对应结局"),
    ("巾箱 1817 条单格诀", "域锁死「日柱×月令」，每格 n≈3，统计层无解", "只当 C 档参照，不进统计层（体例天花板）"),
    ("基外成分（风水/时代/选择/关系）", "不在四柱可算范围内", "按 first-principles §5：模糊出在「认不全」，须承认此限"),
]

# 四档（与 SKILL.md 第 4 节同源；A 档只能由前瞻账本进货）
GRADE_RULE = ("A = 五格齐全 ∧ 强度过可检出线 ∧ **前瞻盲测命中 ≥2**（当前空集）｜"
              "B = 库内**异源异测量**一致（跨源×跨半）｜C = 仅单源/单半，解释得住｜"
              "✗ = 已测全平（该条不成立）｜— = 测不动/未跑")


def grade_of(ms, hits):
    if hits is None:
        return "—"
    if hits >= 2:
        return "A"
    return {"ok": "B", "half": "C", "flat": "✗", "stuck": "—", "none": "—"}.get(ms, "—")


def load_claims():
    """条目 → 前瞻账本 claim id 的映射（唯一的「手写」，且受账本审计）。缺省＝没有映射。"""
    p = os.path.join(HERE, "entry-claims.json")
    if not os.path.exists(p):
        return {}
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


def ledger_hits():
    """从自审账本数「前瞻命中」总数（只认 kind=prospective ∧ result=hit）。"""
    p = os.path.expanduser("~/.hermes/profiles/see/skills/mingli/mingli-self-audit/scripts/ledger.jsonl")
    n = 0
    if not os.path.exists(p):
        return 0
    for ln in open(p, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("kind") == "prospective" and str(d.get("result", "")).lower().startswith("hit"):
            n += 1
    return n


def load_prose():
    p = os.path.join(HERE, "entry-prose.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def load_scores(here):
    """从 score-splithalf.txt 读「机器状态」——状态的真源是打分器，不是手写。"""
    p = os.path.join(here, "score-splithalf.txt")
    if not os.path.exists(p):
        return set(), [], set(), {}, set()
    NUM, AGREE, CROSS, ROWS, REG = set(), [], set(), {}, set()
    sec = ""
    for ln in open(p, encoding="utf-8"):
        s = ln.rstrip("\n")
        if s.startswith("=="):
            sec = s.strip("= ").split("（")[0]
            continue
        if sec == "两源都进上表":
            for part in s.strip().split(","):
                part = part.strip()
                if "·" in part:
                    e, o = part.split("·"); CROSS.add((e.strip(), o.strip()))
            continue
        if sec.startswith("两半一致"):
            m = re.match(r"^\s*([-+\d.]+)\s+(\S+)\s+(\S+)\s+([LSXG])\s+([ABT])", s)
            if m:
                AGREE.append((float(m.group(1)), m.group(2), m.group(4), m.group(5)))
            continue
        m = re.match(r"^(\S+)\s+(\S+)\s+([LSXG])\s+([ABT])\s+(\d+)\s+([-+\d.]+)\s+([-+\d.]+)\s+(\S+)\s*(.*)$", s)
        if m:
            REG.add(m.group(1)); NUM.add(m.group(1))
            ROWS.setdefault(m.group(1), []).append(
                (m.group(3), m.group(4), int(m.group(5)), float(m.group(6)), float(m.group(7)),
                 m.group(8), m.group(9)))
            continue
        m = re.match(r"^(\S+)\s+(\S+)\s+([LSXG])\s+([ABT])\s+(\d+)\s+\S+\s+\S+\s+(\S+)\s*(.*)$", s)
        if m:   # 无数字行（样本不足／无变异）也要登记：否则该类条目被误判成「没进打分器」
            REG.add(m.group(1))
            ROWS.setdefault(m.group(1), []).append(
                (m.group(3), m.group(4), int(m.group(5)), None, None, m.group(6), m.group(7)))
    return NUM, AGREE, CROSS, ROWS, REG


def mstat(eid, NUM, AGREE, CROSS, ROWS, REG):
    """机器状态：ok=跨源×跨半 / half=仅两半 / flat=已测无信号 / stuck=测不动 / none=未进打分器。"""
    a = [x for x in AGREE if x[1] == eid]
    if a and any((eid, x[2]) in CROSS for x in a):
        top = max(a)
        return "ok", f"跨源复现（{top[2]}·{top[3]}）最强半 {top[0]:+.2f}"
    if a:
        top = max(a)
        bad = [r for r in ROWS.get(eid, []) if r[5] != "OK"]
        extra = "；最强出口不健康" if bad else ""
        if top[2] == "G":
            extra += "；G 是代理出口（不是靶域）"
        return "half", f"两半一致（{top[2]}·{top[3]}）最强半 {top[0]:+.2f}{extra}"
    if eid in NUM:
        return "flat", "已测、无信号（全平）"
    if eid in REG:
        return "stuck", "测不动（结局/预测子无变异，或 n 不足）"
    return "none", "未进打分器（未注册／已列「跳过」）"


def main():
    here = HERE
    meta = SPEC.meta()
    prose = load_prose()
    claims = load_claims()
    NUM, AGREE, CROSS, ROWS, REG = load_scores(here)

    # 变体自动补登：打分器测过但规格表没登记的编号（口径变体）→ 从本体克隆，避免「测了却没底账」
    for sid in sorted(REG):
        if sid in meta:
            continue
        stem = sid.rstrip("xmy")
        if stem in meta:
            m = dict(meta[stem])
            m.update(id=sid, auto=True,
                     variant_of=stem, variant_note=f"口径变体（打分器自动补登 {sid[len(stem):]}）")
        else:
            m = dict(id=sid, domain="?", sign=0, gate=None, cond="（未登记）",
                     cal="", dir="（未登记）", variant_of=None, variant_note="", spec=None)
        meta[sid] = m
        prose.setdefault(sid, dict(mech=prose.get(stem, {}).get("mech", ""),
                                  bnd=prose.get(stem, {}).get("bnd", ""),
                                  src=(prose.get(stem, {}).get("src", "") + "（自动补登）").strip("（）"),
                                  res_note="", status_hand=""))

    def resolve(eid):
        """本体编号有时只以变体形式入册（如 AX01-07 只有 AX01-07x 被注册）——认领变体，别误报「没测」。"""
        if eid in REG:
            return eid, ""
        for suf in ("x", "m", "y"):
            if eid + suf in REG:
                return eid + suf, f"（本体按变体 {suf} 计）"
        return eid, ""

    entries, drift, lag = [], [], []
    for eid in sorted(meta):
        m = meta[eid]
        rid, rnote = resolve(eid)
        ms, mres = mstat(rid, NUM, AGREE, CROSS, ROWS, REG)
        if m.get("kind") == "declared":
            ms, mres = "none", "未蒸：判定函数未建（库缺字段／算法／结局域）"
        elif m.get("kind") == "method":
            ms, mres = "none", "口径效应——是尺子不是条目，不进统计层"
        cands = [prose.get(eid), prose.get(m.get("variant_of") or ""), prose.get(m.get("alias_of") or "")]
        pr = next((c for c in cands if c and (c.get("mech") or c.get("bnd") or c.get("src"))), cands[0] or {})
        # 前瞻命中：只认账本里 kind=prospective ∧ result=hit 的 claim（当前 0 条 ⇒ A 档空集）
        hits = sum(1 for c in claims.get(eid, []) if c in HIT_IDS)
        cond = m["cond"] + rnote
        name = re.sub(r"（[^）]*）", "", cond) + " → " + m["dir"]
        rec = dict(
            id=eid, axis="AX-" + eid[2:4], name=name,
            cond=cond, cal=m["cal"], dir=m["dir"], domain=m["domain"], sign=m["sign"],
            gate=m["gate"], mech=pr.get("mech", ""), bnd=pr.get("bnd", ""), src=pr.get("src", ""),
            status=ms, grade=grade_of(ms, hits), hits=hits, res=mres,
            res_note=pr.get("res_note", ""), variant_of=m.get("variant_of"),
            variant_note=m.get("variant_note", ""), auto=m.get("auto", False),
            kind=m.get("kind", "cond"), alias_of=m.get("alias_of"),
            spec=m.get("spec"),
        )
        entries.append(rec)
        # 体检：冻结的手写状态 vs 机器（历史漂移证据，手写不再当状态）
        sh = (prose.get(eid) or {}).get("status_hand", "")   # 只认本编号自己的手写状态（不继承本体）
        if m.get("kind") in ("declared", "method"):
            sh = ""            # 非统计条目：手写状态没有「换口径」可言
        if sh in ("ok", "half") and ms in ("flat", "none", "stuck"):
            drift.append(f"| {eid} | {sh} | {ms} | 旧结果（已换口径）→ 现行口径全平／测不到 |")
        elif sh in ("ok", "half") and ms != sh:
            lag.append(f"{eid}({sh}→{ms})")
        elif sh == "wait" and ms in ("ok", "half", "flat"):
            lag.append(f"{eid}(wait→{ms})")

    # 家族（本体↔变体）索引
    fam = {}
    for e in entries:
        stem = e["variant_of"] or e["id"]
        fam.setdefault(stem, []).append(e["id"])
    for e in entries:
        e["variants"] = [x for x in fam.get(e["id"], []) if x != e["id"]]

    md5 = hashlib.md5(open(os.path.join(here, "score-splithalf.txt"), "rb").read()).hexdigest()[:12]
    try:
        from score_entries import K_TESTS, ZC
    except Exception:
        K_TESTS, ZC = 13, 2.86
    payload = dict(
        version="2.0",
        built="2026-10-07",
        stamp=dict(source="score-splithalf.txt", md5=md5, K_TESTS=K_TESTS, ZC=ZC,
                   ruler_ver=2, shishen_col="shishen_quan", cal="全字口径·含藏干（日主不计）"),
        protocol=dict(
            gate1="归组：校正按「轴」数计（11 轴），组内细条目当稳健性变体",
            gate2="两段：半库发现（宽进）/ 半库确认（严出），确认不过不进「敢说清单」",
            gate3="未蒸清单：落不进三格者登记在册，不偷丢",
            single_source="cond/name/dir/cal 由 entries_spec.py 渲染；status/res/grade 由打分器写入——册子禁手写",
        ),
        grade_rule=GRADE_RULE,
        fields=FIELDS, domains=DOMAINS,
        axes=[dict(id=a, name=n, cond=c, domain=d) for a, n, c, d in AXES],
        entries=entries,
        unsteamed=[dict(name=n, why=w, next=x) for n, w, x in UNSTEAMED],
    )
    with open(os.path.join(here, "entries.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    # ---------- 人读版 ----------
    MICON = {"ok": "★★跨源", "half": "★两半", "flat": "▫无信号", "stuck": "⬜测不动", "none": "❓未跑"}
    KICON = {"declared": "〔未蒸〕", "method": "〔尺子〕", "base": "〔本体〕"}

    def tag(e):
        return KICON.get(e["kind"], MICON[e["status"]])
    L = []
    L.append("# 压缩法 · 条目清单（蒸馏产物 v2.0）\n")
    L.append("> 生成：`distill/build_entry_list.py` ｜ 预注册日期 2026-10-07 ｜ **先写下来才算数**")
    L.append(f"> **单一真相源**：条件/名/方向/口径 由 `entries_spec.py` 渲染（禁手写）；"
             f"状态/结果/档位 由 `score-splithalf.txt`（md5 `{md5}`）机器写入")
    L.append(f"> 四源合成：子平真诠系(骨架/边界) + 巾箱(条件) + 道秀(机制/时间窗) + 案例库(强度)｜"
             f"校正线 K={K_TESTS} ⇒ ZC={ZC}\n")
    nk = {}
    for e in entries:
        nk[e["kind"]] = nk.get(e["kind"], 0) + 1
    L.append(f"当前 **{len(entries)} 条记录** = 机器判定 **{nk.get('cond',0)}**（进统计层）"
             f" ＋ 本体 {nk.get('base',0)} ＋ 未蒸 {nk.get('declared',0)} ＋ 尺子 {nk.get('method',0)}；"
             f"归 **{len(AXES)} 个轴**（多重比较校正按轴计，不是按条数）\n")

    L.append("## 〇 · 档位规则（与 SKILL.md 第 4 节同源）\n")
    L.append(GRADE_RULE + "\n")
    L.append(f"**前瞻账本命中**：{HIT_TOTAL} 条 ⇒ A 档{'空集' if HIT_TOTAL < 2 else '有条目'}"
             f"（A 档只能由前瞻进货；库内封顶 B「库内最强」）\n")

    L.append("## 一 · 条目清单（条件＝**渲染**；状态/档位＝**机器写入**）\n")
    for a, n, c, d in AXES:
        es = [e for e in entries if e["axis"] == a]
        if not es:
            continue
        L.append(f"### {a} {n}\n")
        L.append("| 编号 | 条件（机器渲染） | 口径 | 方向 | 档位 | 机制 | 边界 | 出处 | 状态（机器） |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for e in es:
            L.append(f"| {e['id']} | {e['cond']} | {e['cal']} | {e['dir']} | "
                     f"**{e['grade']}** | {e['mech']} | {e['bnd']} | {e['src']} | "
                     f"{tag(e)}：{e['res']} |")
        L.append("")

    cnts, gcnts = {}, {}
    mach = [e for e in entries if e["kind"] == "cond"]
    for e in mach:
        cnts[e["status"]] = cnts.get(e["status"], 0) + 1
        gcnts[e["grade"]] = gcnts.get(e["grade"], 0) + 1
    L.append("**状态统计（机器）**：" + " ｜ ".join(f"{MICON[k]} {cnts.get(k, 0)} 条"
                                               for k in ("ok", "half", "flat", "stuck", "none")) + "\n")
    L.append("**档位统计**：" + " ｜ ".join(f"{k} {gcnts.get(k, 0)} 条"
                                            for k in ("A", "B", "C", "✗", "—")) + "\n")
    L.append(f"> 状态与档位以打分器为准。手写状态只当历史备注（冻结于 `entry-prose.json`），"
             f"**漂移本身就是体检结果**。\n")
    L.append("**A 类：手写有结果、当前口径测不出来**——旧数字多来自别的口径／别的出口，"
             "**别拿旧口径的数字当现行证据**：\n")
    L.append("| 编号 | 手写 | 机器 | 说明 |")
    L.append("|---|---|---|---|")
    L += (drift if drift else ["| — | — | — | 无 |"])
    L.append("")
    L.append(f"**B 类（无害）手写滞后**——实测已有数、手写没跟上，共 **{len(lag)} 条**：" +
             ("  ".join(lag) if lag else "无"))
    L.append("")

    if fam_variants := {k: v for k, v in fam.items() if len(v) > 1}:
        L.append("## 一·五 · 条目家族（本体 ↔ 变体，显式声明）\n")
        L.append("| 本体 | 变体 | 说明 |")
        L.append("|---|---|---|")
        for stem in sorted(fam_variants):
            for e in entries:
                if e["id"] != stem and (e["variant_of"] == stem):
                    L.append(f"| {stem} | {e['id']} | {e['variant_note']} |")
        L.append("")

    L.append("## 二 · 未蒸清单（登记在册，不偷丢）\n")
    L.append("| 类别 | 为什么没蒸 | 下一步 |")
    L.append("|---|---|---|")
    for n, w, x in UNSTEAMED:
        L.append(f"| {n} | {w} | {x} |")
    L.append("")

    L.append("## 三 · 已备可算字段（条件的落地依据）\n")
    L.append("```")
    for i in range(0, len(FIELDS), 3):
        L.append("  ".join(FIELDS[i:i+3]))
    L.append("```\n")
    L.append("结局域（`case_outcomes` / `case_features.verdict_domains`）：" + " ｜ ".join(DOMAINS))
    L.append("")

    with open(os.path.join(here, "entry-list.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    print(f"OK 条目 {len(entries)} 条 / {len(AXES)} 轴 ｜ 机器状态：" +
          " ".join(f"{k}={cnts.get(k, 0)}" for k in ("ok", "half", "flat", "stuck", "none")))
    print("档位：" + " ".join(f"{k}={gcnts.get(k, 0)}" for k in ("A", "B", "C", "✗", "—")) +
          f" ｜ 前瞻命中 {HIT_TOTAL}")
    print(f"冻结手写 vs 机器 漂移 {len(drift)} 条（手写只当备注，不再当状态）")
    print(f"→ {here}/entry-list.md\n→ {here}/entries.json")


HIT_IDS, HIT_TOTAL = set(), 0
if __name__ == "__main__":
    HIT_TOTAL = ledger_hits()
    HIT_IDS = set()          # 账本 claim 与条目映射靠 entry-claims.json（受账本审计，不手写结论）
    main()
