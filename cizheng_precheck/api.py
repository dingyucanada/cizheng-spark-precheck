import fcntl
import hashlib
import io
import json
import os
import secrets
import shutil
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import Settings, ROOT
from .store import Store, uid, now
from .imaging import inspect_photo
from .knowledge import Knowledge
from .engine import Engine
from .schemas import CaseInput, DemoInput, StartInput
from .examples import EXAMPLES
from .provider import Provider

WEB = Path(__file__).parent / "web"


def create_app(settings=None, provider_factory=None):
    s = settings or Settings()
    store = Store(s.data_dir)
    knowledge = Knowledge(s.knowledge_dir, s.data_dir / "source_cache")
    engine = Engine(store, knowledge, s, **({"provider_factory": provider_factory} if provider_factory else {}))
    csrf = secrets.token_urlsafe(24)

    @asynccontextmanager
    async def lifespan(app):
        with (s.data_dir / "server.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("同一数据目录只能运行一个工作进程") from None
            store.recover()
            store.reconcile_cases()
            yield
            await engine.close()
            fcntl.flock(lock, fcntl.LOCK_UN)

    app = FastAPI(title="瓷证 · 一页预检", version="0.2.0", lifespan=lifespan)
    app.state.store, app.state.engine, app.state.settings = store, engine, s
    hosts = ["localhost", "127.0.0.1", "[::1]", "testserver"] + [h.strip() for h in os.getenv("CZ_ALLOWED_HOSTS", "").split(",") if h.strip()]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        path = request.url.path
        if not s.access_token and request.client and request.client.host not in ("127.0.0.1", "::1", "testclient"):
            return JSONResponse({"detail": "远程访问需要配置 CZ_ACCESS_TOKEN"}, status_code=403)
        protected = path.startswith("/api/") and path not in ("/api/login", "/api/health")
        if protected and s.access_token:
            token = request.headers.get("authorization", "").removeprefix("Bearer ") or request.cookies.get("cz_access", "")
            if not secrets.compare_digest(token, s.access_token):
                return JSONResponse({"detail": "请输入本机访问口令"}, status_code=401)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "不接受跨站请求"}, status_code=403)
            if path != "/api/login" and not secrets.compare_digest(request.headers.get("x-cz-csrf", ""), csrf):
                return JSONResponse({"detail": "会话已更新，请刷新页面"}, status_code=403)
            data = bytearray()
            async for chunk in request.stream():
                data.extend(chunk)
                if len(data) > 50*1024*1024:
                    return JSONResponse({"detail": "单次上传最多 6 张、每张 8 MB"}, status_code=413)
            request._body = bytes(data)
        response = await call_next(request)
        response.headers.update({"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
                                 "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; frame-src 'self'; object-src 'none'; frame-ancestors 'self'; base-uri 'none'"})
        return response

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "记录不存在"}, status_code=404)

    @app.get("/")
    def home():
        return FileResponse(WEB / "index.html")

    @app.get("/assets/{filename}")
    def assets(filename: str):
        if filename not in ("app.js", "style.css"):
            raise HTTPException(404)
        return FileResponse(WEB / filename)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "0.2.0", "installation": hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]}

    @app.post("/api/login")
    async def login(request: Request):
        data = await request.json()
        if not isinstance(data.get("token"), str) or not secrets.compare_digest(data["token"], s.access_token):
            raise HTTPException(401, "口令不正确")
        response = JSONResponse({"ok": True})
        response.set_cookie("cz_access", s.access_token, httponly=True, samesite="strict", secure=request.url.scheme == "https")
        return response

    @app.get("/api/status")
    def status():
        return {"csrf": csrf, "model_configured": s.model_configured, "model": s.model if s.model_configured else None,
                "model_verified": False, "online_enabled": s.enable_online, "cloud_text_enabled": s.cloud_text,
                "catalog_records": len(knowledge.refs), "catalog_photos": len(knowledge.photos),
                "photo_transport": "local_only", "max_photos": 6, "version": "0.2.0"}

    @app.get("/api/demos")
    def demos():
        return [dict(object_id=i, name=e['name'], description=e['description'], theme=e['theme'],
                     premise=e['premise'], claim=e['claim'], photo=f'/api/demo-photos/met-{i}-01.jpg') for i,e in EXAMPLES.items()]

    @app.get('/api/model-health')
    async def model_health():
        return await Provider(s).health()


    @app.get("/api/demo-photos/{filename}")
    def demo_photo(filename: str):
        allowed = {Path(p["file"]).name for p in knowledge.photos}
        if filename not in allowed:
            raise HTTPException(404)
        return FileResponse(s.knowledge_dir / "photos" / filename)

    def save_case(meta, uploads, demo=False, example=None):
        collected, hashes = [], set()
        for i, data in enumerate(uploads):
            role = meta.roles[i] if i < len(meta.roles) else "unknown"
            try:
                photo, preview = inspect_photo(data, f"P{i+1}", role)
            except Exception as e:
                raise HTTPException(422, f"第 {i+1} 张图片无法读取，请使用清晰的 JPEG/PNG/WebP 原图") from e
            if photo["pixel_sha256"] in hashes:
                raise HTTPException(422, "存在重复照片，请保留不同角度的照片")
            hashes.add(photo["pixel_sha256"])
            collected.append((photo, data, preview))
        return store.save_case(meta, collected, demo, example)


    @app.post("/api/cases")
    async def create_case(request: Request):
        async with request.form(max_files=6, max_fields=3, max_part_size=8*1024*1024) as form:
            try:
                meta = CaseInput.model_validate_json(str(form.get("metadata", "{}")))
            except ValueError:
                raise HTTPException(422, "器物信息格式不正确") from None
            files = form.getlist("photos")
            if not 1 <= len(files) <= 6:
                raise HTTPException(422, "请提交 1 至 6 张照片")
            uploads = []
            for f in files:
                if not hasattr(f, "read"):
                    raise HTTPException(422, "照片格式不正确")
                uploads.append(await f.read(8*1024*1024+1))
            return save_case(meta, uploads)

    @app.post("/api/demos")
    def create_demo(body: DemoInput):
        e = EXAMPLES[body.object_id]
        photos = [p for p in knowledge.photos if p["object_id"] == body.object_id]
        return save_case(CaseInput(name=e['name'], claim=e['claim'], source="公开馆藏", roles=e['roles']),
                         [(s.knowledge_dir / "photos" / Path(p["file"]).name).read_bytes() for p in photos], True,
                         dict(object_id=body.object_id,scenario=e['scenario'],premise=e['premise']))


    @app.get("/api/cases")
    def cases():
        result=[]
        for c in store.cases():
            jobs=store.jobs_for_case(c['id'])
            latest=next((j for j in jobs if j['status']=='complete'),None)
            result.append({k:c[k] for k in ('id','name','created_at','source','demo')} | {
                'photo_count':len(c['photos']), 'report_count':sum(j['status']=='complete' for j in jobs),
                'latest_job': latest['id'] if latest else None})
        return result

    @app.get("/api/cases/{case_id}")
    def case(case_id: str):
        return {"case": store.canonical(case_id), "jobs": store.jobs_for_case(case_id)}


    @app.get("/api/cases/{case_id}/photos/{photo_id}")
    def photo(case_id: str, photo_id: str):
        case = store.get(case_id, "case")
        p = next((p for p in case["photos"] if p["id"] == photo_id), None)
        if not p:
            raise HTTPException(404)
        return FileResponse(store.case_dir(case_id) / p["preview_file"])

    @app.post("/api/cases/{case_id}/jobs", status_code=202)
    async def start(case_id: str, body: StartInput):
        try:
            return engine.start(store.canonical(case_id), body.mode, force_new=body.force_new)
        except ValueError as e:
            raise HTTPException(409, str(e)) from None

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        return store.get(job_id, "job")

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel(job_id: str):
        job = store.get(job_id, "job")
        if job_id in engine.tasks:
            engine.tasks[job_id].cancel()
        return {"status": "cancelling" if job["status"] in ("queued", "running") else job["status"]}

    @app.get("/api/jobs/{job_id}/report")
    def report(job_id: str):
        return store.get(job_id+"_report", "report")

    @app.get("/api/jobs/{job_id}/report.pdf")
    def pdf(job_id: str):
        r = store.get(job_id+"_report", "report")
        return FileResponse(store.case_dir(r["case_id"]) / (job_id+".pdf"), media_type="application/pdf", filename=r["report_id"]+".pdf")

    @app.get("/api/jobs/{job_id}/evidence.zip")
    def bundle(job_id: str):
        r = store.get(job_id+"_report", "report")
        folder = store.case_dir(r["case_id"])
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(folder/(job_id+".pdf"), "report.pdf")
            z.write(folder/(job_id+".json"), "evidence.json")
            for p in r["photos"]:
                if hashlib.sha256((folder/p['original_file']).read_bytes()).hexdigest() != p['sha256']:
                    raise HTTPException(409, '原图指纹已改变，停止导出；请核查本地文件')
                z.write(folder/p["original_file"], "originals/"+p["original_file"])
                z.write(folder/p["preview_file"], "previews/"+p["preview_file"])
        return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="'+r["report_id"]+'-evidence.zip"'})

    return app
