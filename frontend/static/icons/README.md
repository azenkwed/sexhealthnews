# Icons

Place your square master logo PNG at `master.png` (minimum 1024×1024 px, transparent background).
Run the commands below to regenerate every icon variant from it.

## Output files

| File | Size | Use |
|---|---|---|
| `favicon.ico` | 16, 32, 48 px multi-size | Browser tab (legacy + modern) |
| `favicon-16.png` | 16×16 | Browser tab fallback |
| `favicon-32.png` | 32×32 | Browser tab standard |
| `favicon-48.png` | 48×48 | Windows site icon |
| `apple-touch-icon.png` | 180×180 | iOS home screen |
| `icon-144.png` | 144×144 | Windows tile / IE |
| `icon-152.png` | 152×152 | iPad home screen |
| `icon-192.png` | 192×192 | Android / PWA |
| `icon-384.png` | 384×384 | PWA splash |
| `icon-512.png` | 512×512 | PWA manifest |
| `icon-1024.png` | 1024×1024 | App Store / high-res |
| `social-170.png` | 170×170 | Twitter/X profile picture |
| `social-300.png` | 300×300 | Facebook profile picture |
| `social-400.png` | 400×400 | LinkedIn profile picture |
| `social-800.png` | 800×800 | General social / email header |

---

## Generate all icons at once

```bash
# Favicons (PNG)
magick master.png -resize 16x16   favicon-16.png
magick master.png -resize 32x32   favicon-32.png
magick master.png -resize 48x48   favicon-48.png

# favicon.ico — multi-size bundle (16 + 32 + 48)
magick favicon-16.png favicon-32.png favicon-48.png favicon.ico

# Apple / iOS
magick master.png -resize 180x180 apple-touch-icon.png

# Android / PWA / Windows
magick master.png -resize 144x144 icon-144.png
magick master.png -resize 152x152 icon-152.png
magick master.png -resize 192x192 icon-192.png
magick master.png -resize 384x384 icon-384.png
magick master.png -resize 512x512 icon-512.png
magick master.png -resize 1024x1024 icon-1024.png

# Social media
magick master.png -resize 170x170 social-170.png
magick master.png -resize 300x300 social-300.png
magick master.png -resize 400x400 social-400.png
magick master.png -resize 800x800 social-800.png
```

### One-liner version

```bash
for size in 16 32 48 144 152 192 384 512 1024; do magick master.png -resize ${size}x${size} icon-${size}.png; done && \
magick master.png -resize 16x16 favicon-16.png && \
magick master.png -resize 32x32 favicon-32.png && \
magick master.png -resize 48x48 favicon-48.png && \
magick favicon-16.png favicon-32.png favicon-48.png favicon.ico && \
magick master.png -resize 180x180 apple-touch-icon.png && \
magick master.png -resize 170x170 social-170.png && \
magick master.png -resize 300x300 social-300.png && \
magick master.png -resize 400x400 social-400.png && \
magick master.png -resize 800x800 social-800.png
```

---

## Add a white background (if master has transparency)

Social platforms often flatten transparency to black. Pre-fill with white before resizing:

```bash
magick master.png -background white -flatten -resize 300x300 social-300.png
```

Replace `-background white` with `-background "#DC143C"` for a branded crimson fill.

---

## Sharpen small sizes

At 16–48 px, icons can look soft. Apply a mild sharpen pass:

```bash
magick master.png -resize 32x32 -unsharp 0x1+0.5+0 favicon-32.png
```

---

## Recommended master spec

- Size: **1024×1024 px** minimum (2048×2048 preferred)
- Format: PNG with transparency
- Content: logo centered with ~10% padding on all sides
- No drop shadows baked in (add them per platform if needed)
