#!/usr/bin/env python3
"""
Generate all icon sizes from logo.png.

Requirements:
    pip install Pillow

Usage:
    python3 resize_icons.py

Input:  logo.png  (place in project root, transparent background, ideally 1024×1024)
Output: icon-32.png      – Favicon
        icon-180.png     – Apple Touch Icon (iOS home screen)
        icon-192.png     – PWA / Android icon
        icon-512.png     – PWA splash / large icon
        social.png       – GitHub Social Preview + og:image (1280×640)

Then rebuild the app:
    python3 build_crowtalk.py
"""

import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image, ImageDraw

SRC = os.path.join(os.path.dirname(__file__), "logo.png")

if not os.path.exists(SRC):
    print("❌  logo.png not found – place your logo in the project root first.")
    sys.exit(1)

def remove_checkerboard_bg(img, threshold=40):
    """
    Remove the baked-in checkered background from an image.
    Detects background by flood-filling from all four corners,
    then makes those pixels transparent.
    """
    img = img.convert("RGBA")
    w, h = img.size
    pixels = img.load()

    def similar(p1, p2, t):
        return all(abs(int(p1[i]) - int(p2[i])) <= t for i in range(3))

    # Collect seed background colors from corners
    corner_colors = [pixels[0,0], pixels[w-1,0], pixels[0,h-1], pixels[w-1,h-1]]

    # Mark background pixels using flood fill from edges
    from collections import deque
    visited = [[False]*h for _ in range(w)]
    queue = deque()
    seeds = [(0,0),(w-1,0),(0,h-1),(w-1,h-1)]
    for sx, sy in seeds:
        if not visited[sx][sy]:
            queue.append((sx, sy))
            visited[sx][sy] = True

    bg_color = pixels[0, 0]  # representative background color

    while queue:
        x, y = queue.popleft()
        p = pixels[x, y]
        if not similar(p, bg_color, threshold):
            # Try other corner colors
            if not any(similar(p, c, threshold) for c in corner_colors):
                continue
        # Mark as background
        pixels[x, y] = (p[0], p[1], p[2], 0)
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = x+dx, y+dy
            if 0 <= nx < w and 0 <= ny < h and not visited[nx][ny]:
                visited[nx][ny] = True
                queue.append((nx, ny))

    return img

src_raw = Image.open(SRC).convert("RGBA")
print(f"✓  Loaded logo.png  ({src_raw.width}×{src_raw.height})")

# Check if image has real transparency or baked-in checkerboard
corner_alpha = src_raw.getpixel((0, 0))[3]
if corner_alpha == 255:
    print("  Removing baked-in background...")
    src = remove_checkerboard_bg(src_raw)
    print("  Background removed.")
else:
    src = src_raw

def save_square(size, filename):
    """Resize to square, compositing on dark background for opaque output."""
    img = src.copy()
    # Crop to actual content (removes transparent borders from landscape source)
    bb = img.getbbox()
    if bb:
        img = img.crop(bb)
    img.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - img.width) // 2
    y = (size - img.height) // 2
    canvas.paste(img, (x, y), img)
    # Flatten onto dark background for PNG without transparency (required by some platforms)
    bg = Image.new("RGB", (size, size), (7, 9, 10))  # --bg color
    bg.paste(canvas, mask=canvas.split()[3])
    out = os.path.join(os.path.dirname(__file__), filename)
    bg.save(out, "PNG", optimize=True)
    print(f"  → {filename}  ({size}×{size})")

def save_social(filename="social.png"):
    """
    1280×640 landscape card for GitHub Social Preview and og:image.
    Logo left-center, right side has app name + tagline.
    Dark background matching app theme.
    """
    W, H = 1280, 640
    card = Image.new("RGB", (W, H), (7, 9, 10))

    # Logo on left (centered vertically, 480px tall max)
    logo_size = 480
    logo = src.copy()
    logo.thumbnail((logo_size, logo_size), Image.LANCZOS)
    lx = 100
    ly = (H - logo.height) // 2
    card.paste(logo, (lx, ly), logo)

    # Right-side text via ImageDraw (no font dependency – use default)
    try:
        from PIL import ImageFont
        # Try to load a nice system font, fall back to default
        try:
            font_lg = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 80)
            font_sm = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",  32)
        except Exception:
            font_lg = ImageFont.load_default()
            font_sm = ImageFont.load_default()
    except Exception:
        font_lg = None
        font_sm = None

    draw = ImageDraw.Draw(card)
    tx = lx + logo_size + 80
    ty_title = H // 2 - 80

    if font_lg:
        draw.text((tx, ty_title),      "CrowTalk",                 fill=(232,237,240), font=font_lg)
        draw.text((tx, ty_title + 100),"Study · Record · Communicate", fill=(143,160,172), font=font_sm)
        draw.text((tx, ty_title + 145),"Hooded Crow field tool",   fill=(85,96,112),   font=font_sm)
    else:
        draw.text((tx, ty_title),      "CrowTalk",                 fill=(232,237,240))
        draw.text((tx, ty_title + 40), "Study · Record · Communicate", fill=(143,160,172))

    out = os.path.join(os.path.dirname(__file__), filename)
    card.save(out, "PNG", optimize=True)
    print(f"  → {filename}  (1280×640)  ← upload to GitHub → Settings → Social Preview")

# --- Generate all sizes ---
print("\nGenerating icons...")
save_square(32,  "icon-32.png")
save_square(180, "icon-180.png")
save_square(192, "icon-192.png")
save_square(512, "icon-512.png")
save_social("social.png")

print("""
Done! Next steps:
  1. python3 build_crowtalk.py        ← rebuilds app with embedded icons
  2. GitHub → Settings → General
     → Social Preview → Upload image → select social.png
  3. Commit all new .png files to the repo
""")
