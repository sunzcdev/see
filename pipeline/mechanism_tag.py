#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机制标签打标脚本 v1 (mechanism_tag.py)
作者：兮（项目负责人）
依据：schema/mechanism_tags.md 第一部分
功能：从 case_features 现有字段计算格局机制标签 → mech_primary/mech_aux
规则：18 个自动规则（十神 + 五行 + 地支合冲）

★ 十神口径（2026-10-07 重标定，第二版）：
  默认＝**全字含藏干、日主不计**（`shishen_quan`，ruler_ver=2）＋**重标定阈值**（`mech_thresholds.json`）。
  为什么必须重标定：18 条规则的老阈值（「印≥3」…）标定在**病尺**`shishen_config`（只数天干 ∧ 日主计入比肩）上；
  两尺十神密度差约 4 倍（老 0.3 个/十神、新 1.2–1.34）⇒ **照搬阈值必饱和**（人人命中＝标签无区分度）。
  做法＝**按选择性对齐**：逐判据在新尺上选阈值，使命中率与老尺持平（见 `calibrate_mech.py`，附审计表）。
  ⇒ 换尺只换坐标、不换「筛掉多少人」的信息量；下次再换尺只改 `mech_thresholds.json`，不动代码。
  回归用：`MECH_SS_COL=shishen_config python3 scripts/mechanism_tag.py` 应复现老尺结果（覆盖 1868/2322）。
  落列：`mech_primary` / `mech_aux`（现＝v2）＋ `mech_ver`；老尺结果留档在 `mech_primary_v1` / `mech_aux_v1`。
  覆盖面：正确尺 1852/2322（79.8%）｜老尺 1868/2322（80.4%）—— 几乎相同 ⇒ **覆盖率不是换尺的理由**（见下条历史坑）。
  ✖ 撤回（2026-10-07）：本文件曾写「老尺只覆盖 1234/2322，是病尺稀疏的必然结果」——**已证伪**。
    根因＝库内那批标签是**旧版脚本（尚无「羊刃驾杀」规则）的产物、从未全量回填**；同一脚本重跑即 1868，差额 696 例全在「羊刃驾杀」。
    ⇒ 教训：**「库 ≠ 代码」也是一种口径漂移**；凡覆盖率/分布数字必须标明「哪版脚本 + 哪把尺 + 跑于何时」。
