#!/usr/bin/env python3
"""
conv - local file converter
usage:
  conv <input> [output]
  conv merge out.pdf a.pdf b.pdf ...
  conv split input.pdf [out_dir]

if output is omitted, a sensible default is chosen based on input type.
multiple images can be passed with the output pdf last: conv *.png out.pdf
"""

import sys
import os
import subprocess
import tempfile
from pathlib import Path


def err(msg):
    print(f"\033[31m[conv] error:\033[0m {msg}", file=sys.stderr)
    sys.exit(1)

def ok(msg):
    print(f"\033[32m[conv]\033[0m {msg}")

def info(msg):
    print(f"\033[34m[conv]\033[0m {msg}")


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif"}


def images_to_pdf(inputs, output):
    cmd = ["img2pdf"] + [str(p) for p in inputs] + ["-o", str(output)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        err(r.stderr.decode())
    ok(f"→ {output}  ({output.stat().st_size // 1024} KB)")


def pdf_to_images(src, output_prefix, fmt="png", dpi=150):
    out = str(output_prefix.parent / f"{output_prefix.stem}-%04d.{fmt}")
    cmd = ["convert", f"-density", str(dpi), str(src), out]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        err(r.stderr.decode())
    files = sorted(output_prefix.parent.glob(f"{output_prefix.stem}-*.{fmt}"))
    ok(f"→ {len(files)} image(s) in {output_prefix.parent}/")


def pdf_to_text(src, dst):
    cmd = ["pdftotext", "-layout", str(src), str(dst)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        err(r.stderr.decode())
    ok(f"→ {dst}")


def pdf_to_docx(src, dst):
    try:
        from pdf2docx import Converter
        cv = Converter(str(src))
        cv.convert(str(dst), multi_processing=False)
        cv.close()
        ok(f"→ {dst}")
    except ImportError:
        err("pdf2docx not installed. run: pip install pdf2docx --break-system-packages")


def merge_pdfs(inputs, output):
    from pypdf import PdfWriter, PdfReader
    writer = PdfWriter()
    total = 0
    for p in inputs:
        reader = PdfReader(str(p))
        for page in reader.pages:
            writer.add_page(page)
        total += len(reader.pages)
    with open(output, "wb") as f:
        writer.write(f)
    ok(f"→ {output}  ({total} pages)")


def split_pdf(src, out_dir):
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(str(src))
    out_dir.mkdir(exist_ok=True)
    for i, page in enumerate(reader.pages):
        writer = PdfWriter()
        writer.add_page(page)
        out = out_dir / f"{src.stem}_page_{i+1:04d}.pdf"
        with open(out, "wb") as f:
            writer.write(f)
    ok(f"→ {len(reader.pages)} pages in {out_dir}/")


def libreoffice_convert(src, dst, fmt):
    cmd = ["libreoffice", "--headless", "--convert-to", fmt,
           "--outdir", str(dst.parent), str(src)]
    r = subprocess.run(cmd, capture_output=True)
    generated = dst.parent / (src.stem + f".{fmt}")
    if r.returncode != 0 or not generated.exists():
        err(r.stderr.decode() or f"libreoffice failed ({src.suffix} → .{fmt})")
    if generated != dst:
        generated.rename(dst)
    ok(f"→ {dst}")


def html_to_pdf(src, dst):
    cmd = ["wkhtmltopdf", "--quiet", str(src), str(dst)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        err(r.stderr.decode())
    ok(f"→ {dst}")


def pandoc_convert(src, dst, extra=None):
    cmd = ["pandoc", str(src), "-o", str(dst)]
    if extra:
        cmd += extra
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        err(r.stderr.decode())
    ok(f"→ {dst}")


def txt_to_pdf(src, dst):
    content = src.read_text(errors="replace").replace("&", "&amp;").replace("<", "&lt;")
    html = (
        "<html><body>"
        "<pre style='font-family:monospace;font-size:13px;white-space:pre-wrap'>"
        f"{content}</pre></body></html>"
    )
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as tmp:
        tmp.write(html)
        tmp_path = Path(tmp.name)
    try:
        html_to_pdf(tmp_path, dst)
    finally:
        tmp_path.unlink(missing_ok=True)


def convert(src, dst):
    se = src.suffix.lower()
    de = dst.suffix.lower()

    # images → pdf
    if se in IMAGE_EXTS and de == ".pdf":
        images_to_pdf([src], dst)

    # pdf → image
    elif se == ".pdf" and de in {".png", ".jpg", ".jpeg"}:
        pdf_to_images(src, dst.parent / dst.stem, fmt=de.lstrip("."))

    # pdf → text
    elif se == ".pdf" and de == ".txt":
        pdf_to_text(src, dst)

    # pdf → docx
    elif se == ".pdf" and de == ".docx":
        pdf_to_docx(src, dst)

    # pdf → html
    elif se == ".pdf" and de == ".html":
        pandoc_convert(src, dst)

    # docx → pdf
    elif se == ".docx" and de == ".pdf":
        libreoffice_convert(src, dst, "pdf")

    # docx → txt / md
    elif se == ".docx" and de in {".txt", ".md"}:
        pandoc_convert(src, dst)

    # pptx/ppt → pdf
    elif se in {".pptx", ".ppt"} and de == ".pdf":
        libreoffice_convert(src, dst, "pdf")

    # pptx/ppt → images (pdf intermediate)
    elif se in {".pptx", ".ppt"} and de in {".png", ".jpg", ".jpeg"}:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir=dst.parent) as tmp:
            tmp_path = Path(tmp.name)
        try:
            libreoffice_convert(src, tmp_path, "pdf")
            pdf_to_images(tmp_path, dst.parent / dst.stem, fmt=de.lstrip("."))
        finally:
            tmp_path.unlink(missing_ok=True)

    # pptx/ppt → txt
    elif se in {".pptx", ".ppt"} and de == ".txt":
        pandoc_convert(src, dst)

    # markdown → pdf (md → html → pdf, avoids needing latex)
    elif se == ".md" and de == ".pdf":
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            pandoc_convert(src, tmp_path)
            html_to_pdf(tmp_path, dst)
        finally:
            tmp_path.unlink(missing_ok=True)

    # markdown → html / docx
    elif se == ".md" and de in {".html", ".docx"}:
        pandoc_convert(src, dst)

    # html → pdf
    elif se in {".html", ".htm"} and de == ".pdf":
        html_to_pdf(src, dst)

    # html → md / docx / txt
    elif se in {".html", ".htm"} and de in {".md", ".docx", ".txt"}:
        pandoc_convert(src, dst)

    # txt → pdf
    elif se == ".txt" and de == ".pdf":
        txt_to_pdf(src, dst)

    # txt → md / html
    elif se == ".txt" and de in {".md", ".html"}:
        pandoc_convert(src, dst)

    else:
        err(
            f"no conversion path for {se} → {de}\n"
            "supported: images, pdf, docx, pptx/ppt, md, html, txt"
        )


def infer_output(src):
    se = src.suffix.lower()
    defaults = {
        **{ext: ".pdf" for ext in IMAGE_EXTS},
        ".pdf": ".txt",
        ".docx": ".pdf",
        ".pptx": ".pdf",
        ".ppt": ".pdf",
        ".md": ".html",
        ".html": ".pdf",
        ".htm": ".pdf",
        ".txt": ".pdf",
    }
    target = defaults.get(se)
    if not target:
        err(f"can't guess output format for {se}. specify an output file.")
    return src.parent / (src.stem + target)


def main():
    args = sys.argv[1:]

    if not args or args[0] in {"-h", "--help", "help"}:
        print(__doc__)
        sys.exit(0)

    # merge
    if args[0] == "merge":
        if len(args) < 3:
            err("usage: conv merge output.pdf file1.pdf file2.pdf ...")
        output = Path(args[1])
        inputs = [Path(a) for a in args[2:]]
        for p in inputs:
            if not p.exists():
                err(f"not found: {p}")
        info(f"merging {len(inputs)} files...")
        merge_pdfs(inputs, output)
        return

    # split
    if args[0] == "split":
        if len(args) < 2:
            err("usage: conv split input.pdf [out_dir]")
        src = Path(args[1])
        if not src.exists():
            err(f"not found: {src}")
        out_dir = Path(args[2]) if len(args) > 2 else src.parent / (src.stem + "_split")
        info(f"splitting {src.name}...")
        split_pdf(src, out_dir)
        return

    # multiple images → single pdf
    if len(args) >= 3 and Path(args[-1]).suffix.lower() == ".pdf":
        inputs = [Path(a) for a in args[:-1]]
        if all(p.suffix.lower() in IMAGE_EXTS for p in inputs):
            output = Path(args[-1])
            for p in inputs:
                if not p.exists():
                    err(f"not found: {p}")
            info(f"combining {len(inputs)} images → {output.name}")
            images_to_pdf(inputs, output)
            return

    # single file, no output specified
    if len(args) == 1:
        src = Path(args[0])
        if not src.exists():
            err(f"not found: {src}")
        dst = infer_output(src)
        info(f"{src.name} → {dst.name}")
        convert(src, dst)

    # single file with output
    elif len(args) == 2:
        src = Path(args[0])
        dst = Path(args[1])
        if not src.exists():
            err(f"not found: {src}")
        info(f"{src.name} → {dst.name}")
        convert(src, dst)

    else:
        err("too many arguments. run conv --help")


if __name__ == "__main__":
    main()
