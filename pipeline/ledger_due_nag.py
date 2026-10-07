#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""前瞻账本催账器（cron 用）——只在「有到期未对账的前瞻条目」时出声，否则静默。

设计要点
- 只报 kind=prospective（回看类不计 A 档，不必催）。
- 只报 result 为空且 due <= 今天的。
- 什么都不该说的时候，输出为空 ⇒ cron 静默（no_agent 模式）。
"""
import datetime
import io
import json
import os

LEDGER = os.path.expanduser(
    "/home/ubuntu/.hermes/profiles/see/skills/mingli/mingli-self-audit/scripts/ledger.jsonl"
)
RECON = ("cd /home/ubuntu/.hermes/profiles/see/skills/mingli/mingli-self-audit/scripts && "
         "python3 self_audit.py --ledger reconcile --id N --result hit|miss|partial --note '…'")


def main() -> None:
    if not os.path.exists(LEDGER):
        return
    today = datetime.date.today()
    rows = []
    for line in io.open(LEDGER, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        it = json.loads(line)
        if it.get("kind", "prospective") != "prospective":
            continue
        if it.get("result") or not it.get("due"):
            continue
        d = datetime.date.fromisoformat(it["due"])
        if d <= today:
            rows.append((it, d))

    if not rows:
        return  # 静默：没有该对账的事

    rows.sort(key=lambda x: x[1])
    out = [f"⏰ 前瞻账本到期未对账 {len(rows)} 条（这就是 A 档唯一的来源）："]
    for it, d in rows:
        late = (today - d).days
        tail = f"（逾期 {late} 天）" if late else "（今天到期）"
        out.append(f"\n#{it['id']} {it['subject']} — 到期 {d}{tail}")
        out.append(f"   当时的预测：{it['claim']}")
        out.append(f"   当时自信 {it['confidence']}／基线 {it['baseline']}"
                   f"（比「不靠这个本来也会发生」高多少才算命中）")
        if it.get("hit_rule"):
            out.append(f"   判据（登记时写死）：{it['hit_rule']}")
        out.append("   → 现实里发生了吗？(hit / miss / partial)")
    out.append(f"\n对账命令：{RECON}")
    out.append("※ 只回现实事实即可，我来判命中并归因；回看类的「命中」不算数。")
    print("\n".join(out))


if __name__ == "__main__":
    main()
