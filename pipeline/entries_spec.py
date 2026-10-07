#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""条目规格登记表 —— **条目条件的唯一定义处**（single source of truth）

为什么要有这个文件（2026-10-07，任务11 ／ 自审 H5「条目条件≠实测判据」）：
  「条目条件」过去有两份：打分器里的**判定函数**（机器真值）＋ `entries.json` 里
  **手写的 cond 文字**。两份会漂移——实测过：偏财条目写「≥1」，打分器却按原始计数梯度测。
  现在改成：条件只写一次（本文件的 `spec`），**判定函数与中文条件文字都由它生成**。
  文字与判定物理上不可能不一致；条目册里的手写 cond 已整体移除（`build_entry_list.py` 改渲染）。

三条纪律：
  1. **口径自动附**（`CAL`）——条件的口径声明由渲染器追加，禁止在别处另写。
  2. **阈值写绝对值**——换尺不靠改阈值文字，靠重标定（`calibrate_mech.py` 同理）。
  3. **变体显式声明**（`variant_of`）——打分器自动补登的编号必须能溯源到本体。

DSL：见 `build()`（生成判定函数）与 `render()`（生成中文条件）——一一对应，同一个节点。
"""

# ---------- 口径声明（渲染时自动追加） ----------
CAL = {
    "quan": "全字口径·含藏干（日主不计，ruler_ver=2）",
    "tiangan": "天干口径（仅年/月/日/时四柱天干）",
}

# ---------- 底层读数（与老打分器逐字同源，不可改） ----------
def ss_sum(f, names):
    """十神计数。比肩在 ruler_ver=1（修根前）需减 1——旧库把「日干自己」算成了比肩。
    修根后（ruler_ver=2）日主已排除，直接读库值。此兜底是**条件式**，不是常数。"""
    s = 0
    for x in names:
        v = f["ss"].get(x, 0)
        if x == "比肩" and f.get("ver", 1) < 2:
            v = max(0, v - 1)
        s += v
    return s


def tgpos(f, names):
    """某十神出现在四柱**天干**的哪些柱位（年/月/日/时）。"""
    s = set()
    for x in names:
        s |= set(f["tg"].get(x, []))
    return s


def fem(f):
    return 1 if f["g"] in ("坤", "女", "F") else 0


def dayzhi(f):
    return f["day"][1] if f["day"] and len(f["day"]) > 1 else ""


JOIN = {("正财", "偏财"): "财", ("比肩", "劫财"): "比劫", ("正印", "偏印"): "印",
        ("食神", "伤官"): "食伤", ("正官", "七杀"): "官杀"}


def label(names):
    if len(names) == 1:
        return names[0]
    return JOIN.get(tuple(names), "+".join(names))


# ---------- DSL：build() 与 render() 一一对应 ----------
def build(n):
    """节点 → 判定函数。返回 None 表示该例不适用（比 gate 更细的筛）。"""
    k = n["k"]
    if k == "ss":
        names, mode = n["n"], n.get("mode", "count")
        if mode == "count":
            return lambda f: ss_sum(f, names)
        if mode == "gt0":
            return lambda f: 1 if ss_sum(f, names) > 0 else 0
        if mode == "eq0":
            return lambda f: 1 if ss_sum(f, names) == 0 else 0
        if mode == "ge":
            K = n["k2"]
            return lambda f: 1 if ss_sum(f, names) >= K else 0
        if mode == "ord_gt0":      # 只在 >0 的例上取原始计数（其余 None）
            return lambda f: (ss_sum(f, names) if ss_sum(f, names) > 0 else None)
        if mode == "ord_range":    # 只在区间内取原始计数
            lo, hi = n["lo"], n["hi"]
            def g(f):
                v = ss_sum(f, names)
                return v if lo <= v <= hi else None
            return g
        raise ValueError(mode)
    if k == "ssc":                 # 天干口径读数
        names = n["n"]
        return lambda f: 1 if sum(f["ssc"].get(x, 0) for x in names) > 0 else 0
    if k == "tg":
        names, pos = n["n"], set(n["pos"])
        if n.get("want", True):
            return lambda f: 1 if (tgpos(f, names) & pos) else 0
        return lambda f: 1 if not (tgpos(f, names) & pos) else 0
    if k == "zhi":                 # 日支被 冲/合/刑
        ln = n["lst"]
        return lambda f: 1 if any(dayzhi(f) in s for s in f[ln]) else 0
    if k == "wx":
        if n["mode"] == "missing":
            return lambda f: 1 if any(f["wx"].get(w, 0) == 0 for w in "木火土金水") else 0
        K = n["k2"]
        return lambda f: 1 if any(f["wx"].get(w, 0) >= K for w in "木火土金水") else 0
    if k == "pillar_set":
        S = n["set"]
        return lambda f: 1 if any(p and len(p) > 1 and p[1] in S for p in f["pil"]) else 0
    if k == "yl_day":
        return lambda f: (1 if (f["yl"] in n["yl"] and f["day"][0] in n["day"]
                                and f["wx"].get(n["wx"], 0) == 0) else 0) if f["yl"] else None
    if k == "carr":                # 财富载体序数：财(0) < 食伤(1) < 官杀(2)
        def carr(f):
            if ss_sum(f, ["正官", "七杀"]) > 0:
                return 2
            if ss_sum(f, ["食神", "伤官"]) > 0:
                return 1
            if ss_sum(f, ["正财", "偏财"]) > 0:
                return 0
            return None
        return carr
    if k == "all":
        subs = [build(x) for x in n["x"]]
        return lambda f: 1 if all(s(f) for s in subs) else 0
    raise ValueError(k)


def render(n):
    """节点 → 中文条件（口径自动追加）。"""
    k = n["k"]
    if k == "ss":
        names, mode = n["n"], n.get("mode", "count")
        L = label(names)
        if mode == "count":
            return f"{L}计数（原始计数 0/1/2/3，未二值化）"
        if mode == "gt0":
            return f"{L}≥1"
        if mode == "eq0":
            return f"{L}=0"
        if mode == "ge":
            return f"{L}≥{n['k2']}"
        if mode == "ord_gt0":
            return f"{L}计数（仅 {L}>0 的例计入）"
        if mode == "ord_range":
            return f"{L}个数∈[{n['lo']},{n['hi']}]（原始计数）"
        raise ValueError(mode)
    if k == "ssc":
        return f"{label(n['n'])}≥1"
    if k == "tg":
        pos = "、".join(n["pos"])
        if n.get("want", True):
            return f"天干（{pos}）见{label(n['n'])}"
        return f"{label(n['n'])}不透于{pos}"
    if k == "zhi":
        ZHINM = {"ch": "冲", "he": "合", "xing": "刑"}
        return f"日支被{ZHINM[n['lst']]}"
    if k == "wx":
        return "五行缺一" if n["mode"] == "missing" else f"任一五行≥{n['k2']}"
    if k == "pillar_set":
        return f"地支见{n['set']}"
    if k == "yl_day":
        return f"月令∈{n['yl']} 且 日干∈{n['day']} 且 五行无{n['wx']}"
    if k == "carr":
        return "财富载体序数（财0<食伤1<官杀2）"
    if k == "all":
        return " 且 ".join(render(x) for x in n["x"])
    raise ValueError(k)


def render_cal(n):
    """口径声明：出现十神计数就附（自动，禁止别处另写）。"""
    kinds = set()

    def walk(x):
        if x["k"] in ("ss", "ssc", "carr"):
            kinds.add("tiangan" if x["k"] == "ssc" else "quan")
        if x["k"] == "all":
            for y in x["x"]:
                walk(y)
    walk(n)
    return "；".join(CAL[k] for k in ("quan", "tiangan") if k in kinds)


# ---------- 登记表：42 条（id → 域 / 方向 / 性别门 / 规格） ----------
# sign：+1 = 该域等级↑，−1 = ↓（方向由机器渲染，不再手写）
SPEC = [
    # AX-01 十神单字轴
    ("AX01-01", "财", +1, None, {"k": "ss", "n": ["偏财"], "mode": "count"}),
    ("AX01-02", "财", +1, None, {"k": "ss", "n": ["正财"], "mode": "count"}),
    ("AX01-03", "财", -1, None, {"k": "ssc", "n": ["劫财"]}),
    ("AX01-04", "财", -1, None, {"k": "ss", "n": ["劫财"], "mode": "count"}),
    ("AX01-05", "财", -1, None, {"k": "ss", "n": ["比肩"], "mode": "count"}),
    ("AX01-06", "功名事业", +1, None, {"k": "ss", "n": ["正官"], "mode": "count"}),
    ("AX01-07x", "刑灾官非", +1, None, {"k": "ss", "n": ["七杀"], "mode": "count"}),
    ("AX01-08", "婚姻", -1, "fem", {"k": "ss", "n": ["伤官"], "mode": "count"}),
    ("AX01-09", "寿元健康", +1, None, {"k": "ss", "n": ["食神"], "mode": "count"}),
    ("AX01-10", "寿元健康", -1, None, {"k": "all", "x": [
        {"k": "ss", "n": ["偏印"], "mode": "gt0"},
        {"k": "ss", "n": ["食神"], "mode": "gt0"}]}),
    # AX-02 格局成破轴
    ("AX02-01x", "刑灾官非", -1, None, {"k": "all", "x": [
        {"k": "ss", "n": ["正官"], "mode": "gt0"},
        {"k": "ss", "n": ["正印", "偏印"], "mode": "gt0"}]}),
    ("AX02-02", "功名事业", +1, None, {"k": "all", "x": [
        {"k": "ss", "n": ["七杀"], "mode": "gt0"},
        {"k": "ss", "n": ["正印", "偏印"], "mode": "gt0"}]}),
    ("AX02-03x", "刑灾官非", +1, None, {"k": "all", "x": [
        {"k": "ss", "n": ["伤官"], "mode": "gt0"},
        {"k": "ss", "n": ["正官"], "mode": "gt0"}]}),
    ("AX02-03m", "婚姻", -1, "fem", {"k": "all", "x": [
        {"k": "ss", "n": ["伤官"], "mode": "gt0"},
        {"k": "ss", "n": ["正官"], "mode": "gt0"}]}),
    ("AX02-04", "财", -1, None, {"k": "all", "x": [
        {"k": "ss", "n": ["比肩", "劫财"], "mode": "ge", "k2": 2},
        {"k": "ss", "n": ["正财", "偏财"], "mode": "gt0"}]}),
    ("AX02-05x", "刑灾官非", -1, None, {"k": "all", "x": [
        {"k": "ss", "n": ["食神"], "mode": "gt0"},
        {"k": "ss", "n": ["七杀"], "mode": "gt0"}]}),
    ("AX02-06", "功名事业", +1, None, {"k": "all", "x": [
        {"k": "ss", "n": ["正财", "偏财"], "mode": "gt0"},
        {"k": "ss", "n": ["正官"], "mode": "gt0"}]}),
    ("AX02-07", "婚姻", -1, None, {"k": "all", "x": [
        {"k": "ss", "n": ["正官"], "mode": "gt0"},
        {"k": "ss", "n": ["七杀"], "mode": "gt0"}]}),
    ("AX02-08", "功名事业", -1, None, {"k": "all", "x": [
        {"k": "ss", "n": ["七杀"], "mode": "gt0"},
        {"k": "ss", "n": ["食神", "伤官"], "mode": "ge", "k2": 2},
        {"k": "ss", "n": ["正印", "偏印"], "mode": "eq0"}]}),
    # AX-03 强弱根气轴
    ("AX03-01x", "刑灾官非", +1, None, {"k": "ss", "n": ["七杀"], "mode": "ord_gt0"}),
    ("AX03-02", "功名事业", -1, None, {"k": "ss", "n": ["正官", "七杀"], "mode": "ord_range", "lo": 1, "hi": 4}),
    ("AX03-03x", "刑灾官非", +1, None, {"k": "all", "x": [
        {"k": "ss", "n": ["比肩", "劫财"], "mode": "eq0"},
        {"k": "ss", "n": ["正印", "偏印"], "mode": "eq0"}]}),
    ("AX03-04", "财", -1, None, {"k": "all", "x": [
        {"k": "ss", "n": ["正财", "偏财"], "mode": "ge", "k2": 3},
        {"k": "ss", "n": ["比肩", "劫财"], "mode": "eq0"},
        {"k": "ss", "n": ["正印", "偏印"], "mode": "eq0"}]}),
    # AX-04 宫位轴
    ("AX04-01", "功名事业", +1, None, {"k": "tg", "n": ["正官", "七杀"], "pos": ["年", "月"]}),
    ("AX04-02x", "刑灾官非", +1, None, {"k": "tg", "n": ["七杀"], "pos": ["日", "时"]}),
    ("AX04-03", "财", +1, None, {"k": "tg", "n": ["正财", "偏财"], "pos": ["年", "月"]}),
    # 域键纠错（2026-10-07）：原挂「六亲」（语料仅 135 例、130 为丧父母，出口天生单极）；
    # 库内有独立「子女」域（60 例，吉凶 22/36 ⇒ 二值出口健康）。域键写错＝白卡死。
    ("AX04-04x", "子女", -1, "fem", {"k": "tg", "n": ["伤官"], "pos": ["时"]}),
    ("AX04-04y", "子女", -1, None, {"k": "tg", "n": ["伤官"], "pos": ["时"]}),
    # AX-05 夫妻宫轴
    ("AX05-01", "婚姻", -1, None, {"k": "zhi", "lst": "ch"}),
    ("AX05-02", "婚姻", -1, None, {"k": "zhi", "lst": "he"}),
    ("AX05-03", "婚姻", -1, None, {"k": "zhi", "lst": "xing"}),
    # AX-06 五行配置轴
    ("AX06-01", "寿元健康", -1, None, {"k": "wx", "mode": "missing"}),
    ("AX06-02x", "刑灾官非", +1, None, {"k": "wx", "mode": "ge", "k2": 4}),
    # AX-07 墓库轴
    ("AX07-01", "功名事业", +1, None, {"k": "pillar_set", "set": "辰戌丑未"}),
    # AX-08 调候轴
    ("AX08-01", "功名事业", -1, "yl", {"k": "yl_day", "yl": "亥子丑", "day": "丙丁", "wx": "火"}),
    ("AX08-02", "功名事业", -1, "yl", {"k": "yl_day", "yl": "巳午未", "day": "壬癸", "wx": "水"}),
    # AX-09 女命夫星轴
    ("AX09-01", "婚姻", -1, "fem", {"k": "all", "x": [
        {"k": "ss", "n": ["正官", "七杀"], "mode": "gt0"},
        {"k": "tg", "n": ["正官", "七杀"], "pos": ["日", "时"], "want": False}]}),
    ("AX09-02", "婚姻", -1, "fem", {"k": "all", "x": [
        {"k": "ss", "n": ["正官"], "mode": "gt0"},
        {"k": "ss", "n": ["七杀"], "mode": "gt0"}]}),
    ("AX09-03", "婚姻", -1, "fem", {"k": "all", "x": [
        {"k": "ss", "n": ["比肩", "劫财"], "mode": "eq0"},
        {"k": "ss", "n": ["正印", "偏印"], "mode": "eq0"}]}),
    ("AX09-04", "婚姻", -1, "fem", {"k": "all", "x": [
        {"k": "ss", "n": ["伤官"], "mode": "gt0"},
        {"k": "ss", "n": ["正官"], "mode": "gt0"}]}),
    ("AX09-05", "婚姻", -1, "fem", {"k": "ss", "n": ["正官", "七杀"], "mode": "eq0"}),
    # AX-11 财富载体轴
    ("AX11-01", "财", +1, None, {"k": "carr"}),
]

# 声明变体：编号 → 本体 + 变体理由（打分器自动补登的编号必须能溯源）
VARIANT = {
    "AX01-07x": ("AX01-07", "域变体：七杀挂刑灾官非（另挂功名）"),
    "AX02-01x": ("AX02-01", "域变体：官印相生挂刑灾官非（原挂功名）"),
    "AX02-03x": ("AX02-03", "域变体：伤官见官挂刑灾官非"),
    "AX02-03m": ("AX02-03", "性别变体：坤命专用"),
    "AX02-05x": ("AX02-05", "域变体：食神制杀挂刑灾官非"),
    "AX03-01x": ("AX03-01", "口径变体：只在七杀>0 的例上取计数"),
    "AX03-03x": ("AX03-03", "域变体：身弱无根挂刑灾官非"),
    "AX04-02x": ("AX04-02", "域变体：七杀在日时挂刑灾官非"),
    "AX04-04x": ("AX04-04", "性别变体：坤命专用"),
    "AX04-04y": ("AX04-04", "对照变体：不限性别"),
    "AX06-02x": ("AX06-02", "域变体：五行偏枯挂刑灾官非"),
}


# ── 非机器判定条目（闸三「未蒸清单：不偷丢」）─────────────────────────────
# kind="declared"：已声明、**判定函数未建**（库缺字段／算法／结局域）→ 一律不进统计层
# kind="method"  ：口径效应（尺子），不是理论条目
EXTRA = [
    ("AX03-05", "method", "（口径效应）", "致效强度递增",
     "同一十神换三种口径（天干／本气／8字）",
     "这是「尺子」不是「理论」，是所有条目的前置"),
    ("AX05-04", "declared", "婚姻", "婚姻等级↓", "〔未蒸〕日支落空亡",
     "⚠ 库无空亡字段 ⇒ 先造字段（见未蒸清单）"),
    ("AX06-03", "declared", "寿元健康", "健康（上热下寒）", "〔未蒸〕水≥3 ∧ 火≤1",
     "⚠ 库无健康结局域 ⇒ 实盘专用（见未蒸清单）"),
    ("AX07-02", "declared", "刑灾官非", "刑灾官非等级↑", "〔未蒸〕日主五行≥2 ∧ 四柱有该五行之墓",
     "⚠ 库无「墓」算法与字段（辰=水墓 等）"),
    ("AX08-03", "declared", "功名事业", "功名事业等级↑", "〔未蒸〕月令=寅 ∧ 日柱=甲子 ∧ 天干透丙",
     "巾箱单格诀，域锁死（日柱×月令）n≈3 ⇒ 只当 C 档参照"),
    ("AX10-01", "declared", "（应期）", "事件应期（凶）", "〔未蒸〕大运含「原局无而忌」之字",
     "依赖 AX-02/03 先定「忌字」可算判据"),
    ("AX10-02", "declared", "（应期）", "事件应期", "〔未蒸〕大运冲原局 ／ 流年冲大运",
     "灰犀牛（大运冲原局）／ 黑天鹅（流年冲大运）"),
    ("AX10-03", "declared", "（应期）", "事件应期", "〔未蒸〕岁运填实（原局有字再现）",
     "⚠ case_events 仅 47 条／25 例，成表前无解"),
]


def registry():
    """→ {id: (域, 方向符号, 判定函数)}；与老打分器逐字等价（有回归测试）。"""
    out = {}
    for eid, dom, sign, gate, spec in SPEC:
        fn = build(spec)
        if gate == "fem":
            fn = (lambda fn: (lambda f: fn(f) if fem(f) else None))(fn)
        elif gate == "yl":
            fn = (lambda fn: (lambda f: fn(f) if f["yl"] else None))(fn)
        out[eid] = (dom, sign, fn)
    return out


def meta():
    """→ {id: 机器渲染的元数据}（条件/方向/口径/变体）——条目册只准读这里，禁手写。"""
    m = {}
    for eid, dom, sign, gate, spec in SPEC:
        gap = "坤命" if gate == "fem" else ("需有月令" if gate == "yl" else "")
        m[eid] = dict(
            id=eid, domain=dom, sign=sign, gate=gate, kind="cond",
            cond=(f"{gap}：{render(spec)}" if gap else render(spec)),
            cal=render_cal(spec),
            dir=f"{dom}等级{'↑' if sign > 0 else '↓'}",
            variant_of=VARIANT.get(eid, (None, ""))[0],
            variant_note=VARIANT.get(eid, (None, ""))[1],
            spec=spec,
        )
        # 本体编号：只以变体形式入册的（AX01-07 等），补一条本体记录指向该变体，
        # 免得条目册里「本体凭空消失」或被误判成「没测」
        base = VARIANT.get(eid, (None, ""))[0]
        if base and base not in m:
            m[base] = dict(m[eid], id=base, kind="base", alias_of=eid,
                           domain="（本体·见变体）", dir="多域",
                           variant_of=None, variant_note=f"本体编号；实测按变体 {eid} 计")
    for eid, kind, dom, dr, cond, note in EXTRA:
        m[eid] = dict(id=eid, domain=dom, sign=None, gate=None, kind=kind,
                      cond=cond,
                      cal=("（口径效应·非统计条目）" if kind == "method" else "（非机器判定：声明未建）"),
                      dir=dr, variant_of=None, variant_note=note, spec=None)
    return m


if __name__ == "__main__":
    M = meta()
    print(f"登记条目 {len(M)} 条")
    for eid in M:
        m = M[eid]
        print(f"{eid}\t{m['domain']}\t{m['dir']}\t{m['cond']}\t｜{m['cal']}")
