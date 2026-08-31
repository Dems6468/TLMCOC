#!/usr/bin/env python3
"""
generate_sample_data.py

Creates FAKE placeholder data so the tier list tool can be tried end-to-end
before you drop in your real MCOC face images + 7-star border assets.

Produces:
  raw/faces/<id>.png                  - placeholder "face" portraits
  raw/borders/7star_top.png           - placeholder top border frame
  raw/borders/7star_bottom.png        - placeholder bottom border frame
  data/champions_source.json          - the "recipe" list (name, class, face file, star)

Run merge_portraits.py afterwards to composite these into final images.

This is throwaway demo data. Delete raw/faces/*.png and replace
data/champions_source.json with your real roster when you're ready.
"""
import json
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FACES_DIR = ROOT / "raw" / "faces"
BORDERS_DIR = ROOT / "raw" / "borders"
DATA_DIR = ROOT / "data"

FACES_DIR.mkdir(parents=True, exist_ok=True)
BORDERS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# The six in-game classes, each with a signature color used for the demo art.
CLASSES = {
    "Cosmic":  "#3E8EDE",
    "Tech":    "#E8C93E",
    "Mutant":  "#E89A3E",
    "Skill":   "#E24C4C",
    "Science": "#4CE28A",
    "Mystic":  "#A24CE2",
}

SIZE = 300  # square face canvas, px

# Made-up placeholder names (NOT real Marvel characters) so the demo data
# doesn't rely on any trademarked names/likenesses. Swap in your real
# roster's names via champions_source.json.
FIRST = ["Nova", "Iron", "Shadow", "Void", "Storm", "Blaze", "Crimson", "Ghost",
         "Titan", "Rogue", "Astra", "Onyx", "Phantom", "Solar", "Frost", "Viper"]
SECOND = ["Warden", "Reaver", "Sentinel", "Wraith", "Fury", "Vanguard", "Strider",
          "Marauder", "Paladin", "Specter", "Rider", "Guard", "Knight", "Runner"]


def make_face(path: Path, label: str, color: str):
    img = Image.new("RGB", (SIZE, SIZE), color)
    draw = ImageDraw.Draw(img)

    # simple diagonal shading so it doesn't look like a flat swatch
    for i in range(0, SIZE, 6):
        draw.line([(i, 0), (0, i)], fill="#00000022", width=2)

    # initials in the middle
    initials = "".join([p[0] for p in label.split()])[:2].upper()
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 110
        )
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), initials, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((SIZE - w) / 2 - bbox[0], (SIZE - h) / 2 - bbox[1]),
        initials, fill="white", font=font
    )
    img.save(path)


def make_border_pieces():
    """A simple gold 7-star style frame, split into a top cap and bottom cap
    (with transparent middles) so merge_portraits.py can layer them over any
    face image regardless of that face's exact crop."""
    gold = (255, 208, 92, 255)
    gold_dark = (168, 122, 30, 255)

    top = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(top)
    d.rectangle([0, 0, SIZE - 1, 14], fill=gold)
    d.rectangle([0, 0, 14, SIZE // 3], fill=gold)
    d.rectangle([SIZE - 15, 0, SIZE - 1, SIZE // 3], fill=gold)
    d.rectangle([0, 12, SIZE - 1, 14], fill=gold_dark)
    # little corner studs
    for x, y in [(0, 0), (SIZE - 24, 0)]:
        d.ellipse([x, y, x + 24, y + 24], fill=gold_dark)
    top.save(BORDERS_DIR / "7star_top.png")

    bottom = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(bottom)
    d.rectangle([0, SIZE - 15, SIZE - 1, SIZE - 1], fill=gold)
    d.rectangle([0, 2 * SIZE // 3, 14, SIZE - 1], fill=gold)
    d.rectangle([SIZE - 15, 2 * SIZE // 3, SIZE - 1, SIZE - 1], fill=gold)
    d.rectangle([0, SIZE - 15, SIZE - 1, SIZE - 13], fill=gold_dark)
    for x, y in [(0, SIZE - 24), (SIZE - 24, SIZE - 24)]:
        d.ellipse([x, y, x + 24, y + 24], fill=gold_dark)
    bottom.save(BORDERS_DIR / "7star_bottom.png")


def main(n=18, seed=42):
    random.seed(seed)
    make_border_pieces()

    used_names = set()
    champions = []
    class_names = list(CLASSES.keys())

    for i in range(n):
        while True:
            name = f"{random.choice(FIRST)} {random.choice(SECOND)}"
            if name not in used_names:
                used_names.add(name)
                break
        champ_class = class_names[i % len(class_names)]
        color = CLASSES[champ_class]
        champ_id = f"champ_{i+1:03d}"
        face_file = f"{champ_id}.png"
        make_face(FACES_DIR / face_file, name, color)

        champions.append({
            "id": champ_id,
            "name": name,
            "class": champ_class,
            "star": random.choice([6, 6, 7, 7, 7]),  # mostly 7* like real rosters
            "face": f"raw/faces/{face_file}",
        })

    out = DATA_DIR / "champions_source.json"
    out.write_text(json.dumps({"champions": champions}, indent=2))
    print(f"Generated {n} placeholder champions -> {out}")
    print("Next: run scripts/merge_portraits.py to composite final images.")


if __name__ == "__main__":
    main()
