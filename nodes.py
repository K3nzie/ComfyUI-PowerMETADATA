"""
ComfyUI Power METADATA - nodes.py
==================================
Core node implementations.

NODE GUIDE
----------
MetadataInjector vs SynthesizeAndSave — pick ONE per workflow:

  ┌─────────────────────────────────────────────────────────────────┐
  │  Need more nodes after injection?                               │
  │    → Use MetadataInjector (returns tensor, save separately)     │
  │                                                                 │
  │  Want a single save step with authentic EXIF?                   │
  │    → Use SynthesizeAndSave (injects + saves in one node)        │
  │                                                                 │
  │  ⚠️  NEVER chain MetadataInjector → SynthesizeAndSave           │
  │      That will double-inject EXIF and corrupt the output.       │
  └─────────────────────────────────────────────────────────────────┘

BATCH SUPPORT
-------------
  Both injection nodes process the full batch automatically.
  Each image in the batch gets its own randomised EXIF (datetime,
  GPS offset, camera settings) — they are NOT identical copies.

MOBILITY PATTERNS (GPS noise radius)
-------------------------------------
  Stationary  ±15 m   — same room / building (home, office)
  Local       ±200 m  — same neighbourhood
  Roaming     ±800 m  — moving around the city
"""

import os
import io
import json
import random
import math
import datetime
import numpy as np
from PIL import Image
import piexif
import folder_paths

# ── Paths ────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(__file__)

with open(os.path.join(_HERE, "device_profiles.json"), "r") as f:
    DEVICE_PROFILES = json.load(f)

with open(os.path.join(_HERE, "gps_locations.json"), "r") as f:
    GPS_LOCATIONS = json.load(f)

with open(os.path.join(_HERE, "scene_profiles.json"), "r") as f:
    SCENE_PROFILES = json.load(f)

# Mobility pattern → GPS noise radius in metres
MOBILITY_PATTERNS = {
    "Stationary  (±15 m  — same room / building)": 15,
    "Local       (±200 m — same neighbourhood)":   200,
    "Roaming     (±800 m — moving around city)":   800,
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def _deg_to_dms(deg):
    d = int(abs(deg))
    m = int((abs(deg) - d) * 60)
    s = ((abs(deg) - d) * 60 - m) * 60
    return [(d, 1), (m, 1), (int(s * 100), 100)]


def _add_gps_noise(lat, lon, radius_m=400):
    delta_lat = random.uniform(-radius_m, radius_m) / 111_320
    delta_lon = random.uniform(-radius_m, radius_m) / (111_320 * abs(math.cos(math.radians(lat))) + 1e-9)
    return lat + delta_lat, lon + delta_lon


def _random_datetime(scene_profile, days_back=180):
    hour_min, hour_max = scene_profile["hour_range"]
    delta = datetime.timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(hour_min, hour_max),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    dt = datetime.datetime.now() - delta
    return dt.strftime("%Y:%m:%d %H:%M:%S")


def _pick_camera_settings(scene_profile):
    """Pick realistic randomised camera settings from a scene profile."""
    iso_min, iso_max = scene_profile["iso_range"]
    iso = random.choice([v for v in [50,64,80,100,125,160,200,250,320,400,500,640,800,
                                      1000,1250,1600,2000,2500,3200,4000,5000,6400]
                         if iso_min <= v <= iso_max] or [iso_min])

    s_min, s_max = scene_profile["shutter_range"]
    shutter = random.uniform(s_min, s_max)
    shutter_denom = max(1, round(1.0 / shutter))
    shutter_rational = (1, shutter_denom)

    fn_min, fn_max = scene_profile["fnumber_range"]
    fnumber_float = random.uniform(fn_min, fn_max)
    fnumber_rational = (round(fnumber_float * 10), 10)

    focal = random.randint(24, 28)
    focal_rational = (focal, 1)

    return iso, shutter_rational, fnumber_rational, focal_rational


def _build_exif(device_profile: dict, location: dict, scene_profile: dict, radius_m: int) -> bytes:
    """Build a unique EXIF blob — called once per image so each gets its own randomised values."""
    lat, lon = _add_gps_noise(location["lat"], location["lon"], radius_m)
    dt_str = _random_datetime(scene_profile)
    iso, shutter, fnumber, focal = _pick_camera_settings(scene_profile)

    zeroth = {
        piexif.ImageIFD.Make:            device_profile["Make"].encode(),
        piexif.ImageIFD.Model:           device_profile["Model"].encode(),
        piexif.ImageIFD.Software:        device_profile["Software"].encode(),
        piexif.ImageIFD.DateTime:        dt_str.encode(),
        piexif.ImageIFD.ResolutionUnit:  device_profile.get("ResolutionUnit", 2),
        piexif.ImageIFD.XResolution:     tuple(device_profile["XResolution"]),
        piexif.ImageIFD.YResolution:     tuple(device_profile["YResolution"]),
    }

    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal:  dt_str.encode(),
        piexif.ExifIFD.DateTimeDigitized: dt_str.encode(),
        piexif.ExifIFD.FocalLength:       focal,
        piexif.ExifIFD.FNumber:           fnumber,
        piexif.ExifIFD.ExposureTime:      shutter,
        piexif.ExifIFD.ISOSpeedRatings:   iso,
        piexif.ExifIFD.LensMake:          device_profile.get("LensMake", device_profile["Make"]).encode(),
    }

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef:  b"N" if lat >= 0 else b"S",
        piexif.GPSIFD.GPSLatitude:     _deg_to_dms(lat),
        piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
        piexif.GPSIFD.GPSLongitude:    _deg_to_dms(lon),
    }

    return piexif.dump({"0th": zeroth, "Exif": exif_ifd, "GPS": gps_ifd})


