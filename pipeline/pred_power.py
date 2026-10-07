#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预测力功效计算器 —— 回答一个问题：**我猜对几条，才算真有本事？**

这是「预测力」课题的量纲地基。没有它，"命中 2 条"这种话没有意义。

三件事：
 1. 正算：给定基线 P0 与想要的真命中率 P1，需要多少条前瞻样本才能以 80% 把握检出（α=0.05 单侧精确二项）。
 2. 反算：给定已有的 n 条、k 条命中、基线 P0 ⇒ p 值 +「距可检出线还差几位」。
 3. 2.8σ 近似线：项目其余部分用的老线 2.8*sqrt(2P0(1-P0)/n)，两条线并列显示以便对照。

用法：
  python3 pred_power.py table                 # 功效总表
  python3 pred_power.py check --n 2 --k 2 --p0 0.5
  python3 pred_power.py check --n 5 --k 4 --p0 0.5
"""
import argparse
import math


def p_ge(k: int, n: int, p0: float) -> float:
    """P(X >= k)，X ~ Binomial(n, p0)。精确计算，无近似。"""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    tot = 0.0
    for i in range(k, n + 1):
        tot += math.comb(n, i) * (p0 ** i) * ((1 - p0) ** (n - i))
    return min(1.0, tot)


def k_crit(n: int, p0: float, alpha: float = 0.05) -> int:
    """α 水平下所需的最小命中数（超过才叫显著）。返回 n+1 表示该 n 下无解。"""
    for k in range(0, n + 1):
        if p_ge(k, n, p0) <= alpha:
            return k
    return n + 1


def min_n(p0: float, p1: float, power: float = 0.8, alpha: float = 0.05) -> int:
    """达到指定把握所需的最小样本数（≤400 条内搜索）。"""
    for n in range(2, 401):
        kc = k_crit(n, p0, alpha)
        if kc > n:
            continue
        pw = sum(math.comb(n, i) * (p1 ** i) * ((1 - p1) ** (n - i)) for i in range(kc, n + 1))
        if pw >= power:
            return n
    return -1


def line28(n: int, p0: float, two_sample: bool = False) -> float:
    """过线所需的命中率。

    ⚠️ 两种口径必须分清，混用会算出荒唐数（本项目踩过）：
      · 单样本（默认，**前瞻命中率检验用这个**）：SE = sqrt(P0(1-P0)/n)
        问的是「这一串命中相比固定基线 P0 是不是运气」。
      · 双样本（two_sample=True）：SE = sqrt(2P0(1-P0)/n)
        问的是「两个率彼此差多少算真差」——**只在库内两源/两半互比时才用**。
    把双样本公式套前瞻命中率，方差被放大一倍 ⇒ 出现「命中率需 >190%」的假不可能。
    """
    k = 2.0 if two_sample else 1.0
    return p0 + 2.8 * math.sqrt(k * p0 * (1 - p0) / n)


def cmd_table(args) -> None:
    print("【正算】想要多准，就得攒多少条前瞻样本（α=0.05 单侧精确二项，把握 80%）")
    print("说明：P0=不靠命理它本来就会发生的概率（基线）；P1=你声称的命中率。")
    print()
    hdr = f"{'基线P0':>6} | " + " | ".join(f"真命中率 P1={v:.0%}" for v in (0.35, 0.45, 0.60, 0.75, 0.90))
    print(hdr)
    print("-" * len(hdr))
    for p0 in (0.10, 0.20, 0.30, 0.40, 0.50):
        cells = []
        for p1 in (0.35, 0.45, 0.60, 0.75, 0.90):
            if p1 <= p0:
                cells.append("  —".rjust(12))
                continue
            n = min_n(p0, p1)
            cells.append((f"{n} 条" if n > 0 else ">400").rjust(12))
        print(f"{p0:>6.2f} | " + " | ".join(cells))
    print()
    a, b = min_n(0.50, 0.75), min_n(0.20, 0.45)
    print(f"读法：基线 50% 的事，你想证明自己有 75% 的本事（高出 25 个点），要 **{a} 条** 前瞻样本。")
    print(f"     基线 20% 的事，想证明有 45%（同样高 25 个点），只要 **{b} 条**。")
    print("     ⇒ 门槛高的事（基线高）最难证明；想省样本，就该挑**基线低**的事来预测。")
    print()
    print("【对照】2.8σ 单样本线（前瞻命中率**该用这条**）在 P0=0.5 下要求的命中率：")
    for n in (2, 5, 10, 20, 31, 50, 100):
        need = line28(n, 0.5)
        k = math.ceil(need)
        tag = f"需命中 {k:>3} 条（{need:.0%}）" if need <= 1 else "**无解**（n 太小，2.8σ 线在 100% 之上）"
        print(f"  n={n:>3}：{tag}")
    print("  ⇒ 与精确检验同结论：**n 小的时候，必须接近全中才有意义；n<8 基本不可能过线**。")
    print()
    print("⚠️ 不要用双样本式 2.8*sqrt(2P0(1-P0)/n)：那是「两个率互比」用的，")
    print("   套在「命中率 vs 固定基线」上会把方差放大一倍（曾算出「命中率需>190%」的假不可能）。")


def cmd_check(args) -> None:
    n, k, p0 = args.n, args.k, args.p0
    pv = p_ge(k, n, p0)
    rate = k / n if n else 0.0
    need28 = line28(n, p0)
    kc = k_crit(n, p0)
    print(f"样本 n={n}，命中 k={k}（命中率 {rate:.0%}），基线 P0={p0:.0%}")
    print(f"  · 保守 p 值（P(X≥{k}) ）= {pv:.3f}")
    print(f"  · α=0.05 下该 n 需要的命中数 = {('无解（n 太小）' if kc > n else kc)}")
    verdict = "显著，可以当本事" if pv <= 0.05 else "不显著，只能算早期迹象"
    print(f"  · 判决：{verdict}")
    tag = f"命中率需 > {need28:.0%}" if need28 <= 1 else "该 n 下 2.8σ 线在 100% 之上 ⇒ 无解"
    ok = " ✅" if need28 <= 1 and rate > need28 else " ❌"
    print(f"  · 2.8σ 单样本线：{tag}（当前 {rate:.0%}）{ok}")
    if pv > 0.05:
        for extra in range(1, 61):
            if p_ge(k + extra, n + extra, p0) <= 0.05:
                print(f"  · 理想情形（往后**全中且互相独立**）：再攒 **{extra} 条**（即 {k+extra}/{n+extra}）可到 p≤0.05")
                print("    ⚠️ 这是上界；真实世界不可能全中，且这些条目常相关，实际所需远多于此。")
                break
    print()
    print("注意：这里假定各条互相独立。同一个人、同一年、同一次咨询里的多条预测是**相关的**，")
    print("      有效 n 远小于名义 n（一条来自 20 条相关预测的「命中」，有效 n 常常就是 1）。")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("table")
    c = sub.add_parser("check")
    c.add_argument("--n", type=int, required=True)
    c.add_argument("--k", type=int, required=True)
    c.add_argument("--p0", type=float, default=0.5)
    a = ap.parse_args()
    cmd_table(a) if a.cmd == "table" else cmd_check(a)


if __name__ == "__main__":
    main()
