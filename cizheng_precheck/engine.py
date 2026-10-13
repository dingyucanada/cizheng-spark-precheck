import asyncio
import hashlib
import json
import os
import time
from .store import uid, now
from .provider import Provider, ModelFailure
from .knowledge import validate_comparisons
from .policy import catalog_report, decide
from .pdf_report import render


class Engine:
    def __init__(self, store, knowledge, settings, provider_factory=Provider):
        self.store, self.knowledge, self.s = store, knowledge, settings
        self.provider_factory = provider_factory
        self.tasks = {}
        self.semaphore = asyncio.Semaphore(1)

    def progress(self, job, stage, percent, message):
        job.update(stage=stage, percent=percent, message=message)
        job["events"].append({"at": now(), "stage": stage, "percent": percent, "message": message})
        self.store.put("job", job)

    def start(self, case, mode):
        if sum(not t.done() for t in self.tasks.values()) >= 4:
            raise ValueError("当前队列已满，请等待正在处理的器物完成")
        if mode == "analyze" and not self.s.model_configured:
            raise ValueError("尚未连接视觉模型。可先体验公开馆藏资料核查；新照片研判需连接 Spark 模型。")
        job = {"id": uid("job_"), "case_id": case["id"], "mode": mode, "created_at": now(), "status": "queued", "stage": "等待处理", "percent": 0, "message": "照片已保存", "events": []}
        self.store.put("job", job)
        task = asyncio.create_task(self.run(job, case))
        self.tasks[job["id"]] = task
        task.add_done_callback(lambda _: self.tasks.pop(job["id"], None))
        return job

    async def run(self, job, case):
        provider = self.provider_factory(self.s)
        started = time.monotonic()
        try:
            async with self.semaphore:
                job["status"] = "running"
                async with asyncio.timeout(self.s.job_timeout):
                    await self.pipeline(job, case, provider)
        except asyncio.CancelledError:
            job.update(status="cancelled", stage="已取消", message="照片已保存，可重新开始")
        except TimeoutError:
            job.update(status="failed", stage="处理超时", message="已保留照片及阶段记录，请重试或减少图片")
        except ModelFailure as e:
            job.update(status="failed", stage="模型未完成", message=str(e))
        except Exception:
            # Never return provider payloads, credentials or local paths to the browser.
            import logging
            logging.getLogger(__name__).exception("precheck job failed: %s", job["id"])
            job.update(status="failed", stage="未能生成报告", message="处理失败；请检查运行日志及中文字体配置。原图已保留。")
        finally:
            job["finished_at"] = now()
            job["seconds"] = round(time.monotonic()-started, 3)
            job["model_calls"] = provider.calls
            self.store.put("job", job)

    async def pipeline(self, job, case, provider):
        folder = self.store.case_dir(case["id"])
        self.progress(job, "照片检查", 12, "校验原图指纹、重复图片及基本画质")
        origins = await asyncio.to_thread(self.knowledge.origins, case["photos"])
        preferred = {m["reference_id"] for m in origins if m["match"] in ("exact_file", "exact_pixels")}
        audit = {"origin_matches": origins, "observations": None, "comparisons": [], "rejected_citations": [], "review": {}, "online": {"status": "disabled"}}
        if job["mode"] == "catalog":
            refs = self.knowledge.search("porcelain stoneware", preferred, 5)
            self.progress(job, "资料核验", 62, "逐张比对已收录馆藏图像，核验馆方原始记录")
            report = catalog_report(case, job, refs, origins)
        else:
            self.progress(job, "视觉观察", 26, "本地视觉模型读取照片，定位器型、底足及局部疑点")
            analysis = await provider.observe(case["photos"], folder)
            audit["observations"] = analysis
            self.progress(job, "检索参考资料", 50, "按可见特征查询本地馆藏资料库")
            refs = self.knowledge.search(" ".join(analysis["search_terms"]), preferred, 5)
            if self.s.enable_online and case["online"]:
                online_refs, online_status = await self.knowledge.online_search(analysis["search_terms"])
                audit["online"] = online_status
                refs = list({r["id"]: r for r in refs + online_refs}.values())[:7]
            if len(refs) > 1:
                different = next((r for r in refs[1:] if r['source_group'] != refs[0]['source_group']), None)
                if different:
                    refs = [refs[0],different] + [r for r in refs[1:] if r['id'] != different['id']]
            target_forms = set(analysis['search_terms']) & {'bowl','vase','jar','dish'}
            refs = [dict(r, applicability='comparable_candidate' if (not target_forms or any(t in r['title'].lower() for t in target_forms)) else 'context_only') for r in refs]
            self.progress(job, "证据比较", 65, "比较照片观察和资料；保存支持点、疑点及替代解释")
            comparisons, rejected = [], []
            review = {"items": []}
            if refs:
                reference_images = await self.knowledge.reference_images(refs, online=self.s.enable_online and case['online'])
                audit['reference_images'] = [{'reference_id': rid, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for rid,path in reference_images]
                selected_photos = [case['photos'][0]]
                if len(case['photos']) > 1:
                    selected_photos.append(next((p for p in case['photos'][1:] if p['role'] == 'base'), case['photos'][-1]))
                comparison_images = [(p['id'], folder/p['preview_file']) for p in selected_photos] + [('REFERENCE '+rid, path) for rid,path in reference_images]
                proposed = await provider.compare(analysis["observations"], refs, case["claim"], images=comparison_images)
                comparisons, rejected = validate_comparisons(proposed["comparisons"], analysis["observations"], refs)
            audit.update(comparisons=comparisons, rejected_citations=rejected)
            self.progress(job, "引用及理由复核", 79, "校验引用原句、照片关联和推断跨度")
            if comparisons:
                review = await provider.review(analysis["observations"], comparisons, refs)
                # Unknown IDs cannot support any decision; duplicate review IDs are rejected.
                keys = [r["comparison_id"] for r in review["items"]]
                if len(keys) != len(set(keys)) or not set(keys).issubset({c["id"] for c in comparisons}):
                    raise ModelFailure("复核记录未正确绑定比较条目")
                if self.s.cloud_text and case["cloud_review"] and self.s.text_url and self.s.text_model:
                    try:
                        audit["cloud_public_review"] = await provider.review([], comparisons, refs, cloud=True)
                    except ModelFailure:
                        audit["cloud_public_review"] = {"status": "unavailable", "effect_on_score": "none"}
            audit["review"] = review
            report = decide(case, job, analysis, comparisons, review, refs, origins)
        report["audit"] = audit
        report["runtime"] = {"model_calls": provider.calls, "hardware_verified": False, "rule_version": report["score"]["method"]}
        self.progress(job, "排版一页报告", 93, "生成 PDF 并封存原图指纹和本次证据档案")
        # All photos are checked again before rendering: never publish a result over modified inputs.
        for photo in case["photos"]:
            actual = hashlib.sha256((folder / photo["original_file"]).read_bytes()).hexdigest()
            if actual != photo["sha256"]:
                raise ValueError("input integrity mismatch")
        output = folder / f"{job['id']}.pdf"
        temporary = output.with_suffix(".part")
        await asyncio.to_thread(render, report, folder, temporary)
        temporary.replace(output)
        report["pdf_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
        (folder / f"{job['id']}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        self.store.put("report", dict(report, id=job["id"]+"_report", created_at=now()))
        job.update(status="complete", report_id=job["id"]+"_report")
        self.progress(job, "报告已生成", 100, "可下载一页 PDF，或展开每条意见的证据")

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