主标签：月令十神优先排序取前 1-2；从格/化气等人工标签永远最前
幂等：重跑覆盖
"""
import sqlite3, json, os

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jinxiang.db')

# 十神口径开关（见文件头 ⚠）。默认老尺：18 条规则的阈值按此标定，换尺须先重标定。
# 'shishen_config' = 老尺（只数天干，日主计入比肩）｜'shishen_quan' = 全字口径含藏干（ruler_ver=2）
# 默认＝正确尺（全字含藏干、日主不计）＋重标定阈值；老尺仅用于回归复现
SS_COL = os.environ.get('MECH_SS_COL', 'shishen_quan')

# 重标定阈值（仅在全字口径下启用；老尺走原阈值＝行为完全不变）
_TH = None
_ST = None            # 旺衰结构层阈值（v3 新增；仅正确尺启用）
if SS_COL == 'shishen_quan':
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mech_thresholds.json')
    if os.path.exists(_p):
        _cfg = json.load(open(_p, encoding='utf-8'))
        _TH = _cfg['thresholds']
        _ST = _cfg.get('structural')
    else:
        raise SystemExit(f'⛔ 全字口径需要重标定阈值，但找不到 {_p}；先跑 calibrate_mech.py')
# MECH_STRUCT=0 可关掉结构层（用于与 v2 结果做等价回归）
if os.environ.get('MECH_STRUCT', '1') == '0':
    _ST = None

def _ge(v, var, old_thr):
    """按老尺写法取阈值：全字口径用重标定值，老尺用原值（回归不变）"""
    t = old_thr if _TH is None else _TH[var][f'ge_{old_thr}']
    return v >= t

def _lt(v, var, old_thr):
    t = old_thr if _TH is None else _TH[var][f'lt_{old_thr}']
    return v < t

# 阳干帝旺位（羊刃）
YANGREN = {'甲': '卯', '乙': '寅', '丙': '午', '丁': '巳', '戊': '午', '己': '巳', '庚': '酉', '辛': '申', '壬': '子', '癸': '亥'}
# 六害（穿）：日支与月支/时支
LIUHAI = [('子','未'),('丑','午'),('寅','巳'),('卯','辰'),('申','亥'),('酉','戌')]
# 月支五行（调候语境用）
ZHI_WX = {'子':'水','丑':'土','寅':'木','卯':'木','辰':'土','巳':'火',
          '午':'火','未':'土','申':'金','酉':'金','戌':'土','亥':'水'}

def calc_tags(shishen, zhis, rizhu, yueling):
    """计算机制标签列表（未排序）"""
    tags = []
    ss = {k: shishen.get(k, 0) for k in ['比肩','劫财','食神','伤官','正财','偏财','正官','七杀','正印','偏印']}
    sha = ss['七杀']; guan = ss['正官']; yin = ss['正印'] + ss['偏印']
    shi = ss['食神']; shang = ss['伤官']; cai = ss['正财'] + ss['偏财']
    bi = ss['比肩'] + ss['劫财']; shishang = shi + shang
    # 格局类（阈值经 _ge/_lt 走「当前尺」：全字口径＝重标定值，老尺＝原值）
    if _ge(sha, 'sha', 1) and _ge(yin, 'yin', 1): tags.append('杀印相生')
    if _ge(guan, 'guan', 1) and _ge(yin, 'yin', 1): tags.append('官印相生')
    if _ge(shi, 'shi', 1) and _ge(sha, 'sha', 1): tags.append('食神制杀')
    if _ge(shang, 'shang', 1) and _ge(sha, 'sha', 1): tags.append('伤官制杀')
    if _ge(shang, 'shang', 1) and _ge(cai, 'cai', 1): tags.append('伤官生财')
    if _ge(shi, 'shi', 1) and _ge(cai, 'cai', 1): tags.append('食神生财')
    if _ge(guan, 'guan', 1) and _ge(sha, 'sha', 1): tags.append('官杀混杂')
    if _ge(yin, 'yin', 3): tags.append('印重身旺')
    if _ge(cai, 'cai', 3) and _lt(bi, 'bi', 2): tags.append('财多身弱')
    if _ge(bi, 'bi', 3) and _ge(cai, 'cai', 1): tags.append('比劫夺财')
    # 羊刃
    yangren_zhi = YANGREN.get(rizhu[0] if rizhu else '')
    if yangren_zhi and yangren_zhi in zhis:
        if _ge(sha, 'sha', 1): tags.append('羊刃驾杀')
        # 羊刃逢冲
        chong_map = {'子':'午','午':'子','卯':'酉','酉':'卯','寅':'申','申':'寅','巳':'亥','亥':'巳','辰':'戌','戌':'辰','丑':'未','未':'丑'}
        if yangren_zhi in chong_map and chong_map[yangren_zhi] in zhis:
            tags.append('羊刃逢冲')
    # 五行组合
    wx = ZHI_WX
    if rizhu and rizhu[0] in '甲乙' and _ge(shishang, 'shishang', 1):
        tags.append('木火通明')
    if rizhu and rizhu[0] in '庚辛' and _ge(cai, 'cai', 1):
        tags.append('金水相涵')
    if yueling in '申酉' and _ge(yin, 'yin', 2):
        tags.append('火炼秋金')
    # 合冲
    if ('寅' in zhis and '申' in zhis) or ('巳' in zhis and '亥' in zhis):
        tags.append('驿马奔波')
    # 六害（日支与月/时支）
    rz_zhi = rizhu[1] if len(rizhu) >= 2 else ''
    for a, b in LIUHAI:
        if (rz_zhi == a and (b in zhis)) or (rz_zhi == b and (a in zhis)):
            tags.append('夫妻宫穿害')
            break
    # 墓库冲开
    if ('辰' in zhis and '戌' in zhis) or ('丑' in zhis and '未' in zhis):
        tags.append('墓库冲开')
    return tags

def calc_structural(shishen):
    """旺衰结构标签（v3 新增）——偏重 / 缺位 / 均平（阈值＝库自身分位，见 mech_thresholds.json）。

    为什么另起一层（2026-10-08 体检，`scripts/analyze_unlabeled.py`）：
      上面 18 条机制规则用的是「**选择性对齐**阈值」——那层的目的是与老尺可比（回归用），
      代价是阈值被抬高（新尺密度是老尺 4 倍 ⇒ 阈值也要 4 倍），于是**中密度案例全落空**。
      库内 470 例（20.2%）无标签，体检发现共性**不是「缺某族机制」**，而是
      **各神俱在而皆轻**（五轴中位数 2、均值 2.40–2.54，无一轴过对齐阈值）⇒ 属阈值分档产物。
      ⇒ 本层用「库自身分位」定阈（偏重＝≥q80＝4），只描述**旺衰结构**，不冒充机制；
        「十神均平」是如实标记「无过重之神」，**不代表该盘有机制可用**。
    """
    if not _ST:
        return []
    fg, ae = _ST.get('focus_ge', 4), _ST.get('absent_eq', 0)
    ss = {k: shishen.get(k, 0) for k in
          ['比肩', '劫财', '食神', '伤官', '正财', '偏财', '正官', '七杀', '正印', '偏印']}
    axes = [('比劫偏重', ss['比肩'] + ss['劫财'], '财缺', ss['正财'] + ss['偏财']),
            ('财偏重', ss['正财'] + ss['偏财'], '官杀缺', ss['正官'] + ss['七杀']),
            ('官杀偏重', ss['正官'] + ss['七杀'], '印缺', ss['正印'] + ss['偏印']),
            ('印偏重', ss['正印'] + ss['偏印'], '食伤缺', ss['食神'] + ss['伤官']),
            ('食伤偏重', ss['食神'] + ss['伤官'], None, None)]
    out = [nm for nm, v, _, _ in axes if v >= fg]
    if not out:
        out = [nm2 for _, _, nm2, v2 in axes if nm2 and v2 == ae]
        if not out:
            out = ['十神均平']
    return out


def pick_primary(tags, yueling, pattern_switches):
    """主标签选取：人工格局开关优先 → 月令十神类优先 → 前 1-2"""
    # 人工标签（格局开关）永远最前
    manual = []
    for ps in pattern_switches:
        for m in ['从杀','从财','从儿','从势','化气','专旺','两神成像']:
            if m in ps and m not in manual:
                manual.append(m)
    # 月令十神类优先序（按月支本气）
    yueling_order = []
    # 简化：把与月令五行相关的标签排前
    if yueling in '寅卯': yueling_order = ['木火通明','官杀混杂','比劫夺财','杀印相生']
    elif yueling in '巳午': yueling_order = ['火炼秋金','伤官生财','食神生财','官杀混杂','羊刃驾杀']
    elif yueling in '申酉': yueling_order = ['金水相涵','财多身弱','食神制杀','伤官生财']
    elif yueling in '亥子': yueling_order = ['杀印相生','官印相生','羊刃驾杀','官杀混杂']
    else: yueling_order = ['比劫夺财','财多身弱','食神生财','伤官生财']
    ordered = [t for t in yueling_order if t in tags] + [t for t in tags if t not in yueling_order]
    ordered = manual + ordered
    return ordered

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT case_id, rizhu, yueling, shishen_quan, shishen_config, di_zhi_freq, pattern_switches
        FROM case_features
    """).fetchall()
    n = 0
    n_fallback = 0
    for case_id, rizhu, yueling, ss_quan, ss_old, dz_json, ps_json in rows:
        ss_json = ss_quan if SS_COL == 'shishen_quan' else ss_old
        if not ss_json:
            ss_json = ss_old or ss_quan
            n_fallback += 1
        try:
            ss = json.loads(ss_json or '{}')
            dz = json.loads(dz_json or '{}')
            ps = json.loads(ps_json or '[]')
        except Exception:
            continue
        if not rizhu or not yueling:
            continue
        zhis = [z for z, c in dz.items() if c > 0]
        tags = calc_tags(ss, zhis, rizhu, yueling)
        # 结构层**追加在最后** ⇒ 既有 18 条规则的主标签选取序完全不变（可回归验证）
        tags = tags + calc_structural(ss)
        ordered = pick_primary(tags, yueling, ps)
        if ordered:
            primary = ordered[0]
            aux = ordered[1:4]
        else:
            primary = ''
            aux = []
        cur.execute("UPDATE case_features SET mech_primary=?, mech_aux=?, mech_ver=? WHERE case_id=?",
                    (primary, json.dumps(aux, ensure_ascii=False),
                     1 if SS_COL == 'shishen_config' else (3 if _ST else 2), case_id))
        n += 1
    conn.commit()
    # 统计
    st_txt = '关' if not _ST else f"开（偏重>={_ST.get('focus_ge')}／缺位=={_ST.get('absent_eq')}）"
    print(f'打标完成: {n} 例 ｜ 十神口径 = {SS_COL} ｜ 机制层阈值 = '
          f'{"原值(老尺)" if _TH is None else "重标定"} ｜ 结构层 = {st_txt}')
    if n_fallback:
        print(f'⚠ 回退老尺（shishen_quan 为空）: {n_fallback} 例 —— 这批的比劫阈值口径不一致，须排查')
    print('主标签分布（前 15）:')
    for r in cur.execute("SELECT mech_primary, COUNT(*) FROM case_features WHERE mech_primary != '' GROUP BY mech_primary ORDER BY COUNT(*) DESC LIMIT 15").fetchall():
        print(f'  {r[0]}: {r[1]}')
    no_tag = cur.execute("SELECT COUNT(*) FROM case_features WHERE mech_primary = ''").fetchone()[0]
    print(f'无标签: {no_tag}')
    conn.close()

if __name__ == '__main__':
    main()
