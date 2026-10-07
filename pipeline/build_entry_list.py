#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压缩法 · 条目清单生成器
把四源（子平真诠系 / 巾箱 / 道秀 / 案例库）蒸馏成「可检验条目清单」。
产物：distill/entry-list.md（人读）+ distill/entries.json（机器读）

纪律（用户 2026-10-07 拍板：方法2 + 三道闸）：
  闸一 归组 —— 真正参与校正的是「轴」数，不是条目数
  闸二 两段 —— 一半发现（宽进）/ 一半确认（严出），确认不过不进「敢说清单」
  闸三 未蒸清单 —— 落不进「条件+方向+机制」三格的，登记在册，不偷丢

每条 = 编号 · 轴 · 条件(可算字段) · 方向(事类) · 机制 · 边界 · 出处 · 状态
强度一栏留空，待上机（预注册：先写下来才算数）
"""
import json, os

# 库当前可算字段（条件必须落在这里面，否则进未蒸清单）
FIELDS = [
    "rizhu 日柱", "yueling 月令", "四柱", "gender",
    "shishen_quan 8字十神", "shishen_benqi 本气十神", "shishen_config 天干十神(旧)",
    "tonggen 通根", "he_list 合", "chong_list 冲", "hui_list 会", "xing_list 刑",
    "wx_standard/conservative/blind/consensus 五行旺衰",
    "dayun_sequence 大运", "qiyun_age 起运", "pattern_switches 格局开关",
]
# 结局域（case_outcomes / case_features.verdict_domains）
DOMAINS = ["财(521)", "婚姻(297)", "寿元(212)", "功名(176)", "刑灾官非(~60)", "六亲(~64)"]

AXES = [
    ("AX-01", "十神单字轴", "某十神在指定口径(8字/本气/天干)的个数", "对应事类"),
    ("AX-02", "格局成破轴", "两个十神共现(成格/破格组合)", "功名/财/刑灾/婚姻"),
    ("AX-03", "强弱根气轴", "身强弱 + 有无支根 + 个数梯度", "全体事类"),
    ("AX-04", "宫位轴", "某十神落在年/月/日/时哪一柱", "六亲/事业/婚姻"),
    ("AX-05", "夫妻宫轴", "日支被合/冲/刑", "婚姻"),
    ("AX-06", "五行配置轴", "五行个数/缺失/偏枯", "寿元/性情/财"),
    ("AX-07", "墓库轴", "有无辰戌丑未 + 何五行入墓", "刑灾/事业持续性"),
    ("AX-08", "调候轴", "月令季节 × 日主 × 寒暖燥湿", "层次/健康"),
    ("AX-09", "女命夫星轴", "官杀显隐/混杂/根气", "婚姻"),
    ("AX-10", "岁运应期轴", "大运/流年与原局字的关系(填实/冲/合)", "应期(限 case_events 子集)"),
    ("AX-11", "财富载体轴", "财挂哪个载体(财<食伤<官殺/禄)", "财/功名"),
]

# status: ok=已测有结果 / half=已测未过线 / wait=待测
E = [
 # --- AX-01 十神单字轴 ---
 dict(id="AX01-01", axis="AX-01", name="偏财≥1 → 财等级↑",
      cond="shishen_quan 中偏财个数 ≥1（8字口径）", dir="财域等级↑",
      mech="偏财主外财/他人财，财为养命之源，有源可承接", bnd="同轴正财≥1 应无此效（阴性对照）",
      src="巾箱+道秀(财富载体)", status="ok", res="唯一跨源存活：回复层z=+2.58 / 素材层z=+2.98；梯度 0→3档 1.42→1.74→2.01→2.20，首末 z=+3.30 单调"),
 dict(id="AX01-02", axis="AX-01", name="正财≥1 → 财等级（阴性对照）",
      cond="shishen_quan 中正财个数 ≥1", dir="财域等级（预期无效应）",
      mech="正财为妻财/正当收入，与偏财同财性但来源不同", bnd="若与偏财同效 ⇒ 说明只是「财多」代理，偏财不特异",
      src="阴性对照设计", status="ok", res="全平：8字+0.16 / 本气−0.16 / 天干−0.16"),
 dict(id="AX01-03", axis="AX-01", name="劫财(天干)≥1 → 财等级↓",
      cond="shishen_config 天干十神中含劫财", dir="财域等级↓",
      mech="劫财夺财，财被分走", bnd="换8字口径后≈0 ⇒ 上轮-2.27 疑为分档抖动",
      src="子平真诠(比劫夺财)", status="half", res="回复层−2.27 → 换测量−1.23，未复现，降待观察"),
 dict(id="AX01-04", axis="AX-01", name="劫财(8字)≥1 → 财等级↓",
      cond="shishen_quan 中劫财个数 ≥1", dir="财域等级↓",
      mech="同上", bnd="8字口径下应为负；实测≈0 则本条无效应",
      src="子平真诠", status="ok", res="≈0：−0.43/+0.64，判无效应"),
 dict(id="AX01-05", axis="AX-01", name="比肩(8字)≥1 → 财等级↓",
      cond="shishen_quan 中比肩个数 ≥1", dir="财域等级↓",
      mech="比肩同类夺财，但比劫财轻", bnd="若比肩负、偏财正 ⇒ 符号自洽（夺财者负/财源者正）",
      src="子平真诠", status="half", res="三口径皆负：−2.10/−1.87/−0.82，方向对，未过线"),
 dict(id="AX01-06", axis="AX-01", name="正官≥1 → 功名等级↑",
      cond="shishen_quan 中正官个数 ≥1", dir="功名域等级↑",
      mech="官为贵气，功名之标；官清则贵", bnd="官个数≥3 转「浊」应反向（见 AX03-02）",
      src="子平真诠(正官格)", status="wait", res=""),
 dict(id="AX01-07", axis="AX-01", name="七杀≥1 → 刑灾↑ / 功名↑（双路）",
      cond="shishen_quan 中七杀个数 ≥1", dir="刑灾官非↑；有制则功名↑",
      mech="杀为凶神，有制则权、无制则祸", bnd="必须分「有制/无制」两臂，混测必平",
      src="道秀(七杀无制非贫则夭)", status="half", res="有制组窄口径 z=+2.06；根气三档 44.8/48.4/40.2 未定"),
 dict(id="AX01-08", axis="AX-01", name="伤官≥1 → 婚姻↓（女命）",
      cond="坤造 ∧ shishen_quan 中伤官 ≥1", dir="婚姻域↓",
      mech="伤官克官，官=夫星 ⇒ 克夫", bnd="须带财/印通关条件切分；坤造池 586 例（2026-10-07 修）",
      src="子平真诠+巾箱(伤官见官)", status="half", res="干净池全平（n=28/73，L·A 两半反向 −2.04/+0.77）；旧 +14.6% 作废"),
 dict(id="AX01-09", axis="AX-01", name="食神≥1 → 寿元↑",
      cond="shishen_quan 中食神个数 ≥1", dir="寿元域↑",
      mech="食神为寿神/食禄；食神不被夺则寿", bnd="须排除枭神夺食臂（AX01-10）",
      src="道秀(食神=寿神)", status="wait", res=""),
 dict(id="AX01-10", axis="AX-01", name="枭神(偏印)≥1 → 寿元↓/财↓",
      cond="shishen_quan 中偏印 ≥1 ∧ 食神 ≥1", dir="寿元↓",
      mech="枭神夺食，食=寿神兼财源", bnd="无食可夺则本条不适用",
      src="道秀(枭神夺食应事谱)", status="wait", res=""),

 # --- AX-02 格局成破轴 ---
 dict(id="AX02-01", axis="AX-02", name="官印相生 → 凶率↓",
      cond="正官≥1 ∧ 印星≥1（8字口径）", dir="刑灾/整体凶率↓",
      mech="印护官，官不受伤；印为避凶之神", bnd="命中率86.9% 太高 ⇒ 需再叠「官有根且印透干」才有压缩力",
      src="子平真诠(正官格三顺用)", status="half", res="B档：52.6%(n=116) vs 34.3%(n=67)，超额+18.3pp，z=2.39；换测量后未过线"),
 dict(id="AX02-02", axis="AX-02", name="杀印相生 → 功名↑",
      cond="七杀≥1 ∧ 印≥1", dir="功名域↑",
      mech="杀不离印、印不离杀；印化杀为权", bnd="⚠口径换向实测 +1.01 → −1.51 ⇒ 结论必须绑口径",
      src="子平真诠+道秀", status="wait", res="口径换向警告"),
 dict(id="AX02-03", axis="AX-02", name="伤官见官 → 刑灾↑/婚姻↓",
      cond="伤官≥1 ∧ 正官≥1", dir="刑灾官非↑；女命婚姻↓",
      mech="伤官克官 ⇒ 诉讼/疾病「两院之灾」", bnd="须分「谁强谁弱、有无财印通关」；不切分必平",
      src="巾箱+道秀", status="half", res="干净池全平；旧「坤造池 +14.6%」系脏性别列造的假信号，已作废"),
 dict(id="AX02-04", axis="AX-02", name="比劫夺财 → 财↓",
      cond="比劫≥2 ∧ 财≥1", dir="财域↓",
      mech="比劫夺财", bnd="命中率92.1% ⇒ 条件人人满足，压不动",
      src="子平真诠", status="ok", res="压不动（命中92.1%，无区分力）；比肩计数修正后仍平"),
 dict(id="AX02-05", axis="AX-02", name="食神制杀 → 刑灾↓",
      cond="食神≥1 ∧ 七杀≥1", dir="刑灾官非↓",
      mech="食神制杀，杀被制则不为祸", bnd="制杀太过则转「不宜当官」（AX02-08）",
      src="道秀(制杀太过)", status="wait", res=""),
 dict(id="AX02-06", axis="AX-02", name="财生官 → 功名↑",
      cond="财≥1 ∧ 正官≥1", dir="功名域↑",
      mech="财是官的源神，持续生官", bnd="命中率可能过高，需叠根气",
      src="道秀(正官格用印不如用财)", status="wait", res=""),
 dict(id="AX02-07", axis="AX-02", name="官杀混杂 → 婚姻↓/功名↓",
      cond="正官≥1 ∧ 七杀≥1", dir="婚姻↓、功名等级↓",
      mech="官杀混杂为「浊」，无清纯之气", bnd="唯一解=用印；无印则破裂",
      src="道秀(官杀混杂唯一解=用印)", status="wait", res="坤造池单独测：+1.0% 未复现"),
 dict(id="AX02-08", axis="AX-02", name="制杀太过 → 不宜当官",
      cond="七杀≥1 ∧ 食伤≥2 ∧ 印=0", dir="功名↓（体制内待不久）",
      mech="杀被制尽 ⇒ 无压制之物 ⇒ 反不受管", bnd="再走食伤运即应凶",
      src="道秀", status="wait", res=""),

 # --- AX-03 强弱根气轴 ---
 dict(id="AX03-01", axis="AX-03", name="七杀有支根 vs 无支根 → 刑灾",
      cond="七杀≥1 ∧ 分「tonggen 有根 / 无根」两臂", dir="刑灾官非",
      mech="有根之杀力实，无根之杀虚而不为祸", bnd="样本三档均 <100，红线高",
      src="道秀", status="half", res="有支根48.4% / 无支根40.2% / 天干有44.8%，方向未定"),
 dict(id="AX03-02", axis="AX-03", name="官星个数 1→4 梯度 → 功名（官多不贵）",
      cond="shishen_quan 中官殺个数 1/2/3/4", dir="功名域等级 单调↓",
      mech="官多为杀，浊而不清；宜一透一藏", bnd="官殺≥5 样本仅 n=2，须删",
      src="子平真诠+道秀v4改判", status="half", res="61.6/50.5/52.2/47.1，非严格单调（2<3），方向成立"),
 dict(id="AX03-03", axis="AX-03", name="身弱(无根无印) → 刑灾↑/寿元↓",
      cond="日主无支根 ∧ 印=0", dir="刑灾↑、寿元↓",
      mech="身弱不胜财官，受克无救", bnd="须先定「旺衰口径」四版并存（standard/conservative/blind/consensus）",
      src="子平真诠", status="wait", res=""),
 dict(id="AX03-04", axis="AX-03", name="财多身弱 → 财↓",
      cond="财≥3 ∧ 日主无根无印", dir="财域等级↓",
      mech="财多身弱，财为身累（富屋贫人）", bnd="与 AX01-01（偏财正效应）冲突臂，须并排测",
      src="子平真诠", status="wait", res=""),
 dict(id="AX03-05", axis="AX-03", name="□口径效应：通根>本气>天干",
      cond="同一十神换三种口径（天干/本气/8字）", dir="致效强度递增",
      mech="地支藏干亦有力，只数天干漏掉大半力量", bnd="——这是「尺子」而非「理论」，是所有条目的前置",
      src="《千里命稿》韦千里「当以干支并看」", status="ok", res="偏财：天干+0.82 / 本气+2.14 / 8字+3.30，单调递增，故立8字为主尺"),

 # --- AX-04 宫位轴 ---
 dict(id="AX04-01", axis="AX-04", name="官星在年月(高位) → 功名量级大",
      cond="正官/七杀 落年柱或月柱", dir="功名等级↑",
      mech="年月=外、高位 ⇒ 管的面大", bnd="与「主位易得难夺」冲突，须并测",
      src="道秀(取富贵位置论)", status="wait", res=""),
 dict(id="AX04-02", axis="AX-04", name="七杀在主位(日时) → 不用则凶",
      cond="七杀 落日柱或时柱", dir="用之转功名，不用则伤病压制",
      mech="主位七杀近身，必须有用（制/化/合）", bnd="须定义「用」的操作化判据",
      src="道秀", status="wait", res=""),
 dict(id="AX04-03", axis="AX-04", name="财在年月 vs 日时 → 财量级/易得度",
      cond="财 落年月臂 vs 落日时臂", dir="财域等级 + 得财难易",
      mech="高位财上限高但竞争烈；主位财易得但上限低", bnd="——",
      src="道秀", status="wait", res=""),
 dict(id="AX04-04", axis="AX-04", name="伤官在时柱(子女宫) → 子女↓",
      cond="伤官 落时柱 ∧ 坤造", dir="六亲(子女)↓",
      mech="时柱=子女宫，伤官泄身；女命食伤为子女星", bnd="须按女命食伤(非伤官)重测",
      src="道秀(子女星)", status="wait", res=""),

 # --- AX-05 夫妻宫轴 ---
 dict(id="AX05-01", axis="AX-05", name="日支被冲 → 婚姻↓",
      cond="chong_list 含日支", dir="婚姻域↓",
      mech="夫妻宫被动摇 ⇒ 婚变", bnd="须分「冲入/冲出」；婚姻域 297 例可测",
      src="道秀+盲派", status="wait", res="本轴为核心待测项"),
 dict(id="AX05-02", axis="AX-05", name="日支被合 → 婚姻变（合走↓ / 合入↑）",
      cond="he_list 含日支", dir="婚姻域双向",
      mech="合走=配偶被合去；合入=配偶进我家", bnd="★合走合入必须分臂，混测必平（断命活法铁律）",
      src="bazi-live-duanming(合走vs合入)", status="wait", res=""),
 dict(id="AX05-03", axis="AX-05", name="日支自刑 → 婚姻↓",
      cond="xing_list 含日支自刑(辰辰/午午/酉酉/亥亥)", dir="婚姻域↓",
      mech="自刑=自我内耗，夫妻宫自伤", bnd="样本少（自刑本就稀有）",
      src="巾箱+实盘先例（同事双辰自刑）", status="wait", res=""),
 dict(id="AX05-04", axis="AX-05", name="夫妻宫逢空亡 → 缘浅",
      cond="日支落空亡", dir="婚姻域↓",
      mech="空=减力，宫位空则缘薄", bnd="⚠库无空亡字段 ⇒ 见未蒸清单（需先造字段）",
      src="道秀", status="wait", res=""),

 # --- AX-06 五行配置轴 ---
 dict(id="AX06-01", axis="AX-06", name="缺任一五行 → 偏枯",
      cond="五行缺失（逐一 5 臂）", dir="吉凶率偏离基线",
      mech="缺五行=偏枯，主人生有缺憾", bnd="——",
      src="道秀(缺字未必显象)", status="ok", res="无效应：5 个 z 全在 ±1.6 内"),
 dict(id="AX06-02", axis="AX-06", name="五行极偏(某行≥4) → 刑灾/寿元↓",
      cond="wx_consensus 中某一行 ≥4", dir="刑灾↑、寿元↓",
      mech="一气独旺无制则偏，偏则折", bnd="需定「旺衰口径」（四版并存）",
      src="子平真诠", status="wait", res=""),
 dict(id="AX06-03", axis="AX-06", name="水多火弱 → 上热下寒（健康）",
      cond="水≥3 ∧ 火≤1", dir="健康（需健康域）",
      mech="火主心血、水主寒湿；火弱则阳不达下", bnd="⚠库无健康域 ⇒ 见未蒸清单",
      src="实盘(振朝原局)", status="wait", res=""),

 # --- AX-07 墓库轴 ---
 dict(id="AX07-01", axis="AX-07", name="有墓库(辰戌丑未) → 事业持续性",
      cond="四柱含辰/戌/丑/未", dir="功名域等级（持续 vs 空档）",
      mech="官杀库=持续建立功勋的机会", bnd="库为哪一五行决定功能，不可只看有无",
      src="道秀(墓库能量等级跃升)", status="wait", res=""),
 dict(id="AX07-02", axis="AX-07", name="旺神入墓 → 刑灾↑",
      cond="日主五行 ≥2 ∧ 四柱有该五行之墓", dir="刑灾↑",
      mech="旺神入库主凶", bnd="须先定「墓」的算法（辰=水墓等），库无现成字段",
      src="道秀(旺神入墓是凶象)", status="wait", res=""),

 # --- AX-08 调候轴 ---
 dict(id="AX08-01", axis="AX-08", name="冬生火日主无火 → 层次↓",
      cond="月令∈亥子丑 ∧ 日主为丙/丁 ∧ 火=0", dir="功名域等级↓",
      mech="寒木/寒火无调候，格局难成", bnd="范围小（冬生火日主），样本可能不足",
      src="子平真诠(论用神配气候)", status="wait", res=""),
 dict(id="AX08-02", axis="AX-08", name="夏生水日主无水 → 层次↓",
      cond="月令∈巳午未 ∧ 日主为壬/癸 ∧ 水=0", dir="功名域等级↓",
      mech="燥土涸水，调候失宜", bnd="同上",
      src="子平真诠", status="wait", res=""),
 dict(id="AX08-03", axis="AX-08", name="木火通明(春生甲木+丙火透) → 富贵",
      cond="月令=寅 ∧ 日柱=甲子 ∧ 天干透丙", dir="功名域等级↑",
      mech="寒木向阳，泄秀生财，木火通明格", bnd="巾箱单格诀，n≈3 ⇒ 只能当 C 档参照（见未蒸清单）",
      src="巾箱(甲子日元寅月)", status="wait", res=""),

 # --- AX-09 女命夫星轴（坤造 586；性别列 2026-10-07 判病并修复，旧列把每批第一例性别盖全批）---
 dict(id="AX09-01", axis="AX-09", name="夫星透干无根 → 婚姻↓",
      cond="坤造 ∧ 官杀仅在天干 ∧ 无支根", dir="婚姻域↓",
      mech="夫星虚浮无根 ⇒ 夫缘不实", bnd="——",
      src="坤造池回调", status="half", res="干净池全平（旧 −3.9% 系脏性别列所致；n=28/73）"),
 dict(id="AX09-02", axis="AX-09", name="官杀混杂 → 婚姻↓",
      cond="坤造 ∧ 正官≥1 ∧ 七杀≥1", dir="婚姻域↓",
      mech="夫星不专，情感难专", bnd="——",
      src="坤造池回调", status="half", res="干净池全平（旧 +1.0%）"),
 dict(id="AX09-03", axis="AX-09", name="身弱 → 婚姻↓",
      cond="坤造 ∧ 日主无根无印", dir="婚姻域↓",
      mech="身弱难任夫星", bnd="——",
      src="坤造池回调", status="half", res="干净池仍无变异：条件（比劫=0 ∧ 印=0）极窄，全库几无命中"),
 dict(id="AX09-04", axis="AX-09", name="伤官见官 → 婚姻↓  ★",
      cond="坤造 ∧ 伤官≥1 ∧ 正官≥1", dir="婚姻域↓",
      mech="伤官克夫星", bnd="干净池已测：平；旧结论作废",
      src="坤造池回调", status="half", res="★破：干净池全平；旧「+14.6%／G·B +2.12」系脏性别池造的假信号"),
 dict(id="AX09-05", axis="AX-09", name="夫星不显(无官杀) → 婚姻↓/晚婚",
      cond="坤造 ∧ 官殺个数=0", dir="婚姻域（婚否/婚龄）",
      mech="无夫星则夫缘迟或改以财/比劫论夫", bnd="现代派有「以财为夫」变体，须并测",
      src="bazi-live-duanming(夫星选有根)", status="half", res="干净池全平"),

 # --- AX-10 岁运应期轴（限 case_events 212 例）---
 dict(id="AX10-01", axis="AX-10", name="大运出现原局忌字 → 该运应凶",
      cond="dayun_sequence 含「原局无而忌」之字", dir="事件应期（凶）",
      mech="结构被扰动 ⇒ 立即应灾，不给缓冲", bnd="须先定义「忌字」的可算判据（依赖 AX-02/03 结论）",
      src="道秀(忌字清单)", status="wait", res="依赖前置轴，排最后"),
 dict(id="AX10-02", axis="AX-10", name="大运冲原局=灰犀牛 / 流年冲大运=黑天鹅",
      cond="chong_list 在 大运×原局 与 流年×大运 两个位置", dir="事件类型（旧事 vs 新事）",
      mech="运冲命=旧有病灶被掀；年冲运=新变量入场", bnd="须流年数据 ⇒ 仅 case_events 子集可测",
      src="道秀", status="wait", res=""),
 dict(id="AX10-03", axis="AX-10", name="岁运填实(原局有字再现) → 触发",
      cond="原局字 ∩ 岁运字 ≠ ∅", dir="应期",
      mech="干填干、支填支 ⇒ 该字凶象被触发", bnd="同上",
      src="道秀", status="wait", res=""),

 # --- AX-11 财富载体轴 ---
 dict(id="AX11-01", axis="AX-11", name="财富载体等级 财<食伤<官殺/禄",
      cond="辨「财/食伤/官殺禄」哪一组承载", dir="财域等级↑",
      mech="载体越高，量级越大；不看几个财，看挂哪个载体", bnd="载体判定需人工/规则，库无现成字段",
      src="道秀", status="half", res="方向支持：官殺印组62.2%(n=127) vs 财组53.8%(n=93)，+7.5%，z=1.69 未过线"),
]

UNSTEAMED = [
 ("空亡类", "库无空亡字段（日支/夫星空亡等）", "先造字段，再入 AX-05/AX-09"),
 ("神煞类", "库无神煞字段（亡神/贵人/羊刃按神煞口径）", "道秀有 6+ 条神煞判据，需造字段"),
 ("象法/职业取象", "职业以自由文本存在，未结构化（土主信+官杀=信贷 等）", "需职业文本抽取，属另一条工程线"),
 ("健康域", "库无健康结局域（水多火弱→上热下寒 等）", "实盘专用，库内无对应结局"),
 ("巾箱 1817 条单格诀", "域锁死「日柱×月令」，每格 n≈3，统计层无解", "只当 C 档参照，不进统计层（体例天花板）"),
 ("基外成分（风水/时代/选择/关系）", "不在四柱可算范围内", "按 first-principles §5：模糊出在「认不全」，须承认此限"),
]


def load_scores(here):
    """从 score-splithalf.txt 读「机器状态」——状态的真源是打分器，不是手写。
    理由：手写状态曾僵住 20 条（跑了却没回写），而条目册是「敢说清单」的底账，
    底账一旦和实测脱钩就不可信。手写字段降级为「备注」，保留追溯。"""
    import re
    p = os.path.join(here, "score-splithalf.txt")
    if not os.path.exists(p):
        return set(), [], set(), {}, set()
    NUM, AGREE, CROSS, ROWS, REG = set(), [], set(), {}, set()
    sec = ""
    for ln in open(p, encoding="utf-8"):
        s = ln.rstrip("\n")
        if s.startswith("=="):
            sec = s.strip("= ").split("（")[0]
            continue
        if sec == "两源都进上表":
            for part in s.strip().split(","):
                part = part.strip()
                if "·" in part:
                    e, o = part.split("·"); CROSS.add((e.strip(), o.strip()))
            continue
        if sec.startswith("两半一致"):
            m = re.match(r"^\s*([-+\d.]+)\s+(\S+)\s+(\S+)\s+([LSXG])\s+([ABT])", s)
            if m:
                AGREE.append((float(m.group(1)), m.group(2), m.group(4), m.group(5)))
            continue
        m = re.match(r"^(\S+)\s+(\S+)\s+([LSXG])\s+([ABT])\s+(\d+)\s+([-+\d.]+)\s+([-+\d.]+)\s+(\S+)\s*(.*)$", s)
        if m:
            REG.add(m.group(1))
            NUM.add(m.group(1))
            ROWS.setdefault(m.group(1), []).append(
                (m.group(3), m.group(4), int(m.group(5)), float(m.group(6)), float(m.group(7)),
                 m.group(8), m.group(9)))
            continue
        m = re.match(r"^(\S+)\s+(\S+)\s+([LSXG])\s+([ABT])\s+(\d+)\s+\S+\s+\S+\s+(\S+)\s*(.*)$", s)
        if m:   # 无数字行（样本不足／无变异）也要登记：否则该类条目被误判成「没进打分器」
            REG.add(m.group(1))
            ROWS.setdefault(m.group(1), []).append(
                (m.group(3), m.group(4), int(m.group(5)), None, None, m.group(6), m.group(7)))
    return NUM, AGREE, CROSS, ROWS, REG


def mstat(eid, NUM, AGREE, CROSS, ROWS, REG):
    """机器状态：ok=跨源×跨半 / half=仅两半 / flat=已测无信号 / stuck=测不动 / none=未进打分器。"""
    a = [x for x in AGREE if x[1] == eid]
    if a and any((eid, x[2]) in CROSS for x in a):
        top = max(a)
        return "ok", f"跨源复现（{top[2]}·{top[3]}）最强半 {top[0]:+.2f}"
    if a:
        top = max(a)
        bad = [r for r in ROWS.get(eid, []) if r[5] != "OK"]
        extra = "；最强出口不健康" if bad else ""
        if top[2] == "G":
            extra += "；G 是代理出口（不是靶域）"
        return "half", f"两半一致（{top[2]}·{top[3]}）最强半 {top[0]:+.2f}{extra}"
    if eid in NUM:
        return "flat", "已测、无信号（全平）"
    if eid in REG:
        return "stuck", "测不动（结局/预测子无变异，或 n 不足）"
    return "none", "未进打分器（未注册／已列「跳过」）"


def main():
    os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
    here = os.path.dirname(os.path.abspath(__file__))

    # 机器版
    payload = dict(
        version="1.0",
        built="2026-10-07",
        protocol=dict(
            gate1="归组：校正按「轴」数计（11 轴），组内细条目当稳健性变体",
            gate2="两段：半库发现（宽进）/ 半库确认（严出），确认不过不进「敢说清单」",
            gate3="未蒸清单：落不进三格者登记在册，不偷丢",
        ),
        fields=FIELDS, domains=DOMAINS,
        axes=[dict(id=a, name=n, cond=c, domain=d) for a, n, c, d in AXES],
        entries=E,
        unsteamed=[dict(name=n, why=w, next=x) for n, w, x in UNSTEAMED],
    )
    with open(os.path.join(here, "entries.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    # 人读版
    L = []
    L.append("# 压缩法 · 条目清单（蒸馏产物 v1.0）\n")
    L.append("> 生成：`distill/build_entry_list.py` ｜ 预注册日期 2026-10-07 ｜ **先写下来才算数**")
    L.append("> 四源合成：子平真诠系(骨架/边界) + 巾箱(条件) + 道秀(机制/时间窗) + 案例库(强度)")
    L.append("> 纪律：**方法2 + 三道闸**——①按轴归组校正 ②半库发现/半库确认 ③未蒸登记在册\n")
    L.append(f"**当前条目数：{len(E)} 条，归 {len(AXES)} 轴**（真正参与多重比较校正的是 **{len(AXES)} 个轴**，不是 {len(E)} 条）\n")

    L.append("## 〇 · 轴表（校正单元）\n")
    L.append("| 轴 | 名称 | 条件族 | 主测事类 | 条数 |")
    L.append("|---|---|---|---|---|")
    for a, n, c, d in AXES:
        cnt = sum(1 for e in E if e["axis"] == a)
        L.append(f"| {a} | {n} | {c} | {d} | {cnt} |")
    L.append("")

    NUM, AGREE, CROSS, ROWS, REG = load_scores(here)
    # 册子自愈：打分器测过、册子没登记的编号（口径变体）→ 由本体克隆补登，避免「测了却没底账」
    _base = {e["id"]: e for e in E}
    _have = set(_base)
    _added = 0
    for sid in sorted(REG):
        if sid in _have:
            continue
        stem = sid.rstrip("xmy")
        b = dict(_base[stem]) if stem in _base else {
            "id": sid, "axis": "?", "name": sid, "cond": "（未登记）", "dir": "（未登记）",
            "mech": "", "bnd": "", "src": "（未登记）", "status": "wait", "res": ""}
        b.update(id=sid, auto=True,
                 name=b["name"] + f"〔口径变体 {sid[len(stem):]}〕",
                 src=(b.get("src") or "") + "（自动补登）")
        E.append(b); _added += 1
    MICON = {"ok": "★★跨源", "half": "★两半", "flat": "▫无信号", "stuck": "⬜测不动", "none": "❓未跑"}
    L.append("## 一 · 条目清单（状态栏＝**机器写入**，来自 `score-splithalf.txt`；手写字段降级为备注）\n")
    if _added:
        L.append(f"> 另有 **{_added} 条口径变体**由打分器自动补登（编号带 `x`/`m`/`y` 后缀），"
                 f"已计入下表与统计。\n")
    drift, lag = [], []

    def resolve(eid):
        """本体编号有时只以变体形式入册（如 AX01-07 只有 AX01-07x 被注册）——认领变体，别误报「没测」。"""
        if eid in REG:
            return eid, ""
        for suf in ("x", "m", "y"):
            if eid + suf in REG:
                return eid + suf, f"（本体按变体 {suf} 计）"
        return eid, ""

    for a, n, c, d in AXES:
        L.append(f"### {a} {n}\n")
        L.append("| 编号 | 条目 | 条件（可算字段） | 方向 | 机制 | 边界 | 出处 | 状态（机器） |")
        L.append("|---|---|---|---|---|---|---|---|")
        for e in [x for x in E if x["axis"] == a]:
            rid, rnote = resolve(e["id"])
            ms, mres = mstat(rid, NUM, AGREE, CROSS, ROWS, REG)
            hand = e["res"].replace("|", "/") if e["res"] else ""
            if e.get("auto"):
                pass
            elif e["status"] in ("ok", "half") and ms in ("flat", "none", "stuck"):
                drift.append(f"| {e['id']} | {e['status']} | {ms} | 旧结果（已换口径）→ 现行口径全平／测不到 |")
            elif e["status"] in ("ok", "half") and ms != e["status"]:
                lag.append(f"{e['id']}({e['status']}→{ms})")
            elif e["status"] == "wait" and ms in ("ok", "half", "flat"):
                lag.append(f"{e['id']}(wait→{ms})")
            note = f" ｜备注（手写）：{hand}" if hand else ""
            L.append(f"| {e['id']} | {e['name']} | {e['cond']} | {e['dir']} | {e['mech']} | "
                     f"{e['bnd']} | {e['src']} | {MICON[ms]}：{mres}{rnote}{note} |")
        L.append("")

    cnts = {}
    for e in E:
        k = mstat(e["id"], NUM, AGREE, CROSS, ROWS, REG)[0]
        cnts[k] = cnts.get(k, 0) + 1
    L.append("**状态统计（机器）**：" + " ｜ ".join(f"{MICON[k]} {cnts.get(k, 0)} 条"
                                               for k in ("ok", "half", "flat", "stuck", "none")) + "\n")
    L.append("> 状态以打分器为准。手写状态只当历史备注，**漂移本身就是体检结果**。\n")
    L.append("**A 类：手写有结果、当前口径测不出来**——旧数字多来自别的口径／别的出口，"
             "**别拿旧口径的数字当现行证据**：\n")
    L.append("| 编号 | 手写 | 机器 | 说明 |")
    L.append("|---|---|---|---|")
    L += (drift if drift else ["| — | — | — | 无 |"])
    L.append("")
    L.append(f"**B 类（无害）手写滞后**——实测已有数、手写没跟上，共 **{len(lag)} 条**：" +
             ("  ".join(lag) if lag else "无"))
    L.append("")

    L.append("## 二 · 未蒸清单（登记在册，不偷丢）\n")
    L.append("| 类别 | 为什么没蒸 | 下一步 |")
    L.append("|---|---|---|")
    for n, w, x in UNSTEAMED:
        L.append(f"| {n} | {w} | {x} |")
    L.append("")

    L.append("## 三 · 已备可算字段（条件的落地依据）\n")
    L.append("```")
    for i in range(0, len(FIELDS), 3):
        L.append("  ".join(FIELDS[i:i+3]))
    L.append("```\n")
    L.append("结局域（`case_outcomes` / `case_features.verdict_domains`）：" + " ｜ ".join(DOMAINS))
    L.append("")

    with open(os.path.join(here, "entry-list.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    print(f"OK 条目 {len(E)} 条 / {len(AXES)} 轴 ｜ 机器状态：" +
          " ".join(f"{k}={cnts.get(k, 0)}" for k in ("ok", "half", "flat", "stuck", "none")))
    print(f"手写 vs 机器 漂移 {len(drift)} 条（手写只当备注，不再当状态）")
    print(f"→ {here}/entry-list.md")
    print(f"→ {here}/entries.json")


if __name__ == "__main__":
    main()
