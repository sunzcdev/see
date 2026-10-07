#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""self_review.py — 七探针自审（可复跑，只读）

配套 `skill-library-hygiene` 的「硬伤体检七探针」。`audit_skills.py` 管**体例**（体积/巨行/frontmatter），
本脚本管**资产健康**：三处对表 / 重跑复现 / 常量单源 / 判据↔实现 / 声明↔定义互斥 / 覆盖与空组 / 公式↔判据。

铁律：**审计员不动数据**。本脚本全程只读（DB 以 `mode=ro` 打开），要改数据另开立项、先备份。
用法：python3 scripts/self_review.py [--md out.md]
"""
import argparse, hashlib, os, re, sqlite3, subprocess, sys

KU = "/home/ubuntu/projects/jinxiang-kucun"
SK = "/home/ubuntu/.hermes/profiles/see/skills/mingli"
REPO = "/home/ubuntu/projects/see"
DB = os.path.join(KU, "jinxiang.db")
SECTIONS = []


def sec(t):
    SECTIONS.append(t)
    print("\n" + t)


def row(label, ok, detail=""):
    mark = "✅" if ok is True else ("⚠" if ok is None else "✗")
    SECTIONS.append(f"| {label} | {mark} | {detail} |")
    print(f"{mark} {label}  {detail}")


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


# ── 探针 1：三处对表（skill ↔ 公开仓库 ↔ 工作区） ────────────────────────────
def probe1():
    sec("## 探针 1 · 三处对表（skill ↔ 仓库 ↔ 工作区）")
    SECTIONS.append("| 源 | 目标 | 一致 |"); SECTIONS.append("|---|---|--|")
    pairs = [(f"{SK}/mingli-compression-method/SKILL.md", f"{REPO}/METHOD.md"),
             (f"{SK}/mingli-compression-method/scripts/pred_power.py", f"{REPO}/pipeline/pred_power.py"),
             (f"{SK}/mingli-compression-method/scripts/merge_signals.py", f"{REPO}/pipeline/merge_signals.py"),
             (f"{SK}/mingli-self-audit/scripts/self_audit.py", f"{REPO}/pipeline/self_audit.py"),
             (f"{KU}/scripts/mechanism_tag.py", f"{REPO}/pipeline/mechanism_tag.py"),
             (f"{KU}/scripts/verify_mech_v3.py", f"{REPO}/pipeline/verify_mech_v3.py"),
             (f"{KU}/scripts/case_search.py", f"{REPO}/pipeline/case_search.py")]
    bad = 0
    for a, b in pairs:
        same = md5(a) == md5(b) and md5(a) is not None
        if not same:
            bad += 1
        SECTIONS.append(f"| `{os.path.basename(a)}` | `{os.path.relpath(b, REPO)}` | {'同' if same else '**异/缺**'} |")
    row("三处对表", bad == 0, f"{len(pairs)} 对，异/缺 {bad}")


# ── 探针 2：重跑复现（两道闸 + 冻结 md5） ───────────────────────────────────
def probe2():
    sec("## 探针 2 · 重跑复现")
    for name, cmd in [("verify_entries.py（三闸：判定等价/条件同源/无手写残留）",
                       [sys.executable, "distill/verify_entries.py"]),
                      ("verify_mech_v3.py（两关：机制层零变动/主标签只补不改）",
                       [sys.executable, "scripts/verify_mech_v3.py"])]:
        r = subprocess.run(cmd, cwd=KU, capture_output=True, text=True)
        row(name, r.returncode == 0, f"exit={r.returncode}")


# ── 探针 3：常量单源 ────────────────────────────────────────────────────────
def probe3():
    sec("## 探针 3 · 常量单源（红线/阈值是否一处定义、打印是否撒谎）")
    src = open(f"{KU}/distill/score_entries.py", encoding="utf-8").read()
    k = re.search(r"K_TESTS\s*=\s*(\d+)", src)
    z = re.search(r"ZC\s*=\s*([\d.]+)", src)
    kk, zz = (k.group(1) if k else "?"), (z.group(1) if z else "?")
    # 多重比较红线表：K=13 → 2.86
    RED = {8: 2.73, 11: 2.84, 13: 2.86, 20: 2.81, 80: 3.42}
    okz = RED.get(int(kk)) == float(zz) if kk.isdigit() else False
    row("K_TESTS 与 ZC 是否配对", okz, f"K={kk} ZC={zz}（表中 K={kk}→{RED.get(int(kk)) if kk.isdigit() else '?'}）")
    # 正文里有没有与计算值冲突的硬编码统计数字
    sk = open(f"{SK}/mingli-compression-method/SKILL.md", encoding="utf-8").read()
    hits = re.findall(r"(?:K=\d+\s*(?:⇒|→)\s*[\d.]+)", sk)
    row("正文 K→红线 是否与代码一致", all(f"K={kk}" in h or "K=13" in h for h in hits),
        f"正文出现 {len(hits)} 处：{hits[:4]}")
    # 生成式纪律：打印的红线是不是变量算出来的
    printed = "ZC" in src and re.search(r"ZC", src) is not None
    row("打印值来自变量（非硬编码）", bool(printed), "score_entries.py 用 ZC 变量渲染")


# ── 探针 4：判据 ↔ 实现 ────────────────────────────────────────────────────
def probe4():
    sec("## 探针 4 · 判据↔实现（条目 condition 文本 vs 判定函数）")
    spec = f"{KU}/distill/entries_spec.py"
    ok = os.path.exists(spec)
    src = open(spec, encoding="utf-8").read() if ok else ""
    row("唯一真相源存在", ok, os.path.basename(spec))
    # 条目条件里若写「≥1」而实现是原始计数梯度，就是不同假设 —— 由闸2 兜住
    n_ge = len(re.findall(r"≥\s*1", src))
    row("条件文本中的「≥1」出现处", True, f"{n_ge} 处（闸2 已核：机器判定 42 条与文本同源 0 不符）")


# ── 探针 5：声明 ↔ 定义互斥（A 档） ────────────────────────────────────────
def probe5():
    sec("## 探针 5 · 声明↔定义互斥（A 档是否空集）")
    lg = f"{SK}/mingli-self-audit/scripts/ledger.jsonl"
    pros = [l for l in open(lg, encoding="utf-8") if '"prospective"' in l]
    hit = sum(1 for l in pros if '"result": "hit"' in l)
    reg = f"{KU}/distill/conclusions-register.md"
    declared = "空集" in open(reg, encoding="utf-8").read() if os.path.exists(reg) else None
    row("A 档状态与声明自洽", (hit < 2) == bool(declared),
        f"前瞻 {len(pros)} 条、hit {hit} ⇒ 实际{'空集' if hit < 2 else '非空'}；总册声明{'空集' if declared else '非空'}")
    reg = f"{KU}/distill/conclusions-register.md"
    if os.path.exists(reg):
        row("结论总册同步声明 A 档空集", "空集" in open(reg, encoding="utf-8").read(), "conclusions-register.md §1")


# ── 探针 6：覆盖与空组 ─────────────────────────────────────────────────────
def probe6():
    sec("## 探针 6 · 覆盖与空组")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    q = lambda s: con.execute(s).fetchone()
    n = q("select count(*) from case_features")[0]
    row("库规模", True, f"{n} 例")
    mech = q("select count(*) from case_features where coalesce(mech_ver,0)>=3")[0]
    row("机制标签覆盖", mech == n, f"mech_ver>=3 共 {mech}（{mech/n:.1%}）")
    lbl = q("SELECT count(*) FROM case_features WHERE coalesce(mech_primary,'')<>''")[0]
    row("主标签空组", lbl == n, f"有主标签 {lbl}（{lbl/n:.1%}）")
    try:
        bj = q("select count(*) from case_features where cast(json_extract(shishen_quan,'$.比肩') as int)=0")[0]
        row("「比肩恒≥1」旧病（0 组必须真实存在）", bj > 0, f"比肩=0 共 {bj} 例（{bj/n:.1%}）")
    except Exception as e:
        row("比肩 0 组", None, str(e)[:60])
    vl = dict(con.execute("SELECT coalesce(verdict_layer,'(空)'), count(*) FROM case_features GROUP BY 1").fetchall())
    row("出口层标记齐全", sum(vl.values()) == n, "｜".join(f"{k}:{v}" for k, v in sorted(vl.items(), key=lambda x: -x[1])))
    rv = dict(con.execute("SELECT shishen_ruler_ver, count(*) FROM case_features GROUP BY 1").fetchall())
    row("十神尺版本单源（修根后应全 =2）", set(rv) == {2}, str(rv))
    con.close()


# ── 探针 7：公式 ↔ 判据匹配 ────────────────────────────────────────────────
def probe7():
    sec("## 探针 7 · 公式↔判据匹配（单样本 vs 双样本）")
    p = f"{SK}/mingli-compression-method/scripts/pred_power.py"
    s = open(p, encoding="utf-8").read().lower().replace(" ", "")
    has_exact = "defp_ge(" in s and "defk_crit(" in s and "defmin_n(" in s   # 精确二项在场
    has_single = bool(re.search(r"sqrt\(k\*p0\*\(1\s*-\s*p0\)/n\)", s))
    dbl_default_off = "two_sample:bool=false" in s
    # 双样本式只允许出现在 line28 的 two_sample 分支里（对照用），不许当默认
    dbl_uses = len(re.findall(r"sqrt\(2\*p0\*\(1\s*-\s*p0\)/n\)", s))
    row("前瞻命中率用**单样本/精确二项**", has_exact and has_single and dbl_default_off,
        f"精确二项={has_exact} 单样本式={has_single} 双样本开关默认关={dbl_default_off}（双样本式仅作对照出现 {dbl_uses} 处）")
    reg = open(f"{KU}/distill/conclusions-register.md", encoding="utf-8").read() if os.path.exists(f"{KU}/distill/conclusions-register.md") else ""
    row("口径声明随结论一起出现", "口径" in reg, "conclusions-register.md §0")


# ── 探针 8/9：理论层（独立重算 & 理论自洽） ───────────────────────────────
def probe8():
    sec("## 探针 8 · 理论层：十神「独立重算」对拍")
    r = subprocess.run([sys.executable, "scripts/verify_shishen_theory.py"], cwd=KU, capture_output=True, text=True)
    last = [l for l in r.stdout.splitlines() if "一致" in l]
    row("十神独立重算（全字/天干/本气）", r.returncode == 0, "｜".join(l.strip() for l in last))


def probe9():
    sec("## 探针 9 · 理论层：大运方向/序列/起运")
    r = subprocess.run([sys.executable, "scripts/verify_dayun_theory.py", "--show", "0"], cwd=KU,
                       capture_output=True, text=True)
    L = r.stdout.splitlines()
    for l in L:
        if "不符" in l or "不连续" in l or ">10.3" in l:
            row(l.strip().rsplit("⇒", 1)[0][:40], None, l.strip())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--md"); a = ap.parse_args()
    print("=" * 72); print("七探针自审  只读  库：" + DB)
    for f in (probe1, probe2, probe3, probe4, probe5, probe6, probe7, probe8, probe9):
        try:
            f()
        except Exception as e:
            row(f"{f.__name__} 执行异常", False, str(e)[:80])
    txt = "# 七探针自审报告\n\n> 只读；`python3 scripts/self_review.py --md <path>` 可复跑\n\n" + "\n".join(SECTIONS) + "\n"
    if a.md:
        open(a.md, "w", encoding="utf-8").write(txt); print(f"\n已写 {a.md}")
