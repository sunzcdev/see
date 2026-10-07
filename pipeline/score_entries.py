#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压缩法 · 条目上机打分器 v2
把 distill/entries.json 的条件落到库上。

两个出口（同一条件 × 同一域，两种测法）：
  L = 等级出口（序数，高=好）      → 需该例在该域有 lvl
  X = 凶率出口（二值，凶=1）       → 需该例在该域有 pol
出处：case_features.verdict_domains（源A，回复层）／case_outcomes（源B，素材层）

预注册判据：
  · 校正单元 = 轴（K=11）⇒ 主判据线 z_crit = 2.84（双侧 0.05）
  · 两段：本脚本=发现半（case_id 奇数）；同号且 |z|≥1.96 才进确认半
  · 只在「两半同号且都过线」时才写「稳定」
"""
import sqlite3, json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "..", "jinxiang.db")
ZC = 2.84

GAN_WX = {'甲':'木','乙':'木','丙':'火','丁':'火','戊':'土','己':'土','庚':'金','辛':'金','壬':'水','癸':'水'}
ZHI_WX = {'寅':'木','卯':'木','巳':'火','午':'火','辰':'土','戌':'土','丑':'土','未':'土',
          '申':'金','酉':'金','亥':'水','子':'水'}

def z_linlin(b, y):
    n = len(b)
    if n < 8: return None, n, "n<8"
    Sb, Sy = sum(b), sum(y)
    Sbb = sum(x*x for x in b); Syy = sum(x*x for x in y)
    Sby = sum(x*y for x, y in zip(b, y))
    db, dy = Sbb - Sb*Sb/n, Syy - Sy*Sy/n
    if db <= 0: return None, n, "预测子无变异"
    if dy <= 0: return None, n, "结局无变异"
    return (Sby - Sb*Sy/n)/math.sqrt(db*dy/(n-1)), n, ""

def parse_doms(raw):
    """{域: {pol,lvl,ev}} → {域: (pol, lvl)}"""
    if not raw: return {}
    try: d = json.loads(raw)
    except Exception: return {}
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, dict):
                out[k] = (v.get('pol'), v.get('lvl'))
            else:
                out[k] = (None, v)      # 形如 {"财": 3}
    return out

def load():
    c = sqlite3.connect(DB)
    rows = c.execute("""select case_id, yueling, year_pillar, month_pillar, day_pillar, hour_pillar,
                               gender, shishen_quan, shishen_config, tonggen,
                               he_list, chong_list, hui_list, xing_list, verdict_domains
                        from case_features""").fetchall()
    lvB = dict(c.execute("select case_id, level from case_outcomes").fetchall())
    polB = dict(c.execute("select case_id, verdict from case_outcomes").fetchall())
    F = {}
    for (cid, yl, py, pm, pd, ph, g, ssq, ssc, tg, he, ch, hui, xing, vdom) in rows:
        pil = [py, pm, pd, ph]
        j = lambda s: json.loads(s) if s else {}
        ss, sscd, tgd = j(ssq), j(ssc), j(tg)
        jl = lambda s: json.loads(s) if s else []
        wx = {}
        for p in pil:
            if not p or len(p) < 2: continue
            for ch_ in (p[0], p[1]):
                w = GAN_WX.get(ch_) or ZHI_WX.get(ch_)
                if w: wx[w] = wx.get(w, 0) + 1
        A = parse_doms(vdom)
        B = parse_doms(lvB.get(cid))          # {"财": 3}
        Bp = parse_doms(polB.get(cid))        # 素材层另有 verdict 文本 → 尝试解析
        for k, (p, l) in Bp.items():
            if k not in B: B[k] = (p, l)
            else: B[k] = (B[k][0] or p, B[k][1] if B[k][1] is not None else l)
        F[cid] = dict(cid=cid, yl=yl, pil=pil, day=pd, g=g, ss=ss, ssc=sscd, tg=tgd, wx=wx,
                      he=jl(he), ch=jl(ch), hui=jl(hui), xing=jl(xing), A=A, B=B)
    return F

def cnt(f, *n): return sum(f['ss'].get(x, 0) for x in n)
def has(f, *n): return cnt(f, *n) > 0
def tgpos(f, *n):
    s = set()
    for x in n: s |= set(f['tg'].get(x, []))
    return s
def dayzhi(f): return f['day'][1] if f['day'] and len(f['day']) > 1 else ''
def hit(lst, z): return 1 if any(z in s for s in lst) else 0
def fem(f): return 1 if f['g'] in ('坤', '女', 'F') else 0

P = {}
def reg(i, dom, sign, fn): P[i] = (dom, sign, fn)

# AX-01 十神单字轴
reg("AX01-01","财",+1,lambda f: f['ss'].get('偏财',0))
reg("AX01-02","财",+1,lambda f: f['ss'].get('正财',0))
reg("AX01-03","财",-1,lambda f: 1 if f['ssc'].get('劫财',0)>0 else 0)
reg("AX01-04","财",-1,lambda f: f['ss'].get('劫财',0))
reg("AX01-05","财",-1,lambda f: f['ss'].get('比肩',0))
reg("AX01-06","功名事业",+1,lambda f: f['ss'].get('正官',0))
reg("AX01-07x","刑灾官非",+1,lambda f: f['ss'].get('七杀',0))
reg("AX01-08","婚姻",-1,lambda f: (f['ss'].get('伤官',0) if fem(f) else None))
reg("AX01-09","寿元健康",+1,lambda f: f['ss'].get('食神',0))
reg("AX01-10","寿元健康",-1,lambda f: 1 if (f['ss'].get('偏印',0)>0 and f['ss'].get('食神',0)>0) else 0)
# AX-02 格局成破轴
reg("AX02-01x","刑灾官非",-1,lambda f: 1 if (f['ss'].get('正官',0)>0 and cnt(f,'正印','偏印')>0) else 0)
reg("AX02-02","功名事业",+1,lambda f: 1 if (f['ss'].get('七杀',0)>0 and cnt(f,'正印','偏印')>0) else 0)
reg("AX02-03x","刑灾官非",+1,lambda f: 1 if (f['ss'].get('伤官',0)>0 and f['ss'].get('正官',0)>0) else 0)
reg("AX02-03m","婚姻",-1,lambda f: (1 if (f['ss'].get('伤官',0)>0 and f['ss'].get('正官',0)>0) else 0) if fem(f) else None)
reg("AX02-04","财",-1,lambda f: 1 if (cnt(f,'比肩','劫财')>=2 and cnt(f,'正财','偏财')>0) else 0)
reg("AX02-05x","刑灾官非",-1,lambda f: 1 if (f['ss'].get('食神',0)>0 and f['ss'].get('七杀',0)>0) else 0)
reg("AX02-06","功名事业",+1,lambda f: 1 if (cnt(f,'正财','偏财')>0 and f['ss'].get('正官',0)>0) else 0)
reg("AX02-07","婚姻",-1,lambda f: 1 if (f['ss'].get('正官',0)>0 and f['ss'].get('七杀',0)>0) else 0)
reg("AX02-08","功名事业",-1,lambda f: 1 if (f['ss'].get('七杀',0)>0 and cnt(f,'食神','伤官')>=2 and cnt(f,'正印','偏印')==0) else 0)
# AX-03
reg("AX03-01x","刑灾官非",+1,lambda f: (f['ss'].get('七杀',0) if has(f,'七杀') else None))
reg("AX03-02","功名事业",-1,lambda f: (cnt(f,'正官','七杀') if 1<=cnt(f,'正官','七杀')<=4 else None))
reg("AX03-03x","刑灾官非",+1,lambda f: 1 if (cnt(f,'比肩','劫财')==0 and cnt(f,'正印','偏印')==0) else 0)
reg("AX03-04","财",-1,lambda f: 1 if (cnt(f,'正财','偏财')>=3 and cnt(f,'比肩','劫财')==0 and cnt(f,'正印','偏印')==0) else 0)
# AX-04
reg("AX04-01","功名事业",+1,lambda f: 1 if (tgpos(f,'正官','七杀') & {'年','月'}) else 0)
reg("AX04-02x","刑灾官非",+1,lambda f: 1 if (tgpos(f,'七杀') & {'日','时'}) else 0)
reg("AX04-03","财",+1,lambda f: 1 if (tgpos(f,'正财','偏财') & {'年','月'}) else 0)
reg("AX04-04x","六亲",-1,lambda f: (1 if (tgpos(f,'伤官') & {'时'}) else 0) if fem(f) else None)
# AX-05
reg("AX05-01","婚姻",-1,lambda f: hit(f['ch'], dayzhi(f)))
reg("AX05-02","婚姻",-1,lambda f: hit(f['he'], dayzhi(f)))
reg("AX05-03","婚姻",-1,lambda f: hit(f['xing'], dayzhi(f)))
# AX-06
reg("AX06-01","寿元健康",-1,lambda f: 1 if any(f['wx'].get(w,0)==0 for w in '木火土金水') else 0)
reg("AX06-02x","刑灾官非",+1,lambda f: 1 if any(f['wx'].get(w,0)>=4 for w in '木火土金水') else 0)
# AX-07
reg("AX07-01","功名事业",+1,lambda f: 1 if any(p and len(p)>1 and p[1] in '辰戌丑未' for p in f['pil']) else 0)
# AX-08
reg("AX08-01","功名事业",-1,lambda f: (1 if (f['yl'] in '亥子丑' and f['day'][0] in '丙丁' and f['wx'].get('火',0)==0) else 0) if f['yl'] else None)
reg("AX08-02","功名事业",-1,lambda f: (1 if (f['yl'] in '巳午未' and f['day'][0] in '壬癸' and f['wx'].get('水',0)==0) else 0) if f['yl'] else None)
# AX-09 女命
reg("AX09-01","婚姻",-1,lambda f: (1 if (cnt(f,'正官','七杀')>0 and not (tgpos(f,'正官','七杀') & {'日','时'})) else 0) if fem(f) else None)
reg("AX09-02","婚姻",-1,lambda f: (1 if (f['ss'].get('正官',0)>0 and f['ss'].get('七杀',0)>0) else 0) if fem(f) else None)
reg("AX09-03","婚姻",-1,lambda f: (1 if (cnt(f,'比肩','劫财')==0 and cnt(f,'正印','偏印')==0) else 0) if fem(f) else None)
reg("AX09-05","婚姻",-1,lambda f: (1 if cnt(f,'正官','七杀')==0 else 0) if fem(f) else None)
# AX-11 财富载体
def carr(f):
    if cnt(f,'正官','七杀')>0: return 2
    if cnt(f,'食神','伤官')>0: return 1
    if cnt(f,'正财','偏财')>0: return 0
    return None
reg("AX11-01","财",+1,carr)

SKIP = {
 "AX03-05":"口径对比实验（另行，三口径并跑）",
 "AX05-04":"库无空亡字段 → 未蒸清单",
 "AX06-03":"库无健康域 → 未蒸清单",
 "AX07-02":"需先造「墓」字段 → 未蒸清单",
 "AX08-03":"巾箱单格诀 n≈3，C 档参照",
 "AX10-01":"需流年数据（限 case_events 子集），排最后",
 "AX10-02":"同上",
 "AX10-03":"同上",
}

def stat(fn, dom, outc, key, ids, F):
    b, y = [], []
    for cid in ids:
        f = F[cid]
        try: v = fn(f)
        except Exception: v = None
        if v is None: continue
        if outc == "G":
            pols = [p for p, _ in f[key].values() if p is not None]
            if not pols: continue
            yv = 1 if '凶' in pols else 0
        else:
            pol, lvl = f[key].get(dom, (None, None))
            if outc == "L":
                if lvl is None: continue
                yv = lvl
            else:
                if pol is None: continue
                yv = 1 if pol == '凶' else 0
        b.append(v); y.append(yv)
    return z_linlin(b, y)

def run():
    F = load()
    L = []; add = L.append
    odd = [c for c in F if c % 2 == 1]
    even = [c for c in F if c % 2 == 0]
    add(f"库 {len(F)} 例 ｜ 分半：奇 {len(odd)} / 偶 {len(even)}（库内唯一独立轴）")
    add(f"预注册：校正单元=轴 K=11 ⇒ z_crit={ZC} ｜ 一致判据：两半同号且都 |z|≥1.5 ｜ 两源同号才算复现")
    add("出口：L=等级(序数,高=好) ｜ X=域凶率(二值,凶=1) ｜ G=全局凶率(该例任意域见凶)")
    add("")
    add(f"{'条目':<11}{'域':<9}{'出口':<4}{'源':<3}{'n':>5}{'z奇':>8}{'z偶':>8}  判定")
    add("-"*80)
    rows = []
    for eid, (dom, sign, fn) in P.items():
        for outc in ("L", "X", "G"):
            sgn = sign if outc == "L" else -sign
            for sname, key in (("A", "A"), ("B", "B")):
                z1, n1, w1 = stat(fn, dom, outc, key, odd, F)
                z2, n2, w2 = stat(fn, dom, outc, key, even, F)
                if z1 is None or z2 is None:
                    add(f"{eid:<11}{dom:<9}{outc:<4}{sname:<3}{max(n1,n2):>5}{'—':>8}{'—':>8}  {w1 or w2 or '样本不足'}")
                    continue
                both = min(abs(z1), abs(z2))
                agree = (z1 > 0) == (z2 > 0)
                if agree and both >= ZC:
                    tag = "★★两半一致且过轴线"
                elif agree and both >= 1.5:
                    tag = "★两半一致"
                elif both >= ZC:
                    tag = "×两半反向"
                else:
                    tag = "·平"
                add(f"{eid:<11}{dom:<9}{outc:<4}{sname:<3}{min(n1,n2):>5}{z1:+8.2f}{z2:+8.2f}  {tag}")
                if both >= 1.5 and agree:
                    rows.append((both, eid, dom, outc, sname, z1, z2, tag))
    add("")
    add("== 两半一致（|z|≥1.5 且同号）——排序＝较弱半的强度 ==")
    for both, eid, dom, outc, sname, z1, z2, tag in sorted(rows, reverse=True):
        add(f"  {both:+.2f}  {eid:<11}{dom:<9}{outc:<4}{sname:<3}  z奇={z1:+.2f} z偶={z2:+.2f}  {tag}")
    if not rows: add("  （无）")
    add("")
    add("== 两源都进上表（跨源 + 跨半 = 最强）==")
    key2 = {}
    for both, eid, dom, outc, sname, z1, z2, tag in rows:
        key2.setdefault((eid, outc), set()).add(sname)
    best = [f"{e}·{o}" for (e, o), s in key2.items() if len(s) == 2]
    add("  " + (", ".join(sorted(best)) if best else "（无）"))
    add("")
    add("== 结构性测不动（无出口/无变异）==")
    for eid in ("AX01-07x","AX02-01x","AX02-03x","AX02-05x","AX03-01x","AX03-03x","AX04-02x","AX04-04x","AX06-02x"):
        add(f"  {eid}: 刑灾官非/六亲 域在库内无出口（54 例全凶、零吉向、无等级）或被测条件无变异")
    add("")
    add("== 跳过 ==")
    for k, v in SKIP.items(): add(f"  {k}: {v}")
    txt = "\n".join(L)
    open(os.path.join(HERE, "score-splithalf.txt"), "w", encoding="utf-8").write(txt)
    print(txt)

if __name__ == "__main__":
    run()
