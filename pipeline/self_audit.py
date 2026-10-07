#!/usr/bin/env python3
"""命理自审闭环工具 —— 四层独立度阶梯的可执行部分。

  L3a --pillars "丁卯 辛亥 戊子 癸丑"      纯干支律代数自洽（五虎遁/五鼠遁/阴阳）
  L3  --recompute male 1987-12-05 1       三腿互校：代数 + sxtwl + mingyu
  L2  --l2 --file X.md | --text "…"       文本角色分层 → 只把断语行送 Jev
  L4  --ledger add|list|reconcile         前瞻账本（预测当场落盘，到期对账）

铁律：本工具只出"体检报告/自校日志"，不出"结论"。终审权归现实回报 + 本人。
用法详见同目录 ../SKILL.md。终端需清代理。
"""
import argparse, json, os, re, subprocess, sys, datetime

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
MONTH_BR = "寅卯辰巳午未申酉戌亥子丑"      # 正月=寅
HOUR_BR = "子丑寅卯辰巳午未申酉戌亥"
HOURS = [0, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23]   # timeIndex 0=早子 … 12=晚子

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLDIR = os.path.dirname(HERE)
# 账本路径：默认同目录；可用环境变量指向副本，供**演练**用（真账本不许拿来做实验）
LEDGER = os.environ.get("SELF_AUDIT_LEDGER") or os.path.join(HERE, "ledger.jsonl")
MINGYU_CALL = os.path.expanduser("~/projects/bazi-verify/mingyu_call.py")
SXTWL_PY = os.path.expanduser("~/.venvs/sxtwl-env/bin/python")
JEV = os.path.expanduser("~/.hermes/profiles/see/skills/mingli/jev-discipline-check/scripts/jev_check.py")


# ─────────────────────────── L3a 代数自洽 ───────────────────────────
def _five_tiger(yg, mz):
    start = {"甲": "丙", "己": "丙", "乙": "戊", "庚": "戊", "丙": "庚",
             "辛": "庚", "丁": "壬", "壬": "壬", "戊": "甲", "癸": "甲"}[yg]
    return GAN[(GAN.index(start) + MONTH_BR.index(mz)) % 10]


def _five_rat(dg, hz):
    start = {"甲": "甲", "己": "甲", "乙": "丙", "庚": "丙", "丙": "戊",
             "辛": "戊", "丁": "庚", "壬": "庚", "戊": "壬", "癸": "壬"}[dg]
    return GAN[(GAN.index(start) + HOUR_BR.index(hz)) % 10]


def split_pillars(text):
    ps = re.findall(r"([甲乙丙丁戊己庚辛壬癸])([子丑寅卯辰巳午未申酉戌亥])",
                    text.replace("醜", "丑").replace("幹", "干").replace(" ", ""))
    return [a + b for a, b in ps][:4]


def l3_algebra(pillars_text):
    ps = split_pillars(pillars_text)
    out = {"leg": "L3a 代数自洽", "impl": "五虎遁/五鼠遁干支律（无日期）", "ok": None, "detail": []}
    if len(ps) < 4:
        out["ok"] = False
        out["detail"].append(f"解析出 {len(ps)} 柱，不足 4 柱")
        return out, None
    y, m, d, h = ps
    errs = []
    for nm, p in (("年", y), ("月", m), ("日", d), ("时", h)):
        if GAN.index(p[0]) % 2 != ZHI.index(p[1]) % 2:
            errs.append(f"{nm}柱 {p} 阴阳不配（不存在的干支组合）")
    if m[1] not in MONTH_BR:
        errs.append(f"月支 {m[1]} 非法")
    else:
        e = _five_tiger(y[0], m[1])
        if e != m[0]:
            errs.append(f"月干不符五虎遁：{y[0]}年{m[1]}月应为 {e}{m[1]}，实际 {m}")
    e = _five_rat(d[0], h[1])
    if e != h[0]:
        errs.append(f"时干不符五鼠遁：{d[0]}日{h[1]}时应为 {e}{h[1]}，实际 {h}")
    out["ok"] = not errs
    out["detail"] = errs or ["四柱代数自洽"]
    return out, " ".join(ps)


