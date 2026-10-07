#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
巾箱案例特征提取脚本 v1 (extract_features.py)
作者：兮（项目负责人）
依据：schema/feature_index.sql + extraction_design.md v2 终版
功能：从 batches 表增量提取案例特征 → case_features / iron_laws / feature_extract_log
原则：纯增量、幂等（同 batch_no+case_no 覆盖）、不动 batches 表
用法：python3 scripts/extract_features.py [--batch N] [--dry-run] [--full]
"""
import sqlite3, json, re, sys, os
from collections import Counter

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'jinxiang.db')

# ── 命理常量 ──────────────────────────────────────────────
GAN = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸']
ZHI = ['子','丑','寅','卯','辰','巳','午','未','申','酉','戌','亥']
WUXING = {'甲':'木','乙':'木','丙':'火','丁':'火','戊':'土','己':'土',
          '庚':'金','辛':'金','壬':'水','癸':'水'}
ZHI_WX = {'子':'水','丑':'土','寅':'木','卯':'木','辰':'土','巳':'火',
          '午':'火','未':'土','申':'金','酉':'金','戌':'土','亥':'水'}

# 藏干表：(本气, 中气, 余气)
CANG = {
    '子': ('癸','',''), '丑': ('己','癸','辛'),
    '寅': ('甲','丙','戊'), '卯': ('乙','',''),
    '辰': ('戊','乙','癸'), '巳': ('丙','庚','戊'),
    '午': ('丁','己',''), '未': ('己','丁','乙'),
    '申': ('庚','壬','戊'), '酉': ('辛','',''),
    '戌': ('戊','辛','丁'), '亥': ('壬','甲',''),
}
# 三系权重 (本气, 中气, 余气)
WEIGHTS = {
    'standard':     (1.0, 0.5, 0.3),
    'conservative': (1.0, 0.3, 0.1),
    'blind':        (1.0, 1.0, 1.0),
}
# 理论归一化基数：四柱八字理论平均得分（天干1+地支藏干加权≈1，四柱≈4）
THEORY_BASE = 4.0
WANG = 1.5   # 比值≥1.5 旺
RUO  = 0.5   # 比值≤0.5 弱

# 六合 / 六冲 / 三合 / 三会 / 刑
LIUHE = [('子','丑'),('寅','亥'),('卯','戌'),('辰','酉'),('巳','申'),('午','未')]
LIUCHONG = [('子','午'),('丑','未'),('寅','申'),('卯','酉'),('辰','戌'),('巳','亥')]
SANHE = {
    '三合火局': ('寅','午','戌'), '三合水局': ('申','子','辰'),
    '三合木局': ('亥','卯','未'), '三合金局': ('巳','酉','丑'),
}
SANHUI = {
    '三会东方': ('寅','卯','辰'), '三会南方': ('巳','午','未'),
    '三会西方': ('申','酉','戌'), '三会北方': ('亥','子','丑'),
}
XING = [('寅','巳','申'),('丑','戌','未'),('子','卯')]  # 简化三刑组

# 十神
def shishen(day_gan, other_gan):
    """以日干为我，other 对我的十神"""
    if other_gan == day_gan:
        return '比肩'
    wx_me, wx_other = WUXING[day_gan], WUXING[other_gan]
    yang_me = day_gan in '甲丙戊庚壬'
    yang_other = other_gan in '甲丙戊庚壬'
    same_yang = (yang_me == yang_other)
    if wx_other == wx_me:
        return '劫财'
    # 我生
    if (wx_me, wx_other) in [('木','火'),('火','土'),('土','金'),('金','水'),('水','木')]:
        return '食神' if same_yang else '伤官'
    # 我克
    if (wx_me, wx_other) in [('木','土'),('火','金'),('土','水'),('金','木'),('水','火')]:
        return '偏财' if same_yang else '正财'
    # 克我
    if (wx_other, wx_me) in [('木','土'),('火','金'),('土','水'),('金','木'),('水','火')]:
        return '七杀' if same_yang else '正官'
    # 生我
    return '偏印' if same_yang else '正印'

SHISHEN_NAMES = ['比肩','劫财','食神','伤官','正财','偏财','正官','七杀','正印','偏印']

def get_baseline(yueling):
    """从 wx_theory_baseline 读理论系数 dict {五行:系数}"""
    cur = DB_CONN.cursor()
    row = cur.execute("SELECT wood_coef,fire_coef,earth_coef,metal_coef,water_coef FROM wx_theory_baseline WHERE yueling=?", (yueling,)).fetchone()
    if not row:
        return None
    return {'木': row[0], '火': row[1], '土': row[2], '金': row[3], '水': row[4]}

def calc_wuxing(pillars, yueling):
    """五行三系计算 → (三系档位dict, 共识list, 敏感list)"""
    baseline = get_baseline(yueling)
    if baseline is None:
        return None
    scores = {}
    for name, (b, z, y) in WEIGHTS.items():
        s = {wx: 0.0 for wx in '木火土金水'}
        for pillar in pillars:
            g, zhi = pillar[0], pillar[1]
            s[WUXING[g]] += 1.0                       # 天干 1 分
            bq, zq, yq = CANG[zhi]
            if bq: s[WUXING[bq]] += b
            if zq: s[WUXING[zq]] += z
            if yq: s[WUXING[yq]] += y
        scores[name] = s
    # 归一化 → 三档
    levels = {}
    for name, s in scores.items():
        lv = {}
        for wx in '木火土金水':
            ratio = s[wx] / (baseline[wx] * THEORY_BASE)
            if ratio >= WANG: lv[wx] = '旺'
            elif ratio <= RUO: lv[wx] = '弱'
            else: lv[wx] = '平'
        levels[name] = lv
    # 共识/敏感
    consensus, sensitive = [], []
    for wx in '木火土金水':
        vals = {levels[n][wx] for n in levels}
        if len(vals) == 1:
            consensus.append(wx)
        else:
            sensitive.append(wx)
    return levels, consensus, sensitive

# ── 格局/合冲检测 ────────────────────────────────────────
def detect_patterns(zhis, reply_text, gans=None):
    """格局开关：自动（三合/三会/四库）+ reply 提取（从格/化气/专旺）"""
    sw = []
    zset = set(zhis)
    for name, trio in SANHE.items():
        if all(z in zset for z in trio):
            sw.append(name)
    for name, trio in SANHUI.items():
        if all(z in zset for z in trio):
            sw.append(name)
    # 四库土局：辰戌丑未≥3 + 天干透戊己（schema 要求）
    kus = [z for z in zhis if z in '辰戌丑未']
    if len(kus) >= 3 and gans and any(g in '戊己' for g in gans):
        sw.append('四库土局')
    # reply 提取（宁缺毋滥，reply 优先）
    if reply_text:
        for kw in ['从杀','从财','从儿','从势','化气','专旺','两神成像']:
            if kw in reply_text:
                sw.append(kw + '格' if not kw.endswith('格') and kw not in ('两神成像','专旺') else kw)
    return list(dict.fromkeys(sw))

def detect_hechong(zhis):
    he, chong, hui, xing = [], [], [], []
    # 六合（两两）
    for i in range(4):
        for j in range(i+1, 4):
            a, b = zhis[i], zhis[j]
            if (a,b) in LIUHE or (b,a) in LIUHE:
                he.append(f'{a}{b}合')
            if (a,b) in LIUCHONG or (b,a) in LIUCHONG:
                chong.append(f'{a}{b}冲')
            if (a,b) in XING or (b,a) in XING:
                xing.append(f'{a}{b}刑')
    # 三会
    for name, trio in SANHUI.items():
        if all(z in zhis for z in trio):
            hui.append(name.replace('三会','会'))
    return he, chong, hui, xing

# ── 大运解析 ─────────────────────────────────────────────
def parse_dayun(dayun_str):
    if not dayun_str:
        return '?', None, '', ''
    m = re.search(r'\(([\d.]+)岁\)', dayun_str)
    age = float(m.group(1)) if m else None
    seq = re.sub(r'\s*\([\d.]+岁\)\s*$', '', dayun_str).strip()
    parts = [p.strip() for p in seq.split('→') if p.strip()]
    first = parts[0] if parts else ''
    # 方向推断：月柱→首柱 天干步进
    return '?', age, first, '→'.join(parts)

def infer_direction(month_pillar, first_dayun):
    """由月柱与首柱天干顺序推断顺逆"""
    if not first_dayun or len(month_pillar) < 2:
        return '?'
    mg, fg = month_pillar[0], first_dayun[0]
    if mg not in GAN or fg not in GAN:
        return '?'
    step = (GAN.index(fg) - GAN.index(mg)) % 10
    if step in (1,2,3,4,5):
        return '顺排'
    if step in (6,7,8,9):
        return '逆排'
    return '?'

# ── reply 提取 ───────────────────────────────────────────
VERDICT_KW = ['身亡','夭亡','夭折','死亡','去世','病死','病亡','入狱','坐牢','判刑','官至','升',
              '发贵','富贵','大富','富翁','亿万','巨富','贫贱','贫寒','婚变','离婚','二婚','克子',
              '无子','丧妻','克妻','克夫','丧夫','失明','眼疾','住院','车祸','残疾','僧','出家',
              '部级','处级','正团','科级','状元','北大','大学','学业有成','仕途','高官','当官',
              '升迁','提拔','发财','多病','怀才不遇','下岗','市长','副市','贵命','先富后贫',
              '克父','丧父','克母','丧母','破财','劳碌','寿短','暴落','暴起']

def extract_verdict(reply_text, case_no):
    """提取该例断事结果（v3：方法论·铁律归属段为主 + 断语回溯段 + 重点发现段）"""
    if not reply_text:
        return ''
    cn = str(case_no)
    # 1. 方法论段（主流格式 425 批）：- 946 描述：断语——**铁律**
    #    兼容：方法论·铁律归属段（标准格式）与 方法论增量段（有的行无冒号）
    ms_start = reply_text.find('方法论')
    if ms_start >= 0:
        ms_end = reply_text.find('【资产', ms_start)
        ms = reply_text[ms_start:ms_end if ms_end > 0 else ms_start + 3000]
        # 防跨行：本行内找冒号；断语取到 ——** 前（含中间口诀）；兼容 "例201" 前缀
        pat = re.compile(r'-\s*(?:例)?' + re.escape(cn) + r'(?!\d)[^：:\n]*[：:]\s*((?:(?!——\*\*)[^\n])*)')
        m = pat.search(ms)
        if m:
            # 方法论段定位到该例行：无论有无关键词都返回（权威段落，不 fallthrough）
            hits = [kw for kw in VERDICT_KW if kw in m.group(1)]
            return '；'.join(hits[:5])
        # 该行无冒号（如方法论增量段）：整行取
        pat2 = re.compile(r'-\s*(?:例)?' + re.escape(cn) + r'(?!\d)\s*((?:(?!——\*\*)[^\n])*)')
        m2 = pat2.search(ms)
        if m2:
            hits = [kw for kw in VERDICT_KW if kw in m2.group(1)]
            return '；'.join(hits[:5])
    # 2. 断语回溯段（16 批）：例XXX：... 
    seg_start = reply_text.find('断语回溯')
    if seg_start >= 0:
        seg_end = reply_text.find('【', seg_start + 4)
        seg = reply_text[seg_start:seg_end if seg_end > 0 else seg_start + 1500]
        pat_line = re.compile(r'(?:例)?' + re.escape(cn) + r'[：:]\s*([^\n]*)')
        m = pat_line.search(seg)
        if m:
            hits = [kw for kw in VERDICT_KW if kw in m.group(1)]
            if hits:
                return '；'.join(hits[:5])
        hits = [kw for kw in VERDICT_KW if kw in seg]
        if hits:
            return '；'.join(hits[:5])
    # 3. 重点发现段定位该例
    fd_start = reply_text.find('重点发现')
    if fd_start >= 0:
        fd_end = reply_text.find('【', fd_start + 4)
        fd = reply_text[fd_start:fd_end if fd_end > 0 else fd_start + 1000]
        m = re.search(re.escape(cn) + r'[^。\n]{0,60}', fd)
        if m:
            hits = [kw for kw in VERDICT_KW if kw in m.group(0)]
            if hits:
                return '；'.join(hits[:5])
    return ''

def extract_rhymes(reply_text):
    """口诀：诀言引号或'诀'字句"""
    rhymes = []
    if not reply_text:
        return rhymes
    for m in re.finditer(r'["“]([^"”]{4,60})["”]', reply_text):
        rhymes.append(m.group(1))
    # 也抓 '诀言' 后面的
    for m in re.finditer(r'诀言[：:]\s*([^，。\n]{4,60})', reply_text):
        if m.group(1) not in rhymes:
            rhymes.append(m.group(1))
    return rhymes[:10]

def extract_iron_laws(reply_text, rizhu, yueling):
    """铁律：仅方法论段内的 **...** 加粗句，排除排盘核验噪声"""
    laws = []
    if not reply_text:
        return laws
    ms_start = reply_text.find('方法论')
    if ms_start < 0:
        return laws
    ms_end = reply_text.find('【资产', ms_start)
    ms = reply_text[ms_start:ms_end if ms_end > 0 else ms_start + 3000]
    NOISE = ['⚠️', '例', '农历', '公历', '素材', '官方生日', '修正', '误传', '差1年', '存疑', '附会']
    for m in re.finditer(r'\*\*([^*]{8,120})\*\*', ms):
        text = m.group(1).strip()
        if any(kw in text for kw in NOISE):
            continue
        if text and text not in laws:
            laws.append(text)
    return laws[:10]

def extract_pattern_from_reply(reply_text):
    """reply 中的格局判定词"""
    hits = []
    for kw in ['从杀','从财','从儿','从势','化气','专旺','两神成像']:
        if kw in reply_text:
            hits.append(kw)
    return hits

# ── 主提取 ───────────────────────────────────────────────
def extract_case(batch_no, pc_case, content, reply_text, layer_map):
    """单例特征提取 → dict"""
    case_no = str(pc_case.get('case_no',''))
    raw_date = pc_case.get('raw_date','')
    solar = pc_case.get('solar','')
    pillars = pc_case.get('pillars_calc') or ''
    # 字段错位 fallback：pillars_calc 为空但 raw_date 像四柱（古例 OCR 错位，如 batch250 例47）
    pillar_pat = re.compile(r'^[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]\s+[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]\s+[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]\s+[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]$')
    if not pillars and pillar_pat.match(raw_date.strip()):
        pillars = raw_date.strip()
    if not pillars:
        pillars = pc_case.get('pillars_material','')
    p_list = [p for p in pillars.split() if re.match(r'^[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]$', p)]
    # 古例判定：无 solar 或 raw_date 为空
    is_ancient = 0 if (solar or raw_date) else 1
    gender = '?'
    if content:
        m = re.search(r'[乾坤]', content[:100])
        if m:
            gender = '乾' if m.group(0) == '乾' else '坤'
    layer = layer_map.get(case_no, 'C')
    flags = pc_case.get('flags', [])
    # 四柱
    year_p = p_list[0] if len(p_list) > 0 else ''
    month_p = p_list[1] if len(p_list) > 1 else ''
    day_p = p_list[2] if len(p_list) > 2 else ''
    hour_p = p_list[3] if len(p_list) > 3 else ''
    rizhu = day_p[:2] if len(day_p) >= 2 else ''
    yueling = month_p[1] if len(month_p) >= 2 else ''
    # 五行
    wx = calc_wuxing(p_list, yueling) if len(p_list) == 4 else None
    wx_standard = wx_conservative = wx_blind = '{}'
    wx_consensus = wx_sensitive = '[]'
    if wx:
        levels, cons, sens = wx
        wx_standard = json.dumps(levels['standard'], ensure_ascii=False)
        wx_conservative = json.dumps(levels['conservative'], ensure_ascii=False)
        wx_blind = json.dumps(levels['blind'], ensure_ascii=False)
        wx_consensus = json.dumps(cons, ensure_ascii=False)
        wx_sensitive = json.dumps(sens, ensure_ascii=False)
    # 格局/合冲
    zhis = [p[1] for p in p_list if len(p) >= 2]
    gans = [p[0] for p in p_list if len(p) >= 2]
    sw = detect_patterns(zhis, reply_text, gans)
    he, chong, hui, xing = detect_hechong(zhis)
    # 十神（透干）—— **老尺留档，勿擅改**：
    # 本循环含日柱，故 `shishen(day_gan, day_gan)` 恒记一枚「比肩」⇒ 本列
    # `shishen_config` 的比肩 = 真比肩 + 1（全库每例比肩 ≥1，无 0 组）。
    # 这是本库 **平台的原始口径**（日主计入十神），作历史证据保留。
    # 已排除日主的正确读数在 `shishen_quan` / `shishen_tiangan`（ruler_ver=2，
    # 见 fix_shishen_root.py）。**新分析一律用后者，勿再用本列比肩。**
    # 十神（透干）
    ss = Counter()
    if day_p:
        for p in p_list:
            if p:
                ss[shishen(day_p[0], p[0])] += 1
    ss_json = json.dumps({k: ss.get(k, 0) for k in SHISHEN_NAMES}, ensure_ascii=False)
    # 字频
    tg = Counter(p[0] for p in p_list if p)
    dz = Counter(p[1] for p in p_list if p)
    tg_json = json.dumps({g: tg.get(g, 0) for g in GAN}, ensure_ascii=False)
    dz_json = json.dumps({z: dz.get(z, 0) for z in ZHI}, ensure_ascii=False)
    # 大运
    direction, age, first_dayun, seq = parse_dayun(pc_case.get('dayun',''))
    if direction == '?':
        direction = infer_direction(month_p, first_dayun)
    # reply 提取
    verdict = extract_verdict(reply_text, case_no)
    rhymes = extract_rhymes(reply_text)
    laws = extract_iron_laws(reply_text, rizhu, yueling)
    return {
        'batch_no': batch_no, 'case_no': case_no, 'bu': '', 'rizhu': rizhu, 'yueling': yueling,
        'year_pillar': year_p, 'month_pillar': month_p, 'day_pillar': day_p, 'hour_pillar': hour_p,
        'gender': gender,
        'wx_standard': wx_standard, 'wx_conservative': wx_conservative, 'wx_blind': wx_blind,
        'wx_consensus': wx_consensus, 'wx_sensitive': wx_sensitive,
        'pattern_switches': json.dumps(sw, ensure_ascii=False),
        'he_list': json.dumps(he, ensure_ascii=False), 'chong_list': json.dumps(chong, ensure_ascii=False),
        'hui_list': json.dumps(hui, ensure_ascii=False), 'xing_list': json.dumps(xing, ensure_ascii=False),
        'shishen_config': ss_json,
        'tian_gan_freq': tg_json, 'di_zhi_freq': dz_json,
        'dayun_direction': direction, 'qiyun_age': age, 'first_dayun': first_dayun,
        'dayun_sequence': seq,
        'verdict': verdict,
        'layer': layer, 'flags': json.dumps(flags, ensure_ascii=False),
        'is_ancient': is_ancient, 'has_date': 0 if is_ancient else 1,
        'rhyme_refs': json.dumps(rhymes, ensure_ascii=False),
        'iron_law_ids': json.dumps([], ensure_ascii=False),
        'pattern_map_ref': '',
    }

def upsert_case(conn, c):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO case_features (
            batch_no, case_no, bu, rizhu, yueling, year_pillar, month_pillar, day_pillar, hour_pillar,
            gender, wx_standard, wx_conservative, wx_blind, wx_consensus, wx_sensitive,
            pattern_switches, he_list, chong_list, hui_list, xing_list, shishen_config,
            tian_gan_freq, di_zhi_freq, dayun_direction, qiyun_age, first_dayun, dayun_sequence,
            verdict, layer, flags, is_ancient, has_date, rhyme_refs, iron_law_ids, pattern_map_ref
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(batch_no, case_no) DO UPDATE SET
            rizhu=excluded.rizhu, yueling=excluded.yueling,
            year_pillar=excluded.year_pillar, month_pillar=excluded.month_pillar,
            day_pillar=excluded.day_pillar, hour_pillar=excluded.hour_pillar,
            gender=excluded.gender, wx_standard=excluded.wx_standard,
            wx_conservative=excluded.wx_conservative, wx_blind=excluded.wx_blind,
            wx_consensus=excluded.wx_consensus, wx_sensitive=excluded.wx_sensitive,
            pattern_switches=excluded.pattern_switches, he_list=excluded.he_list,
            chong_list=excluded.chong_list, hui_list=excluded.hui_list, xing_list=excluded.xing_list,
            shishen_config=excluded.shishen_config, tian_gan_freq=excluded.tian_gan_freq,
            di_zhi_freq=excluded.di_zhi_freq, dayun_direction=excluded.dayun_direction,
            qiyun_age=excluded.qiyun_age, first_dayun=excluded.first_dayun,
            dayun_sequence=excluded.dayun_sequence, verdict=excluded.verdict,
            layer=excluded.layer, flags=excluded.flags, is_ancient=excluded.is_ancient,
            has_date=excluded.has_date, rhyme_refs=excluded.rhyme_refs,
            iron_law_ids=excluded.iron_law_ids, pattern_map_ref=excluded.pattern_map_ref
    """, (
        c['batch_no'], c['case_no'], c['bu'], c['rizhu'], c['yueling'],
        c['year_pillar'], c['month_pillar'], c['day_pillar'], c['hour_pillar'],
        c['gender'], c['wx_standard'], c['wx_conservative'], c['wx_blind'],
        c['wx_consensus'], c['wx_sensitive'], c['pattern_switches'], c['he_list'],
        c['chong_list'], c['hui_list'], c['xing_list'], c['shishen_config'],
        c['tian_gan_freq'], c['di_zhi_freq'], c['dayun_direction'], c['qiyun_age'],
        c['first_dayun'], c['dayun_sequence'], c['verdict'], c['layer'], c['flags'],
        c['is_ancient'], c['has_date'], c['rhyme_refs'], c['iron_law_ids'],
        c['pattern_map_ref']
    ))

