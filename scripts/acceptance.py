"""External HTTP acceptance; --visual never substitutes catalog mode for model calls."""
import argparse
import hashlib
import io
import json
import os
import time
from pathlib import Path
import httpx
from pypdf import PdfReader

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://127.0.0.1:8790")
parser.add_argument("--visual", action="store_true")
parser.add_argument("--output", default="verification/private/acceptance.json")
args = parser.parse_args()
headers = {"Authorization": "Bearer " + os.environ["CZ_ACCESS_TOKEN"]} if os.getenv("CZ_ACCESS_TOKEN") else {}
with httpx.Client(base_url=args.base_url, headers=headers, timeout=30, trust_env=False) as client:
    status = client.get("/api/status"); status.raise_for_status(); status = status.json()
    if args.visual and not status["model_configured"]:
        raise SystemExit("视觉模型未配置；不会用馆藏资料核查冒充视觉验收。")
    client.headers["x-cz-csrf"] = status["csrf"]
    case = client.post("/api/demos", json={"object_id": 48450}); case.raise_for_status(); case = case.json()
    started = time.monotonic()
    job = client.post(f"/api/cases/{case['id']}/jobs", json={"mode": "analyze" if args.visual else "catalog"})
    job.raise_for_status(); job = job.json()
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        job = client.get("/api/jobs/"+job["id"]).json()
        if job["status"] not in ("running", "queued"):
            break
        time.sleep(1)
    assert job["status"] == "complete", job
    report = client.get("/api/jobs/"+job["id"]+"/report").json()
    pdf = client.get("/api/jobs/"+job["id"]+"/report.pdf").content
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 1
    assert hashlib.sha256(pdf).hexdigest() == report["pdf_sha256"]
    assert report["authenticity_probability"] is None
    assert report["model_executed"] == args.visual
    result = {"mode": "real_visual" if args.visual else "catalog_audit", "passed": True, "seconds": round(time.monotonic()-started,2),
              "pdf_pages": 1, "job": job, "model_executed": report["model_executed"], "expert_accuracy_verified": False}
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    out.with_suffix(".pdf").write_bytes(pdf)
    print(json.dumps({k: v for k,v in result.items() if k != "job"}, ensure_ascii=False, indent=2))