# ─────────────────────────── L3b sxtwl ───────────────────────────
SXTWL_SNIPPET = r'''
import sys, sxtwl, json
y, m, d, hour = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
G = "甲乙丙丁戊己庚辛壬癸"; Z = "子丑寅卯辰巳午未申酉戌亥"
day = sxtwl.fromSolar(y, m, d)
ygz, mgz, dgz = day.getYearGZ(), day.getMonthGZ(), day.getDayGZ()
hgz = day.getHourGZ(hour)
print(json.dumps({"year": G[ygz.tg]+Z[ygz.dz], "month": G[mgz.tg]+Z[mgz.dz],
                  "day": G[dgz.tg]+Z[dgz.dz], "hour": G[hgz.tg]+Z[hgz.dz]}, ensure_ascii=False))
'''


def l3_sxtwl(y, m, d, time_index):
    out = {"leg": "L3b sxtwl 历法", "impl": "sxtwl.getYear/Month/Day/HourGZ", "ok": None, "detail": []}
    tmp = "/tmp/_selfaudit_sxtwl.py"
    try:
        with open(tmp, "w") as f:
            f.write(SXTWL_SNIPPET)
        r = subprocess.run([SXTWL_PY, tmp, str(y), str(m), str(d), str(HOURS[time_index])],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            out["ok"] = False
            out["detail"].append("sxtwl 腿不可用: " + (r.stderr.strip().splitlines() or [""])[-1][:160])
            return out, None
        gz = json.loads(r.stdout.strip().splitlines()[-1])
        pillars = f"{gz['year']} {gz['month']} {gz['day']} {gz['hour']}"
        out["ok"] = True
        out["detail"].append(pillars)
        return out, pillars
    except Exception as e:
        out["ok"] = False
        out["detail"].append(f"sxtwl 腿异常: {type(e).__name__}: {e}"[:160])
        return out, None


# ─────────────────────────── L3c mingyu ───────────────────────────
def l3_mingyu(gender, y, m, d, time_index):
    out = {"leg": "L3c mingyu MCP", "impl": "bazi_calculate", "ok": None, "detail": []}
    if not os.path.exists(MINGYU_CALL):
        out["ok"] = False
        out["detail"].append(f"未找到 {MINGYU_CALL}")
        return out, None
    args = {"kwargs": json.dumps({"gender": gender, "dateType": "solar",
                                  "year": y, "month": m, "day": d, "timeIndex": time_index},
                                 ensure_ascii=False)}
    env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    try:
        r = subprocess.run([sys.executable, MINGYU_CALL, "bazi_calculate", json.dumps(args, ensure_ascii=False)],
                           capture_output=True, text=True, timeout=120, env=env)
        txt = (r.stdout or "") + (r.stderr or "")
        gz = re.findall(r"([甲乙丙丁戊己庚辛壬癸])([子丑寅卯辰巳午未申酉戌亥])", txt)
        if len(gz) < 4:
            out["ok"] = False
            out["detail"].append("mingyu 返回未解析出四柱: " + txt.strip()[:200])
            return out, None
        ps = [a + b for a, b in gz[:4]]
        out["ok"] = True
        out["detail"].append(" ".join(ps))
        return out, " ".join(ps)
    except Exception as e:
        out["ok"] = False
        out["detail"].append(f"mingyu 腿异常: {type(e).__name__}: {e}"[:160])
        return out, None


# ─────────────────────────── L2 分层 + Jev ───────────────────────────
DEF_PAT = re.compile(r"五虎遁|五鼠遁|阳男阴女|阴男阳女|顺排|逆排|定义|规则|约定|三合局|三会局"
                     r"|藏干|长生|帝旺|墓库|= *[子丑寅卯辰巳午未申酉戌亥]|十二宫|节气|交节(?!日)"
                     r"|断法|口诀|神煞|十神|宫位|总论|凡例")
EV_PAT = re.compile(r"台词|原文|原句|引用|据.{0,6}(称|说|述)|引号|『|』|「|」|“[^”]{4,}”|\"[^\"]{4,}\"")
FLOW_PAT = re.compile(r"待.{0,4}(确认|核|定|办)|TODO|待办|⚠️|下一步|见上|见下|同上|^\s*$")
VERDICT_PAT = re.compile(r"顺利|不顺|破财|升迁|落马|得财|发财|生病|病|灾|变动|启动|应期|成事|"
                         r"受阻|停滞|转好|变差|离开|入职|结婚|离婚|怀孕|生育|凶|吉|"
                         r"会有|将会|恐|妨|利|宜|忌|可能|倾向|概率|"
                         r"主因|身强|身弱|身不弱|偏旺|偏弱|从格|病灶|病机|推演|人格|性格|为人|"
                         r"不破|作废|重估|内敛|外显|落实|应期|窗口")


def classify_line(ln):
    s = ln.strip()
    if len(s) < 8:
        return "skip", "过短"
    if s.startswith(("#", "|", ">", "- [", "```", "---")) or s.startswith("MEDIA:"):
        return "流程行", "结构行"
    if FLOW_PAT.search(s):
        return "流程行", "含待办/标记"
    if DEF_PAT.search(s):
        return "定义行", "含排盘规则/术语定义"
    if EV_PAT.search(s):
        return "证据行", "含引用/他源"
    if VERDICT_PAT.search(s):
        return "断语行", "含判断词"
    return "skip", "无判断词"


def run_jev(text, facts=""):
    env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    cmd = [sys.executable, JEV, "--text", text, "--json"]
    if facts:
        cmd += ["--facts", facts]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
        raw = (r.stdout or "").strip()
        d = None
        if raw:
            try:
                d = json.loads(raw)          # jev --json 是多行 pretty-print
            except Exception:
                m = re.findall(r"[\[{].*[\]}]", raw, re.S)   # 退路：抓最后一个 JSON 块
                if m:
                    try:
                        d = json.loads(m[-1])
                    except Exception:
                        d = None
        if d is None:
            return None
        if isinstance(d, list):
            d = d[0] if d else {}
        sc = d.get("score", d) or {}
        lay = sc.get("layer")
        return {"checkable": sc.get("checkable"),
                "evidence_leap": sc.get("evidence_leap"),
                "absolute_verdict": sc.get("absolute_verdict"),
                "layer": lay.get("choice") if isinstance(lay, dict) else lay,
                "verdict": d.get("verdict", "")}
    except Exception:
        return None


def l2_audit(text, facts="", limit=200):
    lines, buckets = text.splitlines(), {"断语行": [], "定义行": [], "证据行": [], "流程行": [], "skip": []}
    for i, ln in enumerate(lines, 1):
        role, why = classify_line(ln)
        buckets[role].append((i, ln.strip(), why))
    print(f"\n【L2 分层】共 {len(lines)} 行 → 断语行 {len(buckets['断语行'])}"
          f" / 定义行 {len(buckets['定义行'])} / 证据行 {len(buckets['证据行'])}"
          f" / 流程行 {len(buckets['流程行'])} / 跳过 {len(buckets['skip'])}")
    print("  （定义行/证据行/流程行 **不进 Jev** —— 否则必然误伤，见 SKILL.md 分层表）\n")
    rows, hard = [], 0
    for n, (i, s, _) in enumerate(buckets["断语行"][:limit], 1):
        d = run_jev(s, facts)
        if not d:
            print(f"  {n:>2}. [Jev 无响应] {s[:60]}")
            continue
        leap = float(d.get("evidence_leap", 0) or 0)
        abso = float(d.get("absolute_verdict", 0) or 0)
        chk = float(d.get("checkable", 1) or 0)
        lay = d.get("layer", "?")
        flag = []
        if leap >= 0.85:
            flag.append("硬伤·证据跳跃")
        if abso >= 0.85:
            flag.append("硬伤·绝对化")
        if chk < 0.40:
            flag.append("不可证伪")
        if lay == "verdict":
            flag.append("判决式")
        if flag:
            hard += 1
        print(f"  {n:>2}. chk={chk:.2f} leap={leap:.2f} abs={abso:.2f} layer={lay}"
              f"  {' / '.join(flag) if flag else 'OK'}")
        print(f"      {s[:88]}")
        rows.append({"n": n, "line_no": i, "text": s, "checkable": chk, "leap": leap,
                     "absolute": abso, "layer": lay, "flags": flag})
    print(f"\n===== L2 体检：断语行 {len(rows)} 条，待改 {hard} 条 =====")
    print("※ 分数只查纪律，不是准确性认证；终审权归 L4 现实回报 + 本人。")
    return rows


# ─────────────────────────── L4 前瞻账本 ───────────────────────────
def ledger_load():
    if not os.path.exists(LEDGER):
        return []
    with open(LEDGER) as f:
        return [json.loads(l) for l in f if l.strip()]


def ledger_save(items):
    with open(LEDGER, "w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def ledger_add(a):
    items = ledger_load()
    kind = a.kind or "prospective"
    if kind == "prospective" and not (a.due or a.due_cond):
        print("⛔ 前瞻条目必须给 --due（ISO 日期）或 --due-cond（到期条件），否则永远对不了账。")
        return
    if kind == "prospective" and not (a.hit_rule or "").strip():
        print("⛔ 前瞻条目必须给 --hit-rule（什么现象算 hit / 什么算 miss / 什么算 partial）。")
        print("   没有判据＝事后可以随便改口，这条就不算前瞻盲测。")
        return
    if a.due:
        try:
            datetime.date.fromisoformat(a.due)
        except ValueError:
            print(f"⛔ --due 需 ISO 日期（YYYY-MM-DD），收到 {a.due!r}。")
            return
    it = {"id": (max([x["id"] for x in items]) + 1) if items else 1,
          "logged_at": datetime.datetime.now().isoformat(timespec="seconds"),
          "kind": kind, "metric": a.metric or "rate",
          "subject": a.subject, "claim": a.claim, "window": a.window,
          "due": a.due or None, "due_cond": a.due_cond or None,
          "hit_rule": a.hit_rule or None,
          "confidence": a.confidence, "baseline": a.baseline, "basis": a.basis,
          "result": None, "note": ""}
    items.append(it)
    ledger_save(items)
    print(f"已落盘 #{it['id']} @ {it['logged_at']}  （先断后验，事后不许改）")
    print(f"  类别：{kind}（{'计入 A 档' if kind == 'prospective' else '⛔ 回看类，只算「解释得住」，永不计入 A 档'}）"
          f" ｜ 量纲：{it['metric']} ｜ 基线 {a.baseline}（{it['metric']}）")
    print(json.dumps(it, ensure_ascii=False, indent=1))


def ledger_list():
    items = ledger_load()
    if not items:
        print("账本为空。")
        return
    print(f"{'id':>3} {'记录':<11} {'类别':<11} {'到期':<24} {'自':>4} {'基':>4} {'结果':<6} 预测")
    for it in items:
        kind = it.get("kind", "prospective")
        due = it.get("due") or it.get("due_cond") or it.get("window")
        print(f"{it['id']:>3} {it['logged_at'][:10]:<11} {kind[:10]:<11} {str(due)[:23]:<24} "
              f"{it.get('confidence', 0):>4} {it.get('baseline', 0):>4} "
              f"{str(it.get('result') or '待回报'):<6} {it['claim'][:30]}")
    p = [x for x in items if x.get("kind", "prospective") == "prospective"]
    ph = [x for x in p if x.get("result") == "hit"]
    r = [x for x in items if x.get("kind", "prospective") == "retrospective"]
    print("\n※ 报超额 = 名义命中 − 基线率；有效 n ≠ 条数（同事件多条高度相关）。")
    print(f"※ 分账：前瞻 {len(p)} 条（hit {len(ph)}）｜ 回看 {len(r)} 条（不计 A 档）。")
    print(f"※ A 档进度 = 前瞻命中 {len(ph)} / 2 ⇒ {'✅ 达标' if len(ph) >= 2 else '未达标（回看类 hit 不算）'}")


def ledger_due():
    items = ledger_load()
    today = datetime.date.today()
    due, over, pend = [], [], []
    for it in items:
        if it.get("result"):
            continue
        if it.get("due"):
            d = datetime.date.fromisoformat(it["due"])
            if d <= today:
                due.append((it, d))
            else:
                over.append((it, d))
        else:
            pend.append(it)
    print(f"今天 {today} ｜ 待对账 {len(due) + len(over) + len(pend)} 条\n")
    if due:
        print("⏰ 已到期（该对账了）：")
        for it, d in due:
            print(f"  #{it['id']} 到期 {d} ｜ {it['subject']}：{it['claim'][:40]}")
    if over:
        print("\n⏳ 未到期：")
        for it, d in sorted(over, key=lambda x: x[1]):
            print(f"  #{it['id']} 到期 {d} ｜ {it['subject']}")
    if pend:
        print("\n⚠ 无日期、只靠条件到期（对不了账，须人工盯）：")
        for it in pend:
            print(f"  #{it['id']} 条件：{it.get('due_cond') or it.get('window')} ｜ {it['subject']}")
    print("\n对账命令： python3 self_audit.py --ledger reconcile --id N --result hit|miss|partial|void --note '…'")


def ledger_reconcile(a):
    items = ledger_load()
    for it in items:
        if it["id"] == a.id:
            it["result"] = a.result
            it["note"] = a.note or ""
            it["reconciled_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            ledger_save(items)
            kind = it.get("kind", "prospective")
            print(f"#{a.id} → {a.result}（{kind}）")
            if kind == "retrospective":
                print("  ⚠ 回看类：同库换层/换口径复现 ⇒ 只能写「解释得住」，**不计入 A 档**。")
            done = [x for x in items if x.get("result")]
            if done:
                hits = sum(1 for x in done if x["result"] == "hit")
                nom = hits / len(done)
                base = sum(float(x.get("baseline", 0) or 0) for x in done) / len(done)
                pp = [x for x in done if x.get("kind", "prospective") == "prospective"
                      and x["result"] in ("hit", "miss")]
                ph = [x for x in pp if x["result"] == "hit"]
                rr = [x for x in done if x.get("kind", "prospective") == "retrospective"]
                print(f"全账 n={len(done)}（有效 n 需再扣相关性；含回看类）  名义命中={nom:.2f}  "
                      f"基线={base:.2f}  超额={nom - base:+.2f}")
                print(f"分账：前瞻 {len(ph)} hit / {len(pp)} 判定 ｜ 回看 {len(rr)} 条（不计 A 档）")
                print(f"A 档进度 = 前瞻命中 {len(ph)} / 2 ⇒ "
                      f"{'✅ 达标，可写「敢说」' if len(ph) >= 2 else '未达标'}")
                print("※ MISS 必须归因：方法错 → mingli-method-evidence-audit；读法错 → 对应断法技能。")
            return
    print(f"未找到 #{a.id}")


# ─────────────────────────── main ───────────────────────────
def main():
    p = argparse.ArgumentParser(description="命理自审闭环工具（只体检，不终审）")
    p.add_argument("--pillars", help="四柱串，做 L3a 代数自洽")
    p.add_argument("--recompute", nargs=3, metavar=("GENDER", "DATE", "TIMEINDEX"),
                   help="L3 三腿互校：性别 公历日期 timeIndex")
    p.add_argument("--l2", action="store_true", help="L2 分层体检")
    p.add_argument("--file"), 
    p.add_argument("--text")
    p.add_argument("--facts", default="", help="盘面事实，帮 Jev 判证据跳跃")
    p.add_argument("--ledger", choices=["add", "list", "reconcile", "due"])
    p.add_argument("--subject"), p.add_argument("--claim"), p.add_argument("--window")
    p.add_argument("--kind", choices=["prospective", "retrospective"], default="prospective",
                   help="prospective=前瞻盲测（计 A 档）｜retrospective=回看复现（只算解释得住）")
    p.add_argument("--metric", choices=["rate", "mean"], default="rate",
                   help="基线量纲：rate=率（事件发生概率）｜mean=均值（等级均值）")
    p.add_argument("--due", help="到期日 ISO（YYYY-MM-DD）；前瞻条目必须给 --due 或 --due-cond")
    p.add_argument("--due-cond", dest="due_cond", help="无固定日期时的到期条件（对不了账，须人工盯）")
    p.add_argument("--hit-rule", dest="hit_rule",
                   help="判命中的规则：什么现象算 hit / 什么算 miss / 什么算 partial（前瞻必需，防事后改口）")
    p.add_argument("--confidence", type=float, default=0.5)
    p.add_argument("--baseline", type=float, default=0.0)
    p.add_argument("--basis", default=""), p.add_argument("--id", type=int)
    p.add_argument("--result", choices=["hit", "miss", "partial", "void"]), p.add_argument("--note", default="")
    a = p.parse_args()

    if a.pillars:
        out, ps = l3_algebra(a.pillars)
        print(f"[L3a] {out['impl']}  →  {'✅ 自洽' if out['ok'] else '❌ 不一致'}")
        for d in out["detail"]:
            print(f"   {d}")
        return

    if a.recompute:
        g, ds, ti = a.recompute
        ti = int(ti)
        y, m, d = [int(x) for x in re.split(r"[-/.]", ds)]
        print(f"[L3 三腿互校] {g} {ds} timeIndex={ti}（{HOURS[ti]}:00 档）\n")
        legs, results = [], {}
        o1, p1 = l3_algebra(a.pillars or ""); 
        o2, p2 = l3_sxtwl(y, m, d, ti)
        o3, p3 = l3_mingyu(g, y, m, d, ti)
        for nm, o, res in (("sxtwl", o2, p2), ("mingyu", o3, p3)):
            results[nm] = res
            print(f"  {o['leg']:<16} {'✅' if o['ok'] else '❌'}  {res or ' / '.join(o['detail'])}")
        vals = [v for v in results.values() if v]
        if len(set(vals)) == 1 and len(vals) == 2:
            print(f"\n  ⇒ 两条独立腿一致：{vals[0]}")
            print("  ⇒ 再用 --pillars 对该串跑 L3a 代数自洽，三腿齐备才算计算层自校通过。")
        elif len(vals) >= 2:
            print(f"\n  ⚠️ 两条腿不一致：{results}")
            print("  ⇒ 交节日边界问题优先用 calendar_solar_term 核验；不一致时不得带着往下走。")
        else:
            print("\n  ⚠️ 可用腿不足两条，无法互校 —— 计算层未获独立验证。")
        return

    if a.l2:
        txt = a.text or (open(os.path.expanduser(a.file), encoding="utf-8").read() if a.file else "")
        if not txt:
            print("需要 --text 或 --file")
            return
        l2_audit(txt, a.facts)
        return

    if a.ledger == "add":
        ledger_add(a)
    elif a.ledger == "list":
        ledger_list()
    elif a.ledger == "due":
        ledger_due()
    elif a.ledger == "reconcile":
        ledger_reconcile(a)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
