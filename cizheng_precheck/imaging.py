import hashlib
import io
import warnings
import numpy as np
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 24_000_000
MAX_FILE = 8 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inspect_photo(data, photo_id, role="unknown"):
    if len(data) > MAX_FILE:
        raise ValueError("单张照片最多 8 MB")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data)) as raw:
            if raw.format not in ("JPEG", "PNG", "WEBP") or getattr(raw, "n_frames", 1) != 1:
                raise ValueError("只接受单帧 JPEG、PNG 或 WebP 照片")
            raw.load()
            im = ImageOps.exif_transpose(raw).convert("RGB")
    width, height = im.size
    if min(width, height) < 128:
        raise ValueError("图片太小，请上传至少 128 像素的照片")
    thumb = np.asarray(im.convert("L").resize((128, 128)), dtype=float)
    pixel_hash = sha(f"{width}x{height}:".encode() + im.tobytes())
    tiny = np.asarray(im.convert("L").resize((9, 8)), dtype=int)
    bits = tiny[:, 1:] > tiny[:, :-1]
    dhash = f"{int(''.join('1' if b else '0' for b in bits.flatten()), 2):016x}"
    # Pixel statistics are intake heuristics, never an authenticity/AI-image detector.
    issues = []
    if min(width, height) < 640:
        issues.append("分辨率偏低，建议补充原图")
    if thumb.std() < 10:
        issues.append("画面信息偏少或反差偏低")
    if (thumb > 250).mean() > 0.85:
        issues.append("大部分画面过亮")
    if (thumb < 8).mean() > 0.85:
        issues.append("大部分画面过暗")
    preview = im.copy()
    preview.thumbnail((1400, 1400))
    buf = io.BytesIO()
    preview.save(buf, "JPEG", quality=90)
    return {
        "id": photo_id, "sha256": sha(data), "pixel_sha256": pixel_hash, "dhash": dhash,
        "width": width, "height": height, "bytes": len(data), "role": role,
        "issues": issues, "capture_time": None, "device_id": None,
        "original_file": f"{photo_id}.original", "preview_file": f"{photo_id}.jpg",
    }, buf.getvalue()
