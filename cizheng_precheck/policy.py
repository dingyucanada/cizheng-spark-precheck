"""Versioned review-priority rules. No probability or automatic authenticity verdict."""
from datetime import datetime
from zoneinfo import ZoneInfo

VERSION = "review-priority-1.0"
LABELS = {1: "常规核验", 2: "常规核验", 3: "重点复核", 4: "优先送检", 5: "优先送检"}


def rating(value, trigger):
    return {"name": "送检关注评分", "value": value, "max": 5,
            "label": LABELS.get(value, "暂不评分"), "trigger": trigger,
            "method": VERSION, "authenticity_probability": None,
            "meaning": "分值越高，越需要专业复核；规则等级分，不是真品率。"}


def base_report(case, job, refs, origins):
    return {
        "schema_version": "1.0", "report_id": "CZ-" + job["id"][4:12].upper(),
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "title": "瓷器 AI 辅助预鉴定报告", "object_name": case["name"],
        "case_id": case["id"], "job_id": job["id"], "photos": case["photos"],
        "references": refs, "origin_matches": origins, "reasons": [],
        "claim": case.get("claim", ""), "source_declaration": case["source"],
        "scope": "照片辅助预检，供送检前参考。", "expert_reviewed": False,
        "identity_verified": False, "authenticity_probability": None,
        "notice": "照片分析仅供送检参考，不能替代专业机构实物鉴定。",
    }


def catalog_report(case, job, refs, origins):
    report = base_report(case, job, refs, origins)
    exact = [m for m in origins if m["match"] in ("exact_file", "exact_pixels")]
    ids = {m["reference_id"] for m in exact}
    complete_match = {m["photo_id"] for m in exact} == {p["id"] for p in case["photos"]}
    report.update(mode="catalog_audit", scope="公开照片来源核验及馆藏资料核查；本轮未运行视觉模型。", model_executed=False)
    if len(ids) != 1 or not complete_match:
        report.update(opinion="资料不足，请补充照片", advice="未能把全部照片核对到同一馆藏记录。", score=rating(None, "馆藏照片未完整匹配"), next_step="连接本地视觉模型后分析，或补充同一器物的来源信息。")
        report["reasons"] = [{"title": "照片来源尚未核实", "body": "不能以相似图片或文件名确认照片出处，更不能确认实物身份。", "photo_ids": [], "reference_ids": []}]
        return report
    ref = next(r for r in refs if r["id"] in ids)
    repaired = "repair" in ref["medium"].lower()
    report.update(opinion="馆方记录有修补，建议复核" if repaired else "照片出处已核对，真伪待核",
                  advice="优先核对口沿修补记录及实物状态。" if repaired else "资料归属已列明，实物身份仍须专业核验。",
                  score=rating(3 if repaired else None, "同一照片对应的馆方原始记录明确记载修补" if repaired else "来源核查不等于真伪筛查，暂不评分"),
                  next_step="携带原图和本页咨询专业机构；补充底足、款识及疑点位置的带尺度微距。")
    pids = [p["id"] for p in case["photos"]]
    report["reasons"] = [
        {"title": "原图出处可追溯", "body": f"本组照片的文件或解码像素匹配 The Met 的公开图像。馆藏号 {ref['accession']}；匹配仅确认图片来源。", "photo_ids": pids, "reference_ids": [ref["id"]]},
        {"title": "馆方记录明确记载修补" if repaired else "馆方归属仅适用于参考器", "body": ("材质栏原文包含 gold lacquer repairs（金漆修补）。修补本身不能证明整件为仿品，应核对修复档案。" if repaired else f"馆方年代记录为 {ref['date']}。这是对馆藏对象的描述，不能转用于外观相似的另一件器物。"), "photo_ids": pids[:2], "reference_ids": [ref["id"]]},
        {"title": "实物身份及细节仍需核验", "body": "本轮核验了图片及文献，尚无现场采集或材料检测；微观老化、修补年代及真伪不能据此确定。", "photo_ids": pids, "reference_ids": []},
    ]
    return report


