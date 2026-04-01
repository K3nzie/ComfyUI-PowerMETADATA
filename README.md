# ComfyUI Power METADATA

A ComfyUI custom node pack that strips AI-generated metadata from images and injects
authentic-looking phone EXIF data — with scene-aware camera settings for maximum realism.

---

## Features

- **48 phone device profiles** — Apple iPhone 12–16 Pro Max, Samsung Galaxy S21–S25 Ultra,
  Google Pixel 6–9 Pro, OnePlus 11/12, Xiaomi 13 Pro/14/14 Ultra, Sony Xperia 1V/5V/1VI,
  Huawei P50/P60 Pro, Nothing Phone 2/2a
- **113 GPS locations** — 22 US cities + full EU coverage (UK, France, Germany, Italy,
  Spain, Netherlands, Belgium, Austria, Switzerland, Portugal, Sweden, Norway, Denmark,
  Finland, Poland, Czech Republic, Hungary, Romania, Greece, Croatia, and more)
- **20 scene types** — each one drives realistic, randomised ISO / shutter speed / aperture
  and time-of-day so camera settings actually match the visual content of the image
- **GPS noise** — small random offset applied to coordinates (±400 m) for natural variation

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

---

## Nodes

### 📱 Device Profile Selector
Outputs a `device_profile`, `gps_location`, and `scene_profile` to feed into the injection nodes.

| Input | Description |
|---|---|
| `device` | Phone model (48 options) |
| `location` | GPS city (113 options, flagged by country) |
| `scene_type` | Scene type that drives camera settings (20 options) |

---

### 🔧 Metadata Injector
Injects EXIF into the image tensor and **returns it** for further node processing.
Use this when you need to do more work on the image before saving.

> ⚠️ **Do NOT chain into SynthesizeAndSave** — that double-injects EXIF.

**Typical workflow:**
```
LoadImage → DeviceProfileSelector → MetadataInjector → (more nodes) → SaveImage
```

---

### 💾 Synthesize & Save w/ Authentic Metadata
All-in-one node: injects EXIF and saves the JPEG directly to disk.
Use this as your **final save step**.

> ⚠️ **Do NOT feed MetadataInjector output into this node.**

**Typical workflow:**
```
LoadImage → DeviceProfileSelector → SynthesizeAndSave
```

| Input | Description |
|---|---|
| `filename_prefix` | Output filename prefix (default: `phone_photo`) |
| `quality` | JPEG quality 60–100 (default: 95) |

Output saved to: `ComfyUI/output/PowerMETADATA/`

---

### 📂 Load & Strip Metadata
Strips ALL existing metadata from an image tensor, returning a clean slate.
Useful as a pre-processing step before injecting fresh EXIF.

**Typical workflow:**
```
LoadImage → LoadAndStrip → DeviceProfileSelector → SynthesizeAndSave
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

## File Structure

```
ComfyUI_PowerMETADATA/
├── __init__.py           # Node registration & documentation
├── nodes.py              # Core node logic
├── device_profiles.json  # 48 phone EXIF profiles
├── scene_profiles.json   # 20 scene types with camera setting ranges
├── gps_locations.json    # 113 GPS city coordinates
└── requirements.txt      # piexif, Pillow, numpy
```

---

## Requirements

- ComfyUI (any recent version)
- Python 3.10+
- `piexif >= 1.1.3`
- `Pillow >= 9.0.0` *(usually already installed with ComfyUI)*
- `numpy >= 1.21.0` *(usually already installed with ComfyUI)*
