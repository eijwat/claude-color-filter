"""
Claude Orange Color Filter Tool
================================
GoogleNetの猫ニューロン再構成画像などにClaudeブランドカラー（オレンジ系）の
フィルターを適用するツール。

Usage:
    python claude_orange_filter.py input_image.png
    python claude_orange_filter.py input_image.png --output_dir ./my_output
    python claude_orange_filter.py input_image.png --filters tint_light duo_dark soft_strong
    python claude_orange_filter.py --list   # フィルター一覧表示

Requires: pip install numpy Pillow
"""

import argparse
import numpy as np
from PIL import Image, ImageEnhance
import os
import sys

# === Claude Brand Colors ===
CLAUDE = {
    "dark":       (0x14, 0x14, 0x13),  # #141413
    "light":      (0xfa, 0xf9, 0xf5),  # #faf9f5
    "mid_gray":   (0xb0, 0xae, 0xa5),  # #b0aea5
    "light_gray": (0xe8, 0xe6, 0xdc),  # #e8e6dc
    "orange":     (0xd9, 0x77, 0x57),  # #d97757 (primary)
    "blue":       (0x6a, 0x9b, 0xcc),  # #6a9bcc
    "green":      (0x78, 0x8c, 0x5d),  # #788c5d
}


# ============================================================
#  Blend functions
# ============================================================

def color_tint(img, color, strength):
    """半透明カラーオーバーレイ"""
    overlay = Image.new("RGB", img.size, color)
    return Image.blend(img, overlay, strength)


def duotone(img, shadow, highlight):
    """暗部→明部を2色にマッピング"""
    gray = np.array(img.convert("L"), dtype=np.float32) / 255.0
    s, h = np.array(shadow, np.float32), np.array(highlight, np.float32)
    out = np.stack([s[c] * (1 - gray) + h[c] * gray for c in range(3)], axis=-1)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def tritone(img, shadow, mid, highlight):
    """暗部→中間→明部を3色にマッピング"""
    gray = np.array(img.convert("L"), dtype=np.float32) / 255.0
    s, m, h = [np.array(x, np.float32) for x in (shadow, mid, highlight)]
    out = np.zeros((*gray.shape, 3), np.float32)
    for c in range(3):
        lo = np.where(gray < 0.5, s[c] * (1 - gray * 2) + m[c] * gray * 2, 0)
        hi = np.where(gray >= 0.5, m[c] * (1 - (gray - 0.5) * 2) + h[c] * (gray - 0.5) * 2, 0)
        out[:, :, c] = lo + hi
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def soft_light(img, color, strength):
    """ソフトライトブレンド — ディテールを残しつつ色を乗せる"""
    a = np.array(img, np.float32) / 255.0
    c = np.array(color, np.float32) / 255.0
    bl = np.where(c < 0.5,
                  2 * a * c + a * a * (1 - 2 * c),
                  2 * a * (1 - c) + np.sqrt(a) * (2 * c - 1))
    out = a * (1 - strength) + bl * strength
    return Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8))


def multiply_blend(img, color, strength):
    """乗算ブレンド — 影を深くする"""
    a = np.array(img, np.float32) / 255.0
    c = np.array(color, np.float32) / 255.0
    out = a * (1 - strength) + (a * c) * strength
    return Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8))


def screen_blend(img, color, strength):
    """スクリーンブレンド — 明るく浮遊感"""
    a = np.array(img, np.float32) / 255.0
    c = np.array(color, np.float32) / 255.0
    out = a * (1 - strength) + (1 - (1 - a) * (1 - c)) * strength
    return Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8))


# ============================================================
#  Filter registry
# ============================================================

C = CLAUDE  # shorthand