def _inject_single(tensor_frame, device_profile, location, scene_profile, radius_m, quality=95):
    """Inject EXIF into a single [H, W, C] tensor frame. Returns a PIL Image."""
    arr = (tensor_frame.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    pil_img = Image.fromarray(arr).convert("RGB")
    exif_bytes = _build_exif(device_profile, location, scene_profile, radius_m)
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", exif=exif_bytes, quality=quality)
    buf.seek(0)
    return Image.open(buf).copy()


def _pil_to_tensor(img: Image.Image):
    import torch
    arr = np.array(img).astype(np.float32) / 255.0
    return torch.from_numpy(arr)          # [H, W, C]


def _tensor_to_pil(tensor) -> Image.Image:
    """Legacy single-image helper (used by LoadAndStrip)."""
    arr = (tensor.squeeze(0).cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr)


# ── Node 1: DeviceProfileSelector ────────────────────────────────────────────

class DeviceProfileSelector:
    """
    Select a phone device profile, GPS location, scene type, and mobility pattern.

    Mobility pattern controls the GPS noise radius:
      Stationary  ±15 m   — same room / building (home, office, same spot)
      Local       ±200 m  — same neighbourhood
      Roaming     ±800 m  — moving around the city
    """

    CATEGORY = "Power METADATA"
    RETURN_TYPES = ("DEVICE_PROFILE", "GPS_LOCATION", "SCENE_PROFILE", "INT")
    RETURN_NAMES = ("device_profile", "gps_location", "scene_profile", "gps_radius_m")
    FUNCTION = "select"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "device":           (list(DEVICE_PROFILES.keys()),),
                "location":         (list(GPS_LOCATIONS.keys()),),
                "scene_type":       (list(SCENE_PROFILES.keys()),),
                "mobility_pattern": (list(MOBILITY_PATTERNS.keys()),),
            }
        }

    def select(self, device, location, scene_type, mobility_pattern):
        radius_m = MOBILITY_PATTERNS[mobility_pattern]
        return (DEVICE_PROFILES[device], GPS_LOCATIONS[location], SCENE_PROFILES[scene_type], radius_m)


# ── Node 2: MetadataInjector ──────────────────────────────────────────────────

