#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""无标签池体检（mechanism_tag 规则集完备性分析）

背景：正确尺（shishen_quan + 重标定阈值）下全库 2322 例有 470 例（20.2%）18 条自动规则
一条都不命中 ⇒ 说明**规则集不完备**（不是打标失败）。补规则前必须先看清缺口的结构，
否则就是「为了覆盖率硬贴标签」（标签注水的反面教材）。

本脚本只做体检 + 候选规则可行性试算，**不写库**。补规则的落地改 mechanism_tag.py。
用法：python3 scripts/analyze_unlabeled.py
"""
import os, sys, json, sqlite3
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "distill"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import mechanism_tag as M          # 现行规则（复用，不复制）
from score_entries import load as load_features   # 复用特征加载器（避免第二份真相）
import entries_spec as SPEC

# 月支本气（算「月令十神」用）
ZHI_BENQI = {'子':'癸','丑':'己','寅':'甲','卯':'乙','辰':'戊','巳':'丙',
             '午':'丁','未':'己','申':'庚','酉':'辛','戌':'戊','亥':'壬'}
WX_GAN = {'甲':'木','乙':'木','丙':'火','丁':'火','戊':'土','己':'土','庚':'金','辛':'金','壬':'水','癸':'水'}
SHENG = {'木':'火','火':'土','土':'金','金':'水','水':'木'}     # 我生
KE = {'木':'土','土':'水','水':'火','火':'金','金':'木'}        # 我克


def shishen_of(day_gan, other_gan):
    """日干 vs 另一天干 → 十神（含同/异阴阳）"""
    if not day_gan or not other_gan:
        return None
    a, b = WX_GAN.get(day_gan), WX_GAN.get(other_gan)
    if not a or not b:
        return None
    same = (('甲丙戊庚壬'.index(day_gan) % 2) == ('甲丙戊庚壬'.index(other_gan) % 2)) \
        if day_gan in '甲丙戊庚壬' and other_gan in '甲丙戊庚壬' else \
        (('乙丁己辛癸'.index(day_gan) % 2) == ('乙丁己辛癸'.index(other_gan) % 2)) \
        if day_gan in '乙丁己辛癸' and other_gan in '乙丁己辛癸' else \
        (day_gan in '甲丙戊庚壬') == (other_gan in '甲丙戊庚壬')
    if a == b:
        return '比肩' if same else '劫财'
    if SHENG[a] == b:
        return '食神' if same else '伤官'
    if KE[a] == b:
        return '偏财' if same else '正财'
    if KE[b] == a:
        return '七杀' if same else '正官'
    if SHENG[b] == a:
        return '偏印' if same else '正印'
    return None


def yueling_shishen(f):
    return shishen_of(f['day'][0], ZHI_BENQI.get(f['yl'], ''))


def profile(f):
    ss = f['ss']
    bi = ss.get('比肩', 0) + ss.get('劫财', 0)
    cai = ss.get('正财', 0) + ss.get('偏财', 0)
    guansha = ss.get('正官', 0) + ss.get('七杀', 0)
    yin = ss.get('正印', 0) + ss.get('偏印', 0)
    shishang = ss.get('食神', 0) + ss.get('伤官', 0)
    return dict(bi=bi, cai=cai, guansha=guansha, yin=yin, shishang=shishang)


def main():
    F = load_features()
    unlabeled = []
    for cid in sorted(F):
        f = F[cid]
        # 生产语义＝ pick_primary(calc_tags(...)) —— 人工格局开关也算标签，
        # 漏算它会把 12 例「从杀/从财/从儿/从势」误判成无标签（探针曾犯此错，2026-10-07 已纠）
        zhis = [p[1] for p in f['pil'] if p and len(p) > 1]
        ps = f.get('ps') or []      # 人工格局开关（从 case_features.pattern_switches 读入）
        tags = M.calc_tags(f['ss'], zhis, f['day'], f['yl'])
        if not M.pick_primary(tags, f['yl'], ps):
            unlabeled.append(cid)
    n = len(F)
    print(f"全库 {n} 例 ｜ 无标签 {len(unlabeled)}（{len(unlabeled)/n*100:.1f}%）")
    print("（口径：正确尺 shishen_quan + 重标定阈值；无标签＝18 条规则全不命中）\n")

    # 无标签池的十神画像
    buckets = Counter()
    bi3 = []
    for cid in unlabeled:
        p = profile(F[cid])
        key = []
        if p['bi'] >= 3: key.append('比劫≥3')
        if p['cai'] == 0: key.append('无财')
        if p['guansha'] == 0: key.append('无官杀')
        if p['yin'] == 0: key.append('无印')
        if p['shishang'] == 0: key.append('无食伤')
        if p['bi'] >= 3:
            bi3.append(cid)
        buckets[' + '.join(key) if key else '（十神齐但强度不足）'] += 1
    print("无标签池结构（前 12）:")
    for k, v in buckets.most_common(12):
        print(f"  {v:4d}  {k}")

    # 比劫≥3 子结构：按「财/官杀/印/食伤」四轴分桶
    print(f"\n【比劫≥3 子池：{len(bi3)} 例】按 财/官杀/印/食伤 分桶")
    sub = Counter()
    for cid in bi3:
        p = profile(F[cid])
        def band(v):
            return '0' if v == 0 else ('1-2' if v <= 2 else '≥3')
        sub[(band(p['cai']), band(p['guansha']), band(p['yin']), band(p['shishang']))] += 1
    print("  财 ／ 官杀 ／ 印 ／ 食伤       例数")
    for k, v in sub.most_common(15):
        print(f"  {k[0]:>3} ／ {k[1]:>3} ／ {k[2]:>3} ／ {k[3]:>4}   {v:4d}")

    # 月令十神分布（比劫≥3 子池）——「建禄/月劫格」候选
    ylss = Counter(yueling_shishen(F[cid]) for cid in bi3)
    print(f"\n比劫≥3 子池的月令十神: " + " ｜ ".join(f"{k or '?'} {v}" for k, v in ylss.most_common(6)))

    # 候选新规则试算（不写库）
    print("\n【候选规则试算】（同一批 2322 例上算覆盖 + 落进无标签池多少）")
    cands = [
        ("比劫重重", lambda p, f: p['bi'] >= 4),
        ("群比争财", lambda p, f: p['bi'] >= 3 and 1 <= p['cai'] <= 2),
        ("旺而无依", lambda p, f: p['bi'] >= 3 and p['cai'] == 0 and p['guansha'] == 0 and p['shishang'] == 0),
        ("比劫泄秀", lambda p, f: p['bi'] >= 3 and p['shishang'] >= 2 and p['guansha'] == 0),
        ("印比两旺", lambda p, f: p['bi'] >= 3 and p['yin'] >= 3),
        ("建禄月劫格", lambda p, f: yueling_shishen(f) in ('比肩', '劫财')),
        ("比劫重无制无泄", lambda p, f: p['bi'] >= 3 and p['guansha'] == 0 and p['shishang'] == 0),
    ]
    allp = {cid: profile(F[cid]) for cid in F}
    uni = set(unlabeled)
    for name, fn in cands:
        hit = [cid for cid in F if fn(allp[cid], F[cid])]
        cover_new = sum(1 for cid in hit if cid in uni)
        print(f"  {name:<14} 全库命中 {len(hit):5d}  ｜ 其中无标签 {cover_new:4d}"
              f"  ｜ 命中率 {len(hit)/n*100:5.1f}%")
        if name == "比劫重重":
            for t in (3, 4, 5):
                h = [cid for cid in F if allp[cid]['bi'] >= t]
                print(f"      （试阈值 比劫≥{t}: 命中 {len(h)}，无标签中 {sum(1 for c in h if c in uni)}，"
                      f"命中率 {len(h)/n*100:.1f}%）")


def gap_correction():
    """旧框架核查：v2 文档说「470 池缺『比劫重身旺』族（身旺无财）」——本函数证伪/证实之。

    判据：比劫≥3 只是必要条件，不说明结构。真正的「身旺无依」需 比劫≥3 ∧ 财=0 ∧ 官杀=0 ∧ 食伤=0。
    """
    F = load_features()
    uni = []
    for cid in sorted(F):
        f = F[cid]
        zhis = [p[1] for p in f['pil'] if p and len(p) > 1]
        if not M.pick_primary(M.calc_tags(f['ss'], zhis, f['day'], f['yl']), f['yl'], f.get('ps') or []):
            uni.append(cid)
    bi3 = [c for c in uni if profile(F[c])['bi'] >= 3]
    true_wuyi = [c for c in bi3
                 if profile(F[c])['cai'] == 0 and profile(F[c])['guansha'] == 0 and profile(F[c])['shishang'] == 0]
    print(f"\n【旧框架核查】无标签 {len(uni)} 例 ｜ 其中比劫≥3 有 {len(bi3)} 例")
    print(f"  比劫≥3 里「真·无财∧无官杀∧无食伤」: {len(true_wuyi)} 例"
          f"  ⇒ 「缺比劫重身旺一族」的说法" + ("成立" if len(true_wuyi) > 30 else "**不成立**（该结构不构成一族）"))
    print("  ⇒ 缺口在「没有描述中等强度的标签层」，不在「少一条比劫规则」")


if __name__ == "__main__":
    main()
    gap_correction()
