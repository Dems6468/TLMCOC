#!/usr/bin/env python3
"""
merge_portraits.py

Composites each champion's face PNG with its star-rank border (top + bottom
caps) into one final portrait PNG. Reads YOUR real export format directly:

  data/champions_source.json
    [
      {
        "nom": "Abomination",
        "Short Name": "Abomination",
        "classe": "Science",
        "photo": "faces/portrait_abominationed8d.png",
        ... (buff, immunite, description, photos -- all ignored by this tool,
             kept only if you want them for something else later)
      },
      ...
    ]

  Also accepts the older {"champions": [...]} wrapper with "name"/"class"/
  "face" keys if you still have data in that shape -- both are auto-detected.

Image paths (the "photo" field, e.g. "faces/portrait_xxx.png") are resolved
relative to the repo root, so your existing faces/ folder sits right at the
top level, unchanged:
  faces/portrait_xxx.png   <-  matches "faces/portrait_xxx.png" in the JSON

BORDERS:
  borders/<star>star_top.png
  borders/<star>star_bottom.png
  (falls back to 7star_top/bottom.png if a specific star rank's art is missing;
   no "star" field in your JSON yet, so everyone defaults to 7 for now --
   add a "star" key per champion later if you track multiple ranks)

OUTPUT:
  images/champions/<id>.png    <- final composited portrait
  data/champions.json          <- normalized list the website reads
  data/champions.js            <- same data, inline as window.CHAMPIONS_DATA
                                   so the site works via plain file:// too

Usage:
  pip install pillow
  python3 scripts/merge_portraits.py
"""
import json
import re
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE_JSON = ROOT / "data" / "champions_source.json"
BORDERS_DIR = ROOT / "borders"
OUT_DIR = ROOT / "images" / "champions"
FINAL_JSON = ROOT / "data" / "champions.json"
FINAL_JS = ROOT / "data" / "champions.js"

OUT_DIR.mkdir(parents=True, exist_ok=True)

_border_cache = {}


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "champion"


def normalize(raw_list):
    """Accepts your real export (nom/classe/photo/...) and normalizes each
    entry to {id, name, class, star, face}."""
    out = []
    for champ in raw_list:
        name = champ.get("nom") or champ.get("name") or champ.get("Short Name")
        champ_class = champ.get("classe") or champ.get("class")
        photo = champ.get("photo") or champ.get("face")
        star = champ.get("star", 7)
        champ_id = champ.get("id") or slugify(champ.get("Short Name") or name or "")

        if not name or not photo:
            print(f"SKIP entry (missing name or photo field): {champ}")
            continue

        out.append({
            "id": champ_id,
            "name": name,
            "class": champ_class or "Unknown",
            "star": star,
            "face": photo,
        })
    return out


def get_border(star: int, part: str):
    """part is 'top' or 'bottom'. Falls back to 7star if the specific
    star-rank border doesn't exist yet."""
    key = (star, part)
    if key in _border_cache:
        return _border_cache[key]

    candidates = [
        BORDERS_DIR / f"{star}star_{part}.png",
        BORDERS_DIR / f"7star_{part}.png",
    ]
    for c in candidates:
        if c.exists():
            img = Image.open(c).convert("RGBA")
            _border_cache[key] = img
            return img

    _border_cache[key] = None
    return None


def merge_one(champ: dict) -> str:
    face_path = ROOT / champ["face"]
    face = Image.open(face_path).convert("RGBA")

    top = get_border(champ.get("star", 7), "top")
    bottom = get_border(champ.get("star", 7), "bottom")

    canvas = Image.new("RGBA", face.size, (0, 0, 0, 0))
    canvas.alpha_composite(face)
    if top is not None:
        top_resized = top.resize(face.size) if top.size != face.size else top
        canvas.alpha_composite(top_resized)
    if bottom is not None:
        bottom_resized = bottom.resize(face.size) if bottom.size != face.size else bottom
        canvas.alpha_composite(bottom_resized)

    out_path = OUT_DIR / f"{champ['id']}.png"
    canvas.save(out_path)
    return f"images/champions/{champ['id']}.png"


def main():
    if not SOURCE_JSON.exists():
        raise SystemExit(
            f"Missing {SOURCE_JSON}. Run scripts/generate_sample_data.py for a "
            f"demo roster, or drop your real export there (see this file's "
            f"docstring for the expected shape)."
        )

    raw = json.loads(SOURCE_JSON.read_text())
    raw_list = raw["champions"] if isinstance(raw, dict) and "champions" in raw else raw
    source = normalize(raw_list)

    final_list = []
    for champ in source:
        face_path = ROOT / champ["face"]
        if not face_path.exists():
            print(f"SKIP {champ['id']} ({champ['name']}): face file not found at {face_path}")
            continue
        image_path = merge_one(champ)
        final_list.append({
            "id": champ["id"],
            "name": champ["name"],
            "class": champ["class"],
            "star": champ.get("star", 7),
            "image": image_path,
        })

    payload = {"champions": final_list}
    FINAL_JSON.write_text(json.dumps(payload, indent=2))

    js_content = (
        "// Auto-generated by scripts/merge_portraits.py -- do not edit by hand.\n"
        "window.CHAMPIONS_DATA = " + json.dumps(payload, indent=2) + ";\n"
    )
    FINAL_JS.write_text(js_content)

    print(f"Merged {len(final_list)} portraits -> {OUT_DIR}/")
    print(f"Wrote final roster -> {FINAL_JSON}")
    print(f"Wrote inline data -> {FINAL_JS}")


if __name__ == "__main__":
    main()
