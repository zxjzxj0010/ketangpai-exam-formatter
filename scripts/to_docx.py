#!/usr/bin/env python3
"""将 exam-question-formatter 规范纯文本转换为 Word 文档（.docx）。

规范文本中的图片占位符【图片】/【图片N】会被替换为图片目录中对应的
真实图片（图片.png / 图片1.png / 图片2.png ...），以行内（inline）方式
嵌入文字流，效果与带图 Word 试卷一致。

用法:
    python3 scripts/to_docx.py <输入.txt> <输出.docx> \
        [--images-dir <图片目录>] [--image-width <最大宽度英寸>]
"""

import argparse
import os
import re

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Emu, Pt
from PIL import Image as PILImage

IMG_PATTERN = re.compile(r"【图片(\d*)】")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp")
GROUP_HEADER = re.compile(r"^（\d+[～～]\d+.*(共用题干|共用备选答案)）$")
EMU_PER_INCH = 914400


def find_image(images_dir: str, num: str) -> str | None:
    """按占位符编号查找图片文件：图片N.png/jpg/...；未编号占位符回退 图片1"""
    bases = [f"图片{num}"]
    if num == "":
        bases.append("图片1")
    for base in bases:
        for ext in IMAGE_EXTS:
            p = os.path.join(images_dir, base + ext)
            if os.path.isfile(p):
                return p
    return None


def set_run_font(run, size: int = 12):
    """西文 Times New Roman、中文宋体"""
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = rPr.makeelement(qn("w:rFonts"), {})
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), "宋体")


def add_paragraph_with_images(doc, text: str, images_dir: str,
                              max_width_in: float, missing: list) -> docx.text.paragraph.Paragraph:
    """写一个段落；【图片N】占位符处内嵌对应图片"""
    parts = IMG_PATTERN.split(text)
    p = doc.add_paragraph()
    if len(parts) == 1:
        set_run_font(p.add_run(text))
        return p
    for i in range(0, len(parts), 2):
        seg = parts[i]
        if seg:
            set_run_font(p.add_run(seg))
        if i + 1 < len(parts):
            num = parts[i + 1]
            img_path = find_image(images_dir, num)
            if img_path is None:
                missing.append(f"【图片{num}】未在图片目录找到对应文件")
                set_run_font(p.add_run(f"【图片{num}】"))
                continue
            run = p.add_run()
            try:
                # 按 72dpi 估算图片自然宽度；超过最大宽度时按比例缩小
                with PILImage.open(img_path) as im:
                    w_px, _ = im.size
                natural_w = Emu(int(w_px / 72.0 * EMU_PER_INCH))
                max_w = Emu(int(max_width_in * EMU_PER_INCH))
                if natural_w > max_w:
                    run.add_picture(img_path, width=max_w)
                else:
                    run.add_picture(img_path)
            except Exception as e:  # noqa: BLE001
                missing.append(f"{img_path}: {e}")
                set_run_font(p.add_run(f"【图片{num}】"))
    return p


def convert(txt_path: str, out_path: str, images_dir: str, max_width_in: float) -> list:
    with open(txt_path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    doc = docx.Document()
    # 默认样式：中文宋体小四（12pt），西文 Times New Roman
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)
    rFonts = style.element.get_or_add_rPr().get_or_add_rFonts()
    rFonts.set(qn("w:eastAsia"), "宋体")

    missing: list = []
    for line in lines:
        text = line.rstrip()
        if text.strip() == "":
            doc.add_paragraph()  # 空行 → 空段落（与示例文档一致）
            continue
        p = add_paragraph_with_images(doc, text, images_dir, max_width_in, missing)
        if GROUP_HEADER.match(text.strip()):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.bold = True
    doc.save(out_path)
    return missing


def main():
    ap = argparse.ArgumentParser(description="将规范纯文本转换为 Word 文档（.docx）")
    ap.add_argument("input", help="规范纯文本（.txt）路径")
    ap.add_argument("output", help="输出 Word 文档（.docx）路径")
    ap.add_argument("--images-dir", default="images",
                    help="图片目录，存放 图片.png / 图片1.png / 图片2.png ...（默认 ./images）")
    ap.add_argument("--image-width", type=float, default=3.0,
                    help="图片最大宽度（英寸，默认 3）")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"错误: 输入文件不存在: {args.input}")
        raise SystemExit(1)
    if not os.path.isdir(args.images_dir):
        print(f"警告: 图片目录不存在: {args.images_dir}（【图片】占位符将保留为文本）")

    missing = convert(args.input, args.output, args.images_dir, args.image_width)
    if missing:
        print("已生成文档，但以下图片占位符未能嵌入真实图片（已保留占位符文本）：")
        for m in missing:
            print(f"  - {m}")
    else:
        print(f"已生成: {args.output}")


if __name__ == "__main__":
    main()
