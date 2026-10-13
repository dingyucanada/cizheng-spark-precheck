"""Read-only target inventory; no credential contents or environment dump."""
import json
import platform
import shutil
import subprocess
from pathlib import Path


def run(command):
    try:
        r = subprocess.run(command, text=True, capture_output=True, timeout=15)
        return {"ok": r.returncode == 0, "output": r.stdout.strip()[:2000]}
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "output": "unavailable"}


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    from cizheng_precheck.pdf_report import fonts
    try:
        fonts(); font_ok = True
    except RuntimeError:
        font_ok = False
    result = {"architecture": platform.machine(), "system": platform.system(), "python": platform.python_version(),
              "disk_free_gb": round(shutil.disk_usage(root).free / 1024**3, 1), "cjk_font_ready": font_ok,
              "gpu": run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]),
              "docker": run(["docker", "version", "--format", "{{.Server.Version}}"])}
    destination = root / "verification/private/hardware-inventory.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))
