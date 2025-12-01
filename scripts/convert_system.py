#!/usr/bin/env python3
"""
Convert SVG to WebP using system rsvg-convert with an optional cairosvg fallback
for huge/base64-heavy files that rsvg-convert sometimes fails to parse.
"""

import argparse
import io
import subprocess
import sys
from pathlib import Path
from typing import Literal
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

try:
    import cairosvg

    CAIRO_AVAILABLE = True
except Exception:
    CAIRO_AVAILABLE = False


def convert_using_system_tool(
    svg_path: Path,
    width: int = 1920,
    quality: int = 80,
    keep_original: bool = True,
) -> bool:
    """Convert via system rsvg-convert -> PNG -> WebP. Returns True on success."""
    output_path = svg_path.with_suffix(".webp")
    temp_png = svg_path.with_suffix(".tmp.png")

    try:
        cmd = [
            "rsvg-convert",
            "-w",
            str(width),
            "--keep-aspect-ratio",
            "-o",
            str(temp_png),
            str(svg_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"!! rsvg-convert error: {result.stderr.strip()}")
            return False

        if not temp_png.exists():
            print(f"!! PNG not produced for {svg_path.name}")
            return False

        img = Image.open(temp_png)
        img.save(output_path, "WEBP", quality=quality, method=6)
        temp_png.unlink()

        orig_size = svg_path.stat().st_size
        new_size = output_path.stat().st_size
        reduction = (1 - new_size / orig_size) * 100

        print(f"✔ {svg_path.name} (rsvg-convert)")
        print(f"   {orig_size/1024/1024:.2f}MB -> {new_size/1024:.0f}KB (−{reduction:.0f}%)")

        if not keep_original:
            svg_path.unlink()

        return True

    except FileNotFoundError:
        print("!! rsvg-convert not found. Install librsvg2-bin.")
        sys.exit(1)
    except Exception as e:
        print(f"!! Unexpected error {svg_path.name}: {e}")
        if temp_png.exists():
            temp_png.unlink()
        return False


def convert_using_cairosvg(
    svg_path: Path,
    width: int = 1920,
    quality: int = 80,
    keep_original: bool = True,
) -> bool:
    """Convert using cairosvg in-process. Helps with huge base64-heavy SVGs."""
    if not CAIRO_AVAILABLE:
        print("!! cairosvg is not installed. pip install cairosvg pillow")
        return False

    try:
        svg_bytes = svg_path.read_bytes()
        png_bytes = cairosvg.svg2png(
            bytestring=svg_bytes,
            url=svg_path.as_uri(),
            output_width=width,
        )

        image = Image.open(io.BytesIO(png_bytes))
        output_path = svg_path.with_suffix(".webp")
        image.save(output_path, "WEBP", quality=quality, method=6)

        orig_size = svg_path.stat().st_size
        new_size = output_path.stat().st_size
        reduction = (1 - new_size / orig_size) * 100

        print(f"✔ {svg_path.name} (cairosvg)")
        print(f"   {orig_size/1024/1024:.2f}MB -> {new_size/1024:.0f}KB (−{reduction:.0f}%)")

        if not keep_original:
            svg_path.unlink()

        return True

    except Exception as e:
        print(f"!! cairosvg error {svg_path.name}: {e}")
        return False


def convert_using_resvg(
    svg_path: Path,
    width: int = 1920,
    quality: int = 80,
    keep_original: bool = True,
) -> bool:
    """
    Convert using resvg CLI -> PNG -> WebP. Usually keeps layer order intact.
    """
    output_path = svg_path.with_suffix(".webp")
    temp_png = svg_path.with_suffix(".tmp.png")

    try:
        cmd = [
            "resvg",
            "--width",
            str(width),
            str(svg_path),
            str(temp_png),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"!! resvg error: {result.stderr.strip()}")
            return False

        if not temp_png.exists():
            print(f"!! PNG not produced for {svg_path.name}")
            return False

        img = Image.open(temp_png)
        img.save(output_path, "WEBP", quality=quality, method=6)
        temp_png.unlink()

        orig_size = svg_path.stat().st_size
        new_size = output_path.stat().st_size
        reduction = (1 - new_size / orig_size) * 100

        print(f"✔ {svg_path.name} (resvg)")
        print(f"   {orig_size/1024/1024:.2f}MB -> {new_size/1024:.0f}KB (−{reduction:.0f}%)")

        if not keep_original:
            svg_path.unlink()

        return True

    except FileNotFoundError:
        print("!! resvg not found. Install resvg CLI (cargo install resvg or use binary).")
        return False
    except Exception as e:
        print(f"!! resvg unexpected error {svg_path.name}: {e}")
        if temp_png.exists():
            temp_png.unlink()
        return False


def convert_svg(
    svg_path: Path,
    engine: Literal["rsvg", "resvg", "cairosvg", "auto"] = "auto",
    width: int = 1920,
    quality: int = 80,
    keep_original: bool = True,
) -> bool:
    """Try chosen engine; with 'auto' fallback chain rsvg -> resvg -> cairosvg."""
    if engine == "rsvg":
        return convert_using_system_tool(svg_path, width, quality, keep_original)
    if engine == "resvg":
        return convert_using_resvg(svg_path, width, quality, keep_original)
    if engine == "cairosvg":
        return convert_using_cairosvg(svg_path, width, quality, keep_original)

    # auto: prefer rsvg (fast), then resvg (robust), then cairosvg.
    if convert_using_system_tool(svg_path, width, quality, keep_original):
        return True
    if convert_using_resvg(svg_path, width, quality, keep_original):
        return True
    return convert_using_cairosvg(svg_path, width, quality, keep_original)


def main():
    parser = argparse.ArgumentParser(description="Convert SVG to WebP")
    parser.add_argument("path", type=str)
    parser.add_argument("-r", "--recursive", action="store_true")
    parser.add_argument("--delete-original", action="store_true")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--quality", type=int, default=80)
    parser.add_argument(
        "--engine",
        choices=["auto", "rsvg", "resvg", "cairosvg"],
        default="auto",
        help="Conversion backend. auto = rsvg -> resvg -> cairosvg.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel workers (per-file). 1 = sequential.",
    )

    args = parser.parse_args()
    path = Path(args.path)

    if not path.exists():
        sys.exit("Path not found")

    if path.is_file():
        files = [path]
    else:
        pattern = "**/*.svg" if args.recursive else "*.svg"
        files = list(path.glob(pattern))

    print(f"→ Found files: {len(files)}")
    print(f"Using engine: {args.engine}\n")

    success = 0
    if args.workers > 1 and len(files) > 1:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [
                executor.submit(
                    convert_svg,
                    f,
                    engine=args.engine,
                    width=args.width,
                    quality=args.quality,
                    keep_original=not args.delete_original,
                )
                for f in files
            ]
            for fut in as_completed(futures):
                if fut.result():
                    success += 1
    else:
        for f in files:
            if convert_svg(
                f,
                engine=args.engine,
                width=args.width,
                quality=args.quality,
                keep_original=not args.delete_original,
            ):
                success += 1

    print(f"\nDone: {success}/{len(files)}")


if __name__ == "__main__":
    main()
