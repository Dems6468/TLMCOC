#!/usr/bin/env python3
"""
merge_portraits.py

Composites each champion's face PNG with its star-rank border into one
final portrait PNG. Reads YOUR real export format directly:

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

BORDERS -- two ways, tried in this order:

  1) Proper depth (recommended, gives the "popping out of the frame" look):
     borders/<star>star_back.png   <- behind the face (top bar + side columns)
     borders/<star>star_front.png  <- in front of the face (bottom shelf/base)
     Export both at the EXACT same pixel size as your face images -- no
     auto-crop/resize is applied to these, so mismatched sizes will distort.

  2) Legacy single overlay (flat, no pop-out effect):
     borders/<star>star_frame.png  <- one file, transparent hole in the middle
     (auto-cropped to its own artwork bounding box, then stretched to fit
     the face canvas)

  Also supports the older two-file borders/<star>star_top.png +
  <star>star_bottom.png (both drawn in FRONT of the face) as a last resort.

  All of the above fall back to the 7-star version if a specific star
  rank's art is missing. No "star" field in your JSON yet, so everyone
  defaults to 7 for now -- add a "star" key per champion later if you
  track multiple ranks.

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
    out = []
    seen_ids = set()
    for champ in raw_list:
        name = champ.get("nom") or champ.get("name") or champ.get("Short Name")
        champ_class = champ.get("classe") or champ.get("class")
        photo = champ.get("photo") or champ.get("face")
        star = champ.get("star", 7)

        if not name or not photo:
            print(f"SKIP entry (missing name or photo field): {champ}")
            continue

        base_id = champ.get("id") or slugify(name)
        champ_id = base_id
        n = 2
        while champ_id in seen_ids:
            champ_id = f"{base_id}_{n}"
            n += 1
        seen_ids.add(champ_id)

        out.append({
            "id": champ_id,
            "name": name,
            "class": champ_class or "Unknown",
            "star": star,
            "face": photo,
        })
    return out


def _load_and_crop(path: Path):
    img = Image.open(path).convert("RGBA")
    bbox = img.getbbox()
    if bbox is not None:
        img = img.crop(bbox)
    return img


def get_layer(star: int, kind: str):
    """kind is 'back' (behind the face -- top bar + side columns) or
    'front' (in front of the face -- the bottom shelf/base). Falls back to
    7star if the specific star rank's art is missing. Loaded as-is (no
    auto-crop) -- export these at the exact same canvas size as your face
    images so nothing gets stretched out of position."""
    key = (kind, star)
    if key in _border_cache:
        return _border_cache[key]
    candidates = [
        BORDERS_DIR / f"{star}star_{kind}.png",
        BORDERS_DIR / f"7star_{kind}.png",
    ]
    for c in candidates:
        if c.exists():
            img = Image.open(c).convert("RGBA")
            _border_cache[key] = img
            return img
    _border_cache[key] = None
    return None


def get_frame(star: int):
    """Legacy single full-canvas overlay (frame sits entirely in FRONT of
    the face, no pop-out effect). Used only if back/front pieces aren't
    found -- see get_layer() for the preferred two-piece setup."""
    key = ("frame", star)
    if key in _border_cache:
        return _border_cache[key]
    candidates = [
        BORDERS_DIR / f"{star}star_frame.png",
        BORDERS_DIR / "7star_frame.png",
    ]
    for c in candidates:
        if c.exists():
            img = _load_and_crop(c)
            _border_cache[key] = img
            return img
    _border_cache[key] = None
    return None


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
    star = champ.get("star", 7)
    size = face.size

    canvas = Image.new("RGBA", size, (0, 0, 0, 0))

    back = get_layer(star, "back")
    front = get_layer(star, "front")

    if back is not None or front is not None:
        # Preferred: proper depth. Back frame elements first (behind the
        # face), then the face, then the front shelf/base on top (in
        # front of the face) -- this is what makes the character look
        # like it's popping out of the top of the frame while still
        # being cropped by the bottom shelf.
        if back is not None:
            back_resized = back.resize(size) if back.size != size else back
            canvas.alpha_composite(back_resized)
        canvas.alpha_composite(face)
        if front is not None:
            front_resized = front.resize(size) if front.size != size else front
            canvas.alpha_composite(front_resized)
    else:
        canvas.alpha_composite(face)
        frame = get_frame(star)
        if frame is not None:
            # Legacy: single overlay entirely in front of the face (flat
            # look, no pop-out effect).
            frame_resized = frame.resize(size) if frame.size != size else frame
            canvas.alpha_composite(frame_resized)
        else:
            # Older two-file top/bottom setup, also entirely in front.
            top = get_border(star, "top")
            bottom = get_border(star, "bottom")
            if top is not None:
                top_resized = top.resize(size) if top.size != size else top
                canvas.alpha_composite(top_resized)
            if bottom is not None:
                bottom_resized = bottom.resize(size) if bottom.size != size else bottom
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