def decide(case, job, analysis, comparisons, review, refs, origins):
    report = base_report(case, job, refs, origins)
    report.update(mode="visual_precheck", model_executed=True)
    obs = {o["id"]: o for o in analysis["observations"]}
    reviewed = {r["comparison_id"]: r for r in review.get("items", [])}
    accepted = [c for c in comparisons if reviewed.get(c["id"], {}).get("verdict") == "supported"]
    direct = [c for c in accepted if c["relation"] == "conflict" and c["claim_relevance"] == "direct" and case.get("claim")]
    repairs = [o for o in obs.values() if o["kind"] == "repair_candidate"]
    anomalies = [o for o in obs.values() if o["kind"] == "anomaly_candidate"]
    issues = [issue for p in case["photos"] for issue in p["issues"]]
    sufficient = (len(case["photos"]) >= 2 and {"overall", "base"}.issubset(set(analysis["visible_roles"])) and not issues
                  and analysis["object_consistency"] == "consistent" and analysis["ceramic"] == "yes"
                  and any(o['kind'] != 'unreadable' for o in obs.values()))
    value, trigger = None, "采集覆盖或器物同一性不足，暂停评分"
    opinion, advice = "资料不足，建议补拍", "补齐整体、底足及疑点细节后再评估。"
    if sufficient:
        value, trigger = 2, "本轮有效证据未形成需优先复核的具体矛盾；不表示真品"
        opinion, advice = "本轮未形成明确矛盾", "保留照片和来源信息，送检时核验具体年代及身份。"
        if repairs or anomalies:
            value, trigger = 3, "视觉观察发现修补或异常候选，性质尚需复核"
            opinion, advice = "发现局部疑点，建议复核", "先核对疑点位置及替代解释，再决定送检项目。"
        if direct:
            value, trigger = 4, "有具体归属矛盾通过引用核验及模型二次复核，仍须专家确认"
            opinion, advice = "归属存在疑点，优先送检", "已有照片和资料不支持直接采信当前归属主张。"
            # Multiple pages from the same institution are ONE source group.
            ref_by_id = {r["id"]: r for r in refs}
            groups = {ref_by_id[c["reference_id"]]["source_group"] for c in direct}
            dimensions = {obs[o]["dimension"] for c in direct for o in c["observation_ids"]}
            if len(groups) >= 2 and len(dimensions) >= 2:
                value, trigger = 5, "至少两个维度和两个来源机构存在待专家确认的归属矛盾"
        if value == 2 and not accepted:
            value, trigger = None, "尚未形成经过复核的可用比较依据"
            opinion, advice = "参考证据不足，暂不评分", "本轮保留照片观察；补充可比资料后再形成预检意见。"
    report.update(object_name=analysis["object_name"], score=rating(value, trigger), opinion=opinion, advice=advice)
    reasons = []
    for c in sorted(accepted, key=lambda c: c not in direct):
        related = [obs[o] for o in c["observation_ids"]]
        reasons.append({"title": ("归属疑点：" if c in direct else "资料比对：") + related[0]["dimension"],
                        "body": c["explanation"], "alternative": c["alternative"],
                        "photo_ids": list(dict.fromkeys(o["photo_id"] for o in related)),
                        "observation_ids": c["observation_ids"], "reference_ids": [c["reference_id"]], "quote": c["quote"]})
    for o in repairs + anomalies:
        reasons.append({"title": o["dimension"] + "细节需要复核", "body": o["description"], "alternative": o["alternative"], "photo_ids": [o["photo_id"]], "observation_ids": [o["id"]], "reference_ids": []})
    if not reasons:
        for o in list(obs.values())[:2]:
            reasons.append({"title": o["dimension"] + "观察", "body": o["description"], "alternative": o["alternative"], "photo_ids": [o["photo_id"]], "observation_ids": [o["id"]], "reference_ids": []})
    reasons.append({"title": "证据范围及下一步", "body": "图片记录不提供材料成分或绝对年代；未发现矛盾也不代表真品。对老化、款识和修补应结合实物核验。", "photo_ids": [], "reference_ids": []})
    report["reasons"] = reasons[:3]
    report["all_reasons"] = reasons
    report["next_step"] = ("补拍同一器物的整体、底足和疑点微距，照片需清晰并带尺度。" if not sufficient else "携原图和本页送交专业机构，重点核验上述疑点；请勿自行清洗、刮取或酸洗器物。")
    report["scope"] = "本地模型看图、资料比对及引用复核；评分为送检关注程度。"
    report["review_summary"] = {"citation_checked": len(comparisons), "model_supported": len(accepted), "independent_expert": False, "same_model_review": True}
    return report
