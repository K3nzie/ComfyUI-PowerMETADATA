# ComfyUI Power METADATA

A ComfyUI custom node pack that strips AI-generated metadata from images and injects
authentic-looking phone EXIF data — with scene-aware camera settings, mobility-based
GPS noise, and full batch support.

---

## Features

- **48 phone device profiles** — Apple iPhone 12–16 Pro Max, Samsung Galaxy S21–S25 Ultra,
  Google Pixel 6–9 Pro, OnePlus 11/12, Xiaomi 13 Pro/14/14 Ultra, Sony Xperia 1V/5V/1VI,
  Huawei P50/P60 Pro, Nothing Phone 2/2a
- **135 GPS locations** — 22 US cities + full EU coverage (30+ countries)
- **20 scene types** — each drives realistic, randomised ISO / shutter speed / aperture
  and time-of-day so camera settings actually match the visual content
- **3 mobility patterns** — control GPS coordinate noise radius to match how much
  the "person" is moving between shots
- **Batch support** — process multiple images at once; each image gets its own unique
  randomised EXIF (datetime, GPS offset, camera settings)

---

## Installation

1. Copy the `ComfyUI_PowerMETADATA/` folder into:
   ```
   ComfyUI/custom_nodes/ComfyUI_PowerMETADATA/
   ```
2. Install the only non-standard dependency:
   ```bash
   # Portable install:
   python_embeded\python.exe -m pip install piexif

   # venv install:
   pip install piexif
   ```
3. Restart ComfyUI.
4. Right-click the canvas → **Add Node** → look for the **Power METADATA** category.
5. Delete `__pycache__/` if updating from a previous version.

---

## Nodes

### 📱 Device Profile Selector
Outputs a `device_profile`, `gps_location`, `scene_profile`, and `gps_radius_m` to feed into the injection nodes.

| Input | Description |
|---|---|
| `device` | Phone model (48 options) |
| `location` | GPS city (135 options, flagged by country) |
| `scene_type` | Scene type that drives camera settings (20 options) |
| `mobility_pattern` | Controls GPS noise radius (see table below) |

#### Mobility Patterns

| Pattern | Radius | Best used for |
|---|---|---|
| `Stationary` | ±15 m | Same room / building — home, office, same spot |
| `Local` | ±200 m | Same neighbourhood — nearby streets, park |
| `Roaming` | ±800 m | Moving around the city |

> **Tip:** For a set of photos taken in the same location, use `Stationary`
> so GPS coords stay within ±15 m of each other — just like a real phone would.

---

### 🔧 Metadata Injector
Injects EXIF into the image tensor (or batch) and **returns it** for further node processing.
Use this when you need to do more work on the image before saving.

**Batch behaviour:** each image in the batch gets its own unique randomised EXIF.

> ⚠️ **Do NOT chain into SynthesizeAndSave** — that double-injects EXIF.

**Typical workflow:**
```
LoadImage → DeviceProfileSelector → MetadataInjector → (more nodes) → SaveImage
```

---

### 💾 Synthesize & Save w/ Authentic Metadata
All-in-one node: injects EXIF and saves the JPEG(s) directly to disk.
Use this as your **final save step**.

**Batch behaviour:** each image is saved as a separate file with its own unique EXIF.
Single images → `photo_20260401_123456.jpg`
Batches → `photo_20260401_123456_001.jpg`, `_002.jpg`, etc.

> ⚠️ **Do NOT feed MetadataInjector output into this node.**

**Typical workflow:**
```
LoadImage → DeviceProfileSelector → SynthesizeAndSave
```

| Input | Description |
|---|---|
| `filename_prefix` | Output filename prefix (default: `phone_photo`) |
| `quality` | JPEG quality 60–100 (default: 95) |
| `gps_radius_m` | GPS noise radius in metres (wired from DeviceProfileSelector) |

Output saved to: `ComfyUI/output/PowerMETADATA/`

---

### 📂 Load & Strip Metadata
Strips ALL existing metadata from an image tensor (or batch), returning a clean slate.

> **Note:** If you are using `SynthesizeAndSave`, you do **not** need this node — it already
> overwrites all EXIF when saving, so any pre-existing metadata is gone regardless.
>
> This node is only useful when using `MetadataInjector` (which returns a tensor without saving),
> and you want to guarantee the tensor is completely clean before passing it downstream.

**Batch behaviour:** all images in the batch are stripped.

**Typical workflow (only when using MetadataInjector):**
```
LoadImage → 📂 Load & Strip → 📱 Device Profile Selector → 🔧 Metadata Injector → SaveImage
```

---

## Scene Types & Camera Settings

Each scene type randomises camera settings within realistic bounds:

| Scene | ISO range | Shutter | Aperture |
|---|---|---|---|
| 🌞 Outdoor - Bright Daylight | 50–100 | 1/500–1/1000 | f/1.8–2.8 |
| 🌅 Golden Hour | 64–200 | 1/125–1/500 | f/1.8–2.4 |
| 🌃 Night / City Lights | 800–3200 | 1/8–1/30 | f/1.6–2.0 |
| 🏠 Indoor - Well Lit | 200–800 | 1/60–1/120 | f/1.8–2.4 |
| 🎭 Concert / Stage | 1600–6400 | 1/60–1/125 | f/1.6–2.0 |
| 🏖 Beach / Coastal | 50–100 | 1/500–1/2000 | f/2.0–2.8 |
| ❄️ Snow / Winter | 50–200 | 1/250–1/1000 | f/2.0–2.8 |
| *(+ 13 more...)* | | | |

---

## Batch Workflow Example

To process a set of photos for one post:

```
[Load Image Batch] ──→ [📱 Device Profile Selector]
                              ↓
                   [💾 Synthesize & Save]
```

Each image in the batch will have:
- A different randomised datetime
- A slightly different GPS coordinate (within your chosen mobility radius)
- Different camera settings (ISO, shutter, aperture) within the scene's realistic range

---

## File Structure

```
ComfyUI_PowerMETADATA/
├── __init__.py           # Node registration & documentation
├── nodes.py              # Core node logic
├── device_profiles.json  # 48 phone EXIF profiles
├── scene_profiles.json   # 20 scene types with camera setting ranges
├── gps_locations.json    # 135 GPS city coordinates
└── requirements.txt      # piexif, Pillow, numpy
```

---

## Requirements

- ComfyUI (any recent version)
- Python 3.10+
- `piexif >= 1.1.3`
- `Pillow >= 9.0.0` *(usually already installed with ComfyUI)*
- `numpy >= 1.21.0` *(usually already installed with ComfyUI)*
