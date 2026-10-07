#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机制标签打标脚本 v1 (mechanism_tag.py)
作者：兮（项目负责人）
依据：schema/mechanism_tags.md 第一部分
功能：从 case_features 现有字段计算格局机制标签 → mech_primary/mech_aux
规则：18 个自动规则（十神 + 五行 + 地支合冲）

⚠ 十神口径（2026-10-07 自审）：本脚本**故意用「老尺」`shishen_config`（只数天干）**，因为下面 18 条规则的阈值都是在这把尺上标定的。
  实测换到「全字口径含藏干」(`shishen_quan`) 会让 **99.6%（2313/2322）例的标签集合变化**（老尺口径下十神命中稀疏 ⇒ 规则大量静默不触发）。
  ⇒ **换尺必须同时重标定阈值**，不许直接切。要切换请改 `SS_COL` 并先跑对照实验。
  另注：老尺口径下本脚本只给 1234/2322 例打上主标签（1088 例空）——这是口径稀疏的必然结果，不是脚本坏了。
主标签：月令十神优先排序取前 1-2；从格/化气等人工标签永远最前
幂等：重跑覆盖
"""
import sqlite3, json, os

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jinxiang.db')

# 十神口径开关（见文件头 ⚠）。默认老尺：18 条规则的阈值按此标定，换尺须先重标定。
# 'shishen_config' = 老尺（只数天干，日主计入比肩）｜'shishen_quan' = 全字口径含藏干（ruler_ver=2）
SS_COL = os.environ.get('MECH_SS_COL', 'shishen_config')

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
    bi = ss['比肩'] + ss['劫财']
    # 格局类
    if sha >= 1 and yin >= 1: tags.append('杀印相生')
    if guan >= 1 and yin >= 1: tags.append('官印相生')
    if shi >= 1 and sha >= 1: tags.append('食神制杀')
    if shang >= 1 and sha >= 1: tags.append('伤官制杀')
    if shang >= 1 and cai >= 1: tags.append('伤官生财')
    if shi >= 1 and cai >= 1: tags.append('食神生财')
    if guan >= 1 and sha >= 1: tags.append('官杀混杂')
    if yin >= 3: tags.append('印重身旺')
    if cai >= 3 and bi < 2: tags.append('财多身弱')
    if bi >= 3 and cai >= 1: tags.append('比劫夺财')
    # 羊刃
    yangren_zhi = YANGREN.get(rizhu[0] if rizhu else '')
    if yangren_zhi and yangren_zhi in zhis:
        if sha >= 1: tags.append('羊刃驾杀')
        # 羊刃逢冲
        chong_map = {'子':'午','午':'子','卯':'酉','酉':'卯','寅':'申','申':'寅','巳':'亥','亥':'巳','辰':'戌','戌':'辰','丑':'未','未':'丑'}
        if yangren_zhi in chong_map and chong_map[yangren_zhi] in zhis:
            tags.append('羊刃逢冲')
    # 五行组合
    wx = ZHI_WX
    if rizhu and rizhu[0] in '甲乙' and ss['食神'] + ss['伤官'] >= 1:
        tags.append('木火通明')
    if rizhu and rizhu[0] in '庚辛' and ss['正财'] + ss['偏财'] >= 1:
        tags.append('金水相涵')
    if yueling in '申酉' and ss['正印'] + ss['偏印'] >= 2:
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
        ordered = pick_primary(tags, yueling, ps)
        if ordered:
            primary = ordered[0]
            aux = ordered[1:4]
        else:
            primary = ''
            aux = []
        cur.execute("UPDATE case_features SET mech_primary=?, mech_aux=? WHERE case_id=?",
                    (primary, json.dumps(aux, ensure_ascii=False), case_id))
        n += 1
    conn.commit()
    # 统计
    print(f'打标完成: {n} 例 ｜ 十神口径 = {SS_COL}')
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
