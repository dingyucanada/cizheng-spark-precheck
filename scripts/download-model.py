"""Download a pinned official checkpoint; download consent is the act of running this script."""
import argparse
import json
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="Qwen/Qwen3-VL-8B-Instruct")
parser.add_argument("--revision", default="main")
parser.add_argument("--destination", default="models/qwen3-vl-8b")
parser.add_argument("--inspect-only", action="store_true")
args = parser.parse_args()
info = HfApi().model_info(args.model, revision=args.revision, files_metadata=True)
total = sum(f.size or 0 for f in info.siblings)
print(json.dumps({"model": args.model, "revision": info.sha, "repository_size_gb": round(total/1024**3,2)}, ensure_ascii=False))
if not args.inspect_only:
    path = snapshot_download(args.model, revision=info.sha, local_dir=args.destination)
    manifest = {"model": args.model, "revision": info.sha, "path": str(Path(path).resolve())}
    Path(args.destination, "cizheng-checkpoint.json").write_text(json.dumps(manifest, indent=2))
    print("模型已下载，提交哈希已保存。")
