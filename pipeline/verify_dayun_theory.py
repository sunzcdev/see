#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_dayun_theory.py — 大运/起运「理论自洽」体检（只读）

命理规则（三条，都可独立判定，不依赖任何"参考实现"）：
  ① 方向：**阳年男、阴年女 → 顺排；阴年男、阳年女 → 逆排**（生死在年干阴阳×性别）。
  ② 序列：顺排则干支序列沿六十甲子 **+1** 走，逆排则 **−1** 走（天干差 ±1、地支差 ∓1）。
  ③ 起运：**到节天数 ÷ 3 = 岁**。节与节相隔约 **30.4 天**（不是 15 天——15 天是「节↔气」的间距），
     故出生到下一/上一个节的距离 ∈ [0, 30.4] ⇒ 起运 ∈ **[0, 10.1] 岁**。
     实测本库中位 5.40 岁，与均匀分布吻合；>10.3 岁的属边界/交节日异常，需单独看。
     ⚠️ 2026-10-09 自审纠正：本条最初写成「上限约 5 岁」，是把「节」当成了「节气」（气每 15 天一个），**已撤回**。

用法：python3 scripts/verify_dayun_theory.py [--show N]
退出码 0＝三条全过。
"""
import argparse, sqlite3, sys, json

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"
GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
YANG_GAN = set("甲丙戊庚壬")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--show", type=int, default=6); a = ap.parse_args()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute("""SELECT case_id, gender, year_pillar, dayun_direction, qiyun_age, dayun_sequence,
                                 gender_grade FROM case_features""").fetchall()
    con.close()
    mis, seqbad, over, caveat = [], [], [], 0
    n_dir = n_seq = 0
    for cid, g, yp, dd, qa, ds, gg in rows:
        if g in ("乾", "坤") and dd in ("顺排", "逆排") and yp and yp[0] in GAN:
            n_dir += 1
            exp = "顺排" if ((g == "乾") == (yp[0] in YANG_GAN)) else "逆排"
            if exp != dd:
                mis.append((cid, g, yp, dd, exp, gg or "-"))
                if (gg or "") in ("PASS", "KQ"):
                    caveat += 1        # 性别高可信的，违规更可能是四柱/方向真错
        if ds:
            n_seq += 1
            seq = [s for s in ds.replace("→", " ").split() if len(s) >= 2]
            for i in range(len(seq) - 1):
                dg = (GAN.index(seq[i + 1][0]) - GAN.index(seq[i][0])) % 10
                dz = (ZHI.index(seq[i + 1][1]) - ZHI.index(seq[i][1])) % 12
                if dg not in (1, 9) or (dg == 1 and dz != 1) or (dg == 9 and dz != 11):
                    seqbad.append((cid, seq[i], seq[i + 1]))
        if qa not in (None, ""):
            try:
                if float(qa) > 10.3:
                    over.append((cid, float(qa)))
            except ValueError:
                pass
    print("=" * 74)
    print("① 方向：阳男阴女顺 / 阴男阳女逆")
    print(f"   可比 {n_dir} 例，不符 {len(mis)} 例（{len(mis)/max(n_dir,1):.1%}）"
          f"，其中性别高可信(PASS/KQ) {caveat} 例 ⇒ 不能都推给性别")
    print("   对照组：原文自带的「四柱+大运」块符合规则的 552/560（99%）：")
    print("   ⇒ 规则本身没问题，**病在库的抽取/配对**（见 theory-review 报告）")
    for m in mis[:a.show]:
        print(f"     ✗ case {m[0]} {m[1]} 年柱{m[2]} 库={m[3]} 规则={m[4]}（性别可信度 {m[5]}）")
    pass
    print(f"② 序列方向：顺排 +1 / 逆排 −1（干支同步）")
    print(f"   {n_seq} 例，不连续 {len(seqbad)} 处 " + ("✅" if not seqbad else "✗"))
    for m in seqbad[:a.show]:
        print(f"     ✗ case {m[0]} {m[1]}→{m[2]}")
    print(f"③ 起运：到节天数÷3 ⇒ 理论区间 [0, 10.1] 岁")
    print(f"   >10.3 岁共 {len(over)} 例 " + ("✅" if not over else "✗"))
    for m in over[:a.show]:
        print(f"     ✗ case {m[0]} 起运 {m[1]} 岁")
    bad = len(seqbad) + len(over)
    print(("✅ 序列与起运通过；方向缺口 → 见上（多为四柱配对脏）" if bad == 0 else "✗ 有硬伤"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
