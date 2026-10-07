#!/usr/bin/env python3
# 严重度出口构建器（「出口先于条目」）
# 问题：刑灾官非/六亲 的二元出口天生退化（语料按「出事」挑例，反极性半边不存在）
# 出路：换成「域内严重度」序数出口 S —— 条件化＝只在有该域结局的例内分轻重
#   · 层级顺序＝先验（传统断语轻重：口舌<官司<牢狱<刑伤；疏离<刑克<丧亡；缘薄<难留<克子）
#   · 词表＝从语料普查来的真实词汇（不发明词）
# 纪律：口径换了必须显式声明；无条件版（全库比）登记为「结构性缺口」，不用 S 冒充
import sqlite3, json, sys, math

DB = "/home/ubuntu/projects/jinxiang-kucun/jinxiang.db"

LEX = {
    "刑灾官非": [
        # L1 口舌是非（轻）
        ["是非", "口舌", "争讼", "词讼", "纠纷", "小人", "争吵", "反目"],
        # L2 官司诉讼
        ["官司", "诉讼", "官非", "打官司", "拘", "罚", "败诉", "起诉"],
        # L3 牢狱刑期
        ["牢狱", "入狱", "被捕", "判刑", "有期徒刑", "囚", "坐牢", "犯法", "监狱", "判", "被捕入狱"],
        # L4 刑伤血光/凶死（重）
        ["伤残", "刑伤", "血光", "横死", "凶死", "死于非命", "命案", "残废", "重伤", "身亡"],
    ],
    "六亲": [
        # L1 疏离/缘薄
        ["六亲无靠", "缘薄", "不和", "无靠", "淡薄", "疏远"],
        # L2 刑克/病灾
        ["刑克六亲", "天克地冲", "克父", "克母", "克妻", "克夫", "六亲有灾", "病灾"],
        # L3 丧亡（重）
        ["丧父", "丧母", "早丧", "亡故", "去世", "早逝", "丧妻", "丧夫", "丧子", "丧"],
    ],
    "子女": [
        # L1 缘薄/晚得
        ["子女缘薄", "晚得子", "迟得"],
        # L2 有子难留/不成器
        ["有子难留", "难留", "不成器", "子不肖", "头子未成", "有子难成"],
        # L3 克子/无子（重）
        ["克子", "无子", "伤子", "子亡", "刑妻克子", "无嗣"],
    ],
}


def main():
    write = "--write" in sys.argv
    c = sqlite3.connect(DB)
    cases = {}
    for cid, js, ft in c.execute("select case_id, verdict, fact_text from case_outcomes"):
        if not js: continue
        try: d = json.loads(js)
        except Exception: continue
        cases[cid] = (set(d.keys()), ft or "")

    print("=" * 74)
    for dom, levels in LEX.items():
        # 词频核对
        hitcnt = []
        for lv, words in enumerate(levels, 1):
            tot = sum(1 for cid, (doms, ft) in cases.items() if dom in doms and any(w in ft for w in words))
            per = " ".join(f"{w}={sum(1 for cid,(dm,ft) in cases.items() if dom in dm and w in ft)}" for w in words)
            hitcnt.append(tot)
            print(f"  [{dom} L{lv}] 命中例数={tot}  | {per}")
        # 定档：取命中的最高层
        dist = {}
        sev_rows = []
        for cid, (doms, ft) in cases.items():
            if dom not in doms: continue
            s = 0
            for lv, words in enumerate(levels, 1):
                if any(w in ft for w in words): s = lv
            dist[s] = dist.get(s, 0) + 1
            sev_rows.append((cid, dom, s))
        n = len(sev_rows)
        nc = sum(v for k, v in dist.items() if k > 0)
        c0 = dist.get(0, 0)
        hh = 0.0
        ks = sorted(k for k in dist if k > 0)
        if nc:
            hh = -sum((dist[k]/nc)*math.log2(dist[k]/nc) for k in ks)/math.log2(len(ks)) if len(ks) > 1 else 0.0
        print(f"  [{dom}] 域内 n={n} ｜ 有级 {nc} ｜ 无词 {c0} ｜ 档数 {len(ks)} ｜ "
              f"H/Hmax={hh:.2f} ｜ 分布 {dict(sorted(dist.items()))}")
        # 两半一致性：档分布是否随半变化（量表本身要稳）
        d1, d2 = {}, {}
        for cid, dm, s in sev_rows:
            (d1 if cid % 2 == 1 else d2)[s] = (d1 if cid % 2 == 1 else d2).get(s, 0) + 1
        print(f"        半分布 奇={dict(sorted(d1.items()))} 偶={dict(sorted(d2.items()))}")
        if write:
            c.executemany("insert or replace into case_severity(case_id, dom, sev) values (?,?,?)", sev_rows)

    print("=" * 74)
    if write:
        c.commit()
        print("已写入 case_severity 表")
    else:
        print("（只读普查；加 --write 落库）")


if __name__ == "__main__":
    main()
