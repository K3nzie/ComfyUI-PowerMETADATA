"""
ComfyUI Power METADATA
======================
A custom node pack for ComfyUI that strips AI-generated metadata from images
and injects authentic-looking phone EXIF data, with scene-aware camera settings.

WHAT'S INCLUDED
---------------
  • 48 phone device profiles  (Apple, Samsung, Google, OnePlus, Xiaomi, Sony, Huawei, Nothing)
  • 113 GPS locations          (22 US cities + full EU coverage across 25+ countries)
  • 20 scene types             (each drives realistic ISO, shutter, aperture & time-of-day)

NODES
-----
1. 📱 Device Profile Selector
   - Choose a phone model, a GPS city, and a scene type.
   - Scene type controls realistic camera settings (ISO, shutter speed, aperture)
     so they match the visual content — e.g. beach = low ISO, night = high ISO.
   - Output feeds into either MetadataInjector OR SynthesizeAndSave.

2. 🔧 Metadata Injector  [USE THIS when you need the tensor for more nodes]
   - Injects scene-aware EXIF into an image tensor and returns it for further processing.
   - ⚠️  Do NOT chain this into SynthesizeAndSave — that would double-inject EXIF.
   - Typical workflow:
       LoadImage → DeviceProfileSelector → MetadataInjector → (more nodes) → SaveImage

3. 💾 Synthesize & Save w/ Authentic Metadata  [USE THIS as your final save]
   - All-in-one: injects scene-aware EXIF and saves the JPEG in one step.
   - ⚠️  Do NOT feed MetadataInjector output into this node.
   - Typical workflow:
       LoadImage → DeviceProfileSelector → SynthesizeAndSave

4. 📂 Load & Strip Metadata
   - Strips ALL existing metadata from an image tensor (clean slate).
   - Useful before injecting fresh EXIF.
   - Typical workflow:
       LoadImage → LoadAndStrip → DeviceProfileSelector → SynthesizeAndSave

CHOOSE YOUR INJECTION NODE
--------------------------
  Need more processing after injection?  → Use MetadataInjector
  Just want to save with authentic EXIF? → Use SynthesizeAndSave
  ⚠️  Never use both on the same image.
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