def upsert_law(conn, law_id, rizhu, yueling, law_text, source_batch, support_case):
    """铁律 UPSERT：幂等，同 law_id 只更新支持计数"""
    cur = conn.cursor()
    exists = cur.execute("SELECT law_id, support_case_ids FROM iron_laws WHERE law_id=?", (law_id,)).fetchone()
    if exists:
        ids = json.loads(exists[1])
        if support_case not in ids:
            ids.append(support_case)
        cur.execute("""
            UPDATE iron_laws SET support_count=?, support_case_ids=?, updated_at=datetime('now')
            WHERE law_id=?
        """, (len(ids), json.dumps(ids, ensure_ascii=False), law_id))
    else:
        cur.execute("""
            INSERT INTO iron_laws (law_id, rizhu, yueling, law_text, law_summary, confidence,
                                   support_count, support_case_ids, mechanism_path, source_batch)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (law_id, rizhu, yueling, law_text, law_text, 'BRONZE', 1,
              json.dumps([support_case], ensure_ascii=False), '', source_batch))

def main():
    global DB_CONN
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    only_batch = None
    for a in args:
        if a.startswith('--batch'):
            only_batch = int(args[args.index(a)+1])
    DB_CONN = sqlite3.connect(DB)
    cur = DB_CONN.cursor()
    # 读取批次（precompute 非空）
    q = "SELECT batch_no, precompute, content, reply, layer FROM batches WHERE precompute IS NOT NULL AND precompute != ''"
    if only_batch:
        q += f" AND batch_no={only_batch}"
    rows = cur.execute(q).fetchall()
    total_cases, total_batches, errors = 0, 0, []
    for batch_no, precompute, content, reply, layer_json in rows:
        try:
            pc = json.loads(precompute)
            cases = pc.get('cases', [])
        except Exception as e:
            errors.append(f'batch{batch_no}: precompute 解析失败 {e}')
            continue
        layer_map = {}
        if layer_json:
            try:
                layer_map = json.loads(layer_json)
            except Exception:
                pass
        n = 0
        # 批次主日主/月令（铁律归属用）
        batch_rz, batch_yl = '', ''
        for pc_case in cases:
            try:
                c = extract_case(batch_no, pc_case, content or '', reply or '', layer_map)
                if not batch_rz:
                    batch_rz, batch_yl = c['rizhu'], c['yueling']
                if dry_run:
                    total_cases += 1
                    n += 1
                    continue
                upsert_case(DB_CONN, c)
                total_cases += 1
                n += 1
            except Exception as e:
                errors.append(f'batch{batch_no} 例{pc_case.get("case_no","?")}: {e}')
        # 铁律提取 → iron_laws（BRONZE 起步，置信度引擎后续升级）
        if not dry_run and reply and batch_rz:
            laws = extract_iron_laws(reply, batch_rz, batch_yl)
            law_counter = cur.execute(
                "SELECT COUNT(*) FROM iron_laws WHERE rizhu=? AND yueling=?", (batch_rz, batch_yl)
            ).fetchone()[0]
            for lt in laws:
                law_counter += 1
                law_id = f'R-{batch_rz}{batch_yl}-{law_counter:03d}'
                support = f'{batch_no}-{cases[0].get("case_no","?")}' if cases else str(batch_no)
                upsert_law(DB_CONN, law_id, batch_rz, batch_yl, lt, batch_no, support)
        if not dry_run and n > 0:
            DB_CONN.commit()
        total_batches += 1
    if dry_run:
        print(f'[dry-run] 扫描批次 {total_batches}，可提取案例 {total_cases}，错误 {len(errors)}')
    else:
        # 写提取日志（供审计/增量核对）
        cur.execute("""
            INSERT INTO feature_extract_log (batch_no, cases_extracted, new_iron_laws, upgraded_laws, errors)
            VALUES (?,?,0,0,?)
        """, (only_batch or -1, total_cases, json.dumps(errors[:50], ensure_ascii=False)))
        DB_CONN.commit()
        print(f'[done] 批次 {total_batches}，案例 {total_cases}，错误 {len(errors)}')
    for e in errors[:20]:
        print('  ERR:', e)
    DB_CONN.close()

if __name__ == '__main__':
    main()
