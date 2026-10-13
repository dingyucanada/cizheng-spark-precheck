"""Download a pinned official checkpoint; download consent is the act of running this script."""
import argparse
import json
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="Qwen/Qwen3-VL-8B-Instruct")
parser.add_argument("--revision", default=None)
parser.add_argument("--destination", default="models/qwen3-vl-8b")
parser.add_argument("--inspect-only", action="store_true")
args = parser.parse_args()
manifest_path=Path(args.destination)/'cizheng-checkpoint.json'
revision=args.revision
if revision is None and manifest_path.exists():
    previous=json.loads(manifest_path.read_text())
    if previous.get('model')!=args.model:
        raise SystemExit('此目录已有其他模型记录，请改用单独的 --destination。')
    revision=previous['revision']
info = HfApi().model_info(args.model, revision=revision or 'main', files_metadata=True)
if not args.inspect_only:
    import shutil
    existing=Path(args.destination)
    available=shutil.disk_usage(existing if existing.exists() else Path.cwd()).free
    missing=max(0,sum(f.size or 0 for f in info.siblings if not (existing/f.rfilename).is_file()))
    if available < missing + 5*1024**3:
        raise SystemExit('可用磁盘不足以保存模型并留出运行空间，请先清理或更换模型目录。')
total = sum(f.size or 0 for f in info.siblings)
print(json.dumps({"model": args.model, "revision": info.sha, "repository_size_gb": round(total/1024**3,2)}, ensure_ascii=False))
if not args.inspect_only:
    path = snapshot_download(args.model, revision=info.sha, local_dir=args.destination)
    manifest = {"model": args.model, "revision": info.sha, "path": str(Path(path).resolve())}
    Path(args.destination, "cizheng-checkpoint.json").write_text(json.dumps(manifest, indent=2))
    print("模型已下载，提交哈希已保存。")
