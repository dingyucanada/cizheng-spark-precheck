import html
import os
import threading
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from PIL import Image

_FONT_LOCK = threading.Lock()


def fonts():
    with _FONT_LOCK:
        if "CZ" in pdfmetrics.getRegisteredFontNames():
            return "CZ", "CZB"
        candidates = [os.getenv("CZ_FONT_PATH", ""), "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "/System/Library/Fonts/STHeiti Light.ttc"]
        regular = next((x for x in candidates if x and Path(x).is_file()), None)
        if regular:
            bold = os.getenv("CZ_FONT_BOLD_PATH") or ("/System/Library/Fonts/STHeiti Medium.ttc" if regular.startswith("/System") else regular)
            pdfmetrics.registerFont(TTFont("CZ", regular, subfontIndex=0))
            pdfmetrics.registerFont(TTFont("CZB", bold, subfontIndex=0))
            return "CZ", "CZB"
        raise RuntimeError("缺少中文字体；请执行 scripts/bootstrap-spark.sh 或设置 CZ_FONT_PATH")


def render(report, directory, output):
    normal, boldfont = fonts()
    W, H, M = 595.276, 841.89, 37
    CW = W - 2*M
    ink, green, muted, amber = map(HexColor, ["#203F3E", "#315F58", "#687771", "#A57533"])
    c = canvas.Canvas(str(output), pagesize=(W, H))
    c.setTitle(report["title"] + " · " + report["object_name"])
    c.setAuthor("瓷证")

    def box(x, y, w, h, color, r=0):
        c.setFillColor(HexColor(color))
        c.roundRect(x, H-y-h, w, h, r, fill=1, stroke=0)

    def text(value, x, y, w, size=10, bold=False, color=ink, max_h=70):
        # Fit text into reserved blocks, never let generated prose create an extra page.
        escaped = html.escape(str(value)).replace("\n", "<br/>")
        for candidate in [size, size-.5, size-1, size-1.5, size-2]:
            p = Paragraph(escaped, ParagraphStyle("p", fontName=boldfont if bold else normal, fontSize=candidate, leading=candidate*1.4, textColor=color, wordWrap="CJK"))
            _, height = p.wrap(w, H)
            if height <= max_h:
                p.drawOn(c, x, H-y-height)
                return
        raise ValueError("报告文字超过一页布局容量；请缩短结构化理由")

    box(0, 0, W, 6, "#315F58")
    text("瓷证", M, 23, 100, 20, True)
    text("器物照片 · 判断理由 · 送检建议", 325, 31, 240, 9, color=muted)
    text(report["title"], M, 65, CW, 23, True)
    text(report["object_name"], M, 103, 275, 11.5, True, max_h=18)
    text(report["report_id"] + " | " + report["generated_at"][:10], 328, 106, 229, 8.4, color=muted, max_h=15)
    box(M, 136, CW, 128, "#F0F5F2", 10)
    text("预检意见", M+17, 151, 290, 9.5, color=green)
    text(report["opinion"], M+17, 176, 333, 21, True, max_h=31)
    text(report["advice"], M+17, 210, 328, 10, color=green, max_h=28)
    text("依据照片及可核验资料形成意见", M+17, 244, 328, 8.3, color=muted, max_h=14)
    sx = W-M-137
    box(sx, 146, 126, 108, "#F7F1E6", 8)
    text("送检关注评分", sx+13, 156, 110, 9, color=amber)
    value = report["score"]["value"]
    text(str(value) if value is not None else "—", sx+15, 175, 48, 32, True, amber, 46)
    text("/ 5", sx+53, 190, 55, 14, color=amber)
    text(report["score"]["label"], sx+14, 219, 103, 10.5, True, amber, 16)
    for i in range(5):
        box(sx+14+i*19, 239, 15, 4, "#A57533" if value and i<value else "#E1D9CB", 1)
    text("本次输入照片", M, 280, 250, 11.5, True)
    text(f"{len(report['photos'])} 张原图留存 · 本页精选最多 3 张", 290, 283, 267, 8.3, color=muted)
    selected = report["photos"][:3]
    widths = {1: [CW], 2: [CW/2-4]*2, 3: [242,131,131]}[len(selected)]
    x = M
    for photo, width in zip(selected, widths):
        box(x, 307, width, 151, "#F4F5F1", 5)
        path = directory / photo["preview_file"]
        with Image.open(path) as im:
            iw, ih = im.size
        scale = min((width-6)/iw, 145/ih)
        dw, dh = iw*scale, ih*scale
        c.drawImage(str(path), x+(width-dw)/2, H-310-(145+dh)/2, width=dw, height=dh)
        text(photo["id"] + "  原图留存", x, 463, width, 8.7, color=muted, max_h=14)
        x += width+8
    text(report["scope"], M, 485, CW, 8.7, color=muted, max_h=25)
    text("判断理由", M, 515, 260, 11.5, True)
    text(report["score"]["label"] + " · 点击资料编号查看出处", 307, 517, 250, 8.5, color=amber)
    reasons = report["reasons"][:3]
    for i, reason in enumerate(reasons):
        y = 543+i*61
        box(M, y, 20, 20, "#F0F5F2", 4)
        text(f"{i+1:02}", M+3, y+2, 20, 10, color=green, max_h=17)
        text(reason["title"], M+29, y, 360, 10.5, True, max_h=17)
        text("/".join(reason["photo_ids"]), 458, y+1, 99, 8, color=muted, max_h=15)
        text(reason["body"], M+29, y+20, CW-29, 9, max_h=35)
        if i < 2:
            box(M+29, y+56, CW-29, .4, "#DCE5DF")
    box(M, 727, CW, 43, "#315F58", 8)
    text("下一步", M+14, 738, 70, 10, True, HexColor("#FFFFFF"), 17)
    text(report["next_step"], M+83, 736, CW-100, 9.5, color=HexColor("#FFFFFF"), max_h=30)
    text("评分：2常规核验 · 3重点复核 · 4-5优先送检；证据不足暂不评分。不是真品率。", M, 780, CW, 7.5, color=muted, max_h=12)
    used_ids = list(dict.fromkeys(r for reason in reasons for r in reason["reference_ids"]))[:3]
    sources = {r["id"]: r for r in report["references"]}
    labels = "资料出处：" + (" · ".join(used_ids) if used_ids else "未形成可用引用；详见证据档案")
    text(labels, M, 794, CW, 7.5, color=muted, max_h=12)
    for n, rid in enumerate(used_ids):
        if rid in sources:
            c.linkURL(sources[rid]["url"], (M+42+n*95, H-806, M+135+n*95, H-791), relative=0)
    text(report["notice"], M, 808, CW, 7.5, color=muted, max_h=12)
    c.showPage()
    c.save()