class MetadataInjector:
    """
    Inject phone EXIF metadata into an image tensor (or batch) and return it.

    Supports batches — each image in the batch gets its own unique randomised
    EXIF (datetime, GPS offset, camera settings).

    USE THIS NODE when you need the tensor for further processing downstream.
    Save the result with ComfyUI's built-in SaveImage node.

    ⚠️  Do NOT chain this into SynthesizeAndSave — that double-injects EXIF.

    Typical workflow:
        LoadImage → DeviceProfileSelector → MetadataInjector
                  → (optional extra nodes) → SaveImage
    """

    CATEGORY = "Power METADATA"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "inject"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image":          ("IMAGE",),
                "device_profile": ("DEVICE_PROFILE",),
                "gps_location":   ("GPS_LOCATION",),
                "scene_profile":  ("SCENE_PROFILE",),
                "gps_radius_m":   ("INT", {"default": 400, "min": 5, "max": 2000}),
            }
        }

    def inject(self, image, device_profile, gps_location, scene_profile, gps_radius_m):
        import torch
        frames = []
        for i in range(image.shape[0]):
            pil = _inject_single(image[i], device_profile, gps_location, scene_profile, gps_radius_m)
            frames.append(_pil_to_tensor(pil))
        return (torch.stack(frames),)   # [B, H, W, C]


# ── Node 3: SynthesizeAndSave ─────────────────────────────────────────────────

class SynthesizeAndSave:
    """
    All-in-one: inject authentic phone EXIF and save the JPEG(s).

    Supports batches — each image in the batch is saved as a separate file,
    each with its own unique randomised EXIF.

    USE THIS NODE as your final save step when you don't need the tensor
    for any further processing.

    ⚠️  Do NOT feed MetadataInjector output into this node.
        That will double-inject EXIF and corrupt the output.

    Typical workflow:
        LoadImage → DeviceProfileSelector → SynthesizeAndSave
    """

    CATEGORY = "Power METADATA"
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "save"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image":           ("IMAGE",),
                "device_profile":  ("DEVICE_PROFILE",),
                "gps_location":    ("GPS_LOCATION",),
                "scene_profile":   ("SCENE_PROFILE",),
                "gps_radius_m":    ("INT", {"default": 400, "min": 5, "max": 2000}),
                "filename_prefix": ("STRING", {"default": "phone_photo"}),
                "quality":         ("INT", {"default": 95, "min": 60, "max": 100}),
            }
        }

    def save(self, image, device_profile, gps_location, scene_profile, gps_radius_m, filename_prefix, quality):
        output_dir = os.path.join(folder_paths.get_output_directory(), "PowerMETADATA")
        os.makedirs(output_dir, exist_ok=True)

        batch_size = image.shape[0]
        ts_base = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        for i in range(batch_size):
            pil_img = _inject_single(image[i], device_profile, gps_location, scene_profile, gps_radius_m, quality)
            # Append index only when batch > 1 to keep single-image filenames clean
            suffix = f"_{i+1:03d}" if batch_size > 1 else ""
            filename = f"{filename_prefix}_{ts_base}{suffix}.jpg"
            out_path = os.path.join(output_dir, filename)
            pil_img.save(out_path, format="JPEG", quality=quality)
            print(f"[Power METADATA] Saved ({i+1}/{batch_size}): {out_path}")

        return {}


# ── Node 4: LoadAndStrip ──────────────────────────────────────────────────────

class LoadAndStrip:
    """
    Strip ALL existing metadata from an image tensor (or batch) — clean slate.
    Useful as a pre-processing step before injecting fresh EXIF.
    """

    CATEGORY = "Power METADATA"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "load_strip"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
            }
        }

    def load_strip(self, image):
        import torch
        frames = []
        for i in range(image.shape[0]):
            arr = (image[i].cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
            pil = Image.fromarray(arr).convert("RGB")
            clean = Image.new("RGB", pil.size)
            clean.paste(pil)
            frames.append(_pil_to_tensor(clean))
        return (torch.stack(frames),)


# ── Mappings ──────────────────────────────────────────────────────────────────

NODE_CLASS_MAPPINGS = {
    "DeviceProfileSelector": DeviceProfileSelector,
    "MetadataInjector":      MetadataInjector,
    "SynthesizeAndSave":     SynthesizeAndSave,
    "LoadAndStrip":          LoadAndStrip,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DeviceProfileSelector": "📱 Device Profile Selector",
    "MetadataInjector":      "🔧 Metadata Injector [chain → SaveImage]",
    "SynthesizeAndSave":     "💾 Synthesize & Save w/ Authentic Metadata",
    "LoadAndStrip":          "📂 Load & Strip Metadata",
}
