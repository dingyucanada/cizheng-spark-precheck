"""Run a real image call through the exact production contract on the target Spark."""
import asyncio
import json
import tempfile
from pathlib import Path
from cizheng_precheck.config import Settings
from cizheng_precheck.provider import Provider
from cizheng_precheck.imaging import inspect_photo


async def main():
    s = Settings()
    if not s.model_configured:
        raise SystemExit("请先加载 .env 并启动模型。")
    provider = Provider(s)
    with tempfile.TemporaryDirectory() as d:
        directory = Path(d)
        photos = []
        for i, suffix in enumerate(("01", "03"), 1):
            data = (s.knowledge_dir / "photos" / f"met-48450-{suffix}.jpg").read_bytes()
            p, preview = inspect_photo(data, f"P{i}")
            (directory / p["preview_file"]).write_bytes(preview)
            photos.append(p)
        analysis = await provider.observe(photos, directory)
    out = Path("verification/private/model-probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"contract_passed": True, "expert_accuracy_verified": False, "model": s.model,
                               "observations": analysis, "calls": provider.calls}, ensure_ascii=False, indent=2))
    print("真实双图调用和结构校验通过；请目视复核观察位置。记录：" + str(out))


asyncio.run(main())