FILTERS = {
    # --- Tint ---
    "tint_light":    ("Tint: Orange 15%",
        lambda img: color_tint(img, C["orange"], 0.15)),
    "tint_medium":   ("Tint: Orange 25%",
        lambda img: color_tint(img, C["orange"], 0.25)),
    "tint_strong":   ("Tint: Orange 40% + contrast",
        lambda img: ImageEnhance.Contrast(color_tint(img, C["orange"], 0.40)).enhance(1.15)),
    "tint_blue":     ("Tint: Blue 25%",
        lambda img: color_tint(img, C["blue"], 0.25)),
    "tint_green":    ("Tint: Green 25%",
        lambda img: color_tint(img, C["green"], 0.25)),
    "tint_pampas":   ("Tint: Pampas 30%",
        lambda img: color_tint(img, C["light_gray"], 0.30)),

    # --- Duotone ---
    "duo_dark":      ("Duo: Dark → Orange",
        lambda img: duotone(img, C["dark"], C["orange"])),
    "duo_blue":      ("Duo: Blue → Orange",
        lambda img: duotone(img, C["blue"], C["orange"])),
    "duo_green":     ("Duo: Green → Orange",
        lambda img: duotone(img, C["green"], C["orange"])),
    "duo_light":     ("Duo: Orange → Light",
        lambda img: duotone(img, C["orange"], C["light"])),
    "duo_dark_blue": ("Duo: Dark → Blue",
        lambda img: duotone(img, C["dark"], C["blue"])),
    "duo_contrast":  ("Duo: Dark → Orange + contrast",
        lambda img: ImageEnhance.Contrast(duotone(img, C["dark"], C["orange"])).enhance(1.3)),

    # --- Soft Light ---
    "soft_mild":     ("Soft: Orange 35%",
        lambda img: soft_light(img, C["orange"], 0.35)),
    "soft_medium":   ("Soft: Orange 50%",
        lambda img: soft_light(img, C["orange"], 0.50)),
    "soft_strong":   ("Soft: Orange 75%",
        lambda img: soft_light(img, C["orange"], 0.75)),
    "soft_blue":     ("Soft: Blue 50%",
        lambda img: soft_light(img, C["blue"], 0.50)),
    "soft_green":    ("Soft: Green 50%",
        lambda img: soft_light(img, C["green"], 0.50)),

    # --- Multiply / Screen ---
    "mult_orange":   ("Multiply: Orange 40%",
        lambda img: multiply_blend(img, C["orange"], 0.40)),
    "screen_orange": ("Screen: Orange 40%",
        lambda img: screen_blend(img, C["orange"], 0.40)),

    # --- Tritone ---
    "tri_classic":   ("Tri: Dark → Orange → Light",
        lambda img: tritone(img, C["dark"], C["orange"], C["light"])),
    "tri_cool":      ("Tri: Blue → Orange → Light",
        lambda img: tritone(img, C["blue"], C["orange"], C["light"])),
    "tri_earth":     ("Tri: Green → Orange → Light",
        lambda img: tritone(img, C["green"], C["orange"], C["light"])),

    # --- Combo ---
    "combo_warm":    ("Combo: Soft Orange + Blue Tint",
        lambda img: color_tint(soft_light(img, C["orange"], 0.4), C["blue"], 0.12)),
    "combo_screen":  ("Combo: Screen Orange + Soft Blue",
        lambda img: soft_light(screen_blend(img, C["orange"], 0.3), C["blue"], 0.25)),
}


# ============================================================
#  Main
# ============================================================

def list_filters():
    print("Available filters:")
    print("-" * 50)
    for key, (label, _) in FILTERS.items():
        print(f"  {key:20s}  {label}")
    print(f"\nTotal: {len(FILTERS)} filters")
    print(f"\nUsage: python {os.path.basename(__file__)} image.png --filters duo_dark soft_medium")


def main():
    parser = argparse.ArgumentParser(
        description="Claude Orange Color Filter Tool")
    parser.add_argument("input", nargs="?", help="Input image path")
    parser.add_argument("--output_dir", "-o", default="./output",
                        help="Output directory (default: ./output)")
    parser.add_argument("--filters", "-f", nargs="*", default=None,
                        help="Filter names to apply (default: all)")
    parser.add_argument("--list", "-l", action="store_true",
                        help="List available filters")
    args = parser.parse_args()

    if args.list:
        list_filters()
        return

    if not args.input:
        parser.print_help()
        return

    if not os.path.exists(args.input):
        print(f"Error: {args.input} not found")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    img = Image.open(args.input).convert("RGB")
    basename = os.path.splitext(os.path.basename(args.input))[0]

    # Select filters
    if args.filters:
        selected = {}
        for k in args.filters:
            if k in FILTERS:
                selected[k] = FILTERS[k]
            else:
                print(f"Warning: unknown filter '{k}', skipping")
        if not selected:
            print("No valid filters selected. Use --list to see options.")
            sys.exit(1)
    else:
        selected = FILTERS

    # Apply
    print(f"Input:  {args.input}")
    print(f"Output: {args.output_dir}/")
    print(f"Filters: {len(selected)}")
    print("-" * 50)

    for key, (label, fn) in selected.items():
        out = fn(img)
        out_path = os.path.join(args.output_dir, f"{basename}_{key}.png")
        out.save(out_path)
        print(f"  ✓ {label:40s} → {out_path}")

    print(f"\nDone! {len(selected)} images saved to {args.output_dir}/")


if __name__ == "__main__":
    main()
