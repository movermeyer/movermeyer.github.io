#!/usr/bin/env python3
"""Find (and optionally fix) images that shouldn't be published as they are.

1. Metadata. Phone photos and screenshots carry EXIF (GPS location, device, timestamps),
   XMP, Photoshop/IPTC blocks and comments. This flags any of them. Colour profiles (ICC)
   are kept: they don't identify anyone, and removing them changes how colours look.
2. Size. Images wider or taller than MAX_DIMENSION pixels, or bigger than MAX_BYTES.

Usage:
  script/check_images.py FILE...          Report problem files (exit 1 if any)
  script/check_images.py --fix FILE...    Fix them in place
  script/check_images.py --staged         Check the images staged for commit (pre-commit hook)

Checking only uses the standard library. Handles JPEG, PNG, WebP and GIF.
--fix turns rotated JPEGs upright with jpegtran (`brew install jpeg`), and shrinks JPEGs
and PNGs with macOS's sips. Oversized WebPs and GIFs have to be shrunk by hand.
"""

import os
import struct
import subprocess
import sys
import tempfile
import zlib

EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")

MAX_DIMENSION = 1600       # px, longest side. Wider than the post column on a high-DPI screen
MAX_BYTES = 1024 * 1024    # 1 MiB
JPEG_QUALITY = 85          # when a JPEG is still over MAX_BYTES after resizing


class Problem(Exception):
    pass


# ---------- JPEG ----------

def _jpeg_segments(data):
    """Yield (marker, start, end) for each segment before the image data."""
    if data[:2] != b"\xff\xd8":
        raise Problem("not a JPEG")
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            raise Problem(f"corrupt JPEG at byte {i}")
        marker = data[i + 1]
        if marker == 0xFF:  # fill byte
            i += 1
            continue
        if marker == 0xDA:  # start of scan: the rest is image data
            yield marker, i, len(data)
            return
        if marker in (0x01,) or 0xD0 <= marker <= 0xD7:
            yield marker, i, i + 2
            i += 2
            continue
        (length,) = struct.unpack(">H", data[i + 2:i + 4])
        yield marker, i, i + 2 + length
        i += 2 + length


def _jpeg_label(marker, payload):
    if marker == 0xE1:
        if payload.startswith(b"Exif\0"):
            return "EXIF"
        if payload.startswith(b"http://ns.adobe.com/xap/1.0/") or payload.startswith(b"http://ns.adobe.com/xmp/"):
            return "XMP"
        return "APP1"
    if marker == 0xED:
        return "Photoshop/IPTC"
    if marker == 0xFE:
        return "comment"
    if 0xE3 <= marker <= 0xEF:  # APP3–APP15: vendor blocks (APP0 JFIF, APP2 ICC are fine)
        return f"APP{marker - 0xE0}"
    return None


def _exif_orientation(payload):
    """The EXIF Orientation tag (1 = upright), or None."""
    tiff = payload[6:]
    if len(tiff) < 8:
        return None
    endian = {b"II": "<", b"MM": ">"}.get(tiff[:2])
    if not endian:
        return None
    (ifd,) = struct.unpack(endian + "I", tiff[4:8])
    if ifd + 2 > len(tiff):
        return None
    (count,) = struct.unpack(endian + "H", tiff[ifd:ifd + 2])
    for n in range(count):
        entry = tiff[ifd + 2 + 12 * n: ifd + 14 + 12 * n]
        if len(entry) < 12:
            break
        tag, = struct.unpack(endian + "H", entry[:2])
        if tag == 0x0112:
            return struct.unpack(endian + "H", entry[8:10])[0]
    return None


# EXIF orientation -> the jpegtran transform that makes the pixels upright
JPEGTRAN_OPS = {2: ["-flip", "horizontal"], 3: ["-rotate", "180"], 4: ["-flip", "vertical"],
                5: ["-transpose"], 6: ["-rotate", "90"], 7: ["-transverse"], 8: ["-rotate", "270"]}


def _jpegtran(data, op):
    """Losslessly transform a JPEG with jpegtran, keeping only its ICC profile."""
    for edges in ("-perfect", "-trim"):  # -trim drops a partial block (<16 px) at an edge if needed
        try:
            result = subprocess.run(["jpegtran", "-copy", "icc", edges, *op], input=data, capture_output=True)
        except FileNotFoundError:
            raise Problem("this photo is rotated by its EXIF, and fixing it needs jpegtran (brew install jpeg)")
        if result.returncode == 0:
            return result.stdout
    raise Problem(f"jpegtran failed: {result.stderr.decode().strip()}")


def jpeg(data, fix):
    found, out, orientation = [], bytearray(data[:2]), None  # start with the SOI marker
    for marker, start, end in _jpeg_segments(data):
        payload = data[start + 4:end]
        label = _jpeg_label(marker, payload)
        if label:
            found.append(label)
            if label == "EXIF":
                orientation = _exif_orientation(payload)
        else:
            out += data[start:end]
    if fix and orientation in JPEGTRAN_OPS:
        # Stripping the EXIF would leave the photo sideways, so turn the pixels upright first
        found.append(f"rotated upright (orientation {orientation})")
        out = jpeg(_jpegtran(data, JPEGTRAN_OPS[orientation]), fix)[1]
    return found, bytes(out)


# ---------- PNG ----------

PNG_SIG = b"\x89PNG\r\n\x1a\n"
PNG_METADATA = {b"eXIf": "EXIF", b"tEXt": "text", b"zTXt": "text", b"iTXt": "text/XMP", b"tIME": "timestamp"}


def png(data, fix):
    if not data.startswith(PNG_SIG):
        raise Problem("not a PNG")
    found, out, i = [], bytearray(PNG_SIG), len(PNG_SIG)
    while i < len(data):
        (length,) = struct.unpack(">I", data[i:i + 4])
        ctype = data[i + 4:i + 8]
        end = i + 12 + length
        if ctype in PNG_METADATA:
            label = PNG_METADATA[ctype]
            if ctype in (b"tEXt", b"zTXt", b"iTXt"):
                label += f" ({data[i + 8:i + 8 + length].split(b'\0', 1)[0].decode('latin-1')})"
            found.append(label)
        else:
            out += data[i:end]
        i = end
        if ctype == b"IEND":
            break
    return found, bytes(out)


# ---------- WebP ----------

def webp(data, fix):
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise Problem("not a WebP")
    found, chunks, i = [], [], 12
    while i + 8 <= len(data):
        ctype = data[i:i + 4]
        (length,) = struct.unpack("<I", data[i + 4:i + 8])
        end = i + 8 + length + (length & 1)
        if ctype in (b"EXIF", b"XMP "):
            found.append(ctype.decode().strip())
        else:
            chunks.append(bytearray(data[i:end]))
        i = end
    for c in chunks:  # clear the "has EXIF/XMP" flags in the extended header
        if c[:4] == b"VP8X":
            c[8] &= ~0x0C & 0xFF
    body = b"WEBP" + b"".join(chunks)
    return found, b"RIFF" + struct.pack("<I", len(body)) + body


# ---------- GIF ----------

def gif(data, fix):
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise Problem("not a GIF")
    found, out = [], bytearray(data[:13])
    i = 13
    flags = data[10]
    if flags & 0x80:  # global colour table
        size = 3 * (2 << (flags & 7))
        out += data[i:i + size]
        i += size

    def sub_blocks(j):
        while data[j]:
            j += 1 + data[j]
        return j + 1

    while i < len(data):
        b = data[i]
        if b == 0x3B:  # trailer
            out += data[i:]
            break
        if b == 0x21:
            label = data[i + 1]
            end = sub_blocks(i + 2)
            if label == 0xFE:
                found.append("comment")
                i = end
                continue
            if label == 0xFF and data[i + 3:i + 14] == b"XMP DataXMP":
                found.append("XMP")
                i = end
                continue
            out += data[i:end]
            i = end
        elif b == 0x2C:  # image
            start = i
            flags = data[i + 9]
            i += 10
            if flags & 0x80:
                i += 3 * (2 << (flags & 7))
            i = sub_blocks(i + 1)  # skip the LZW minimum code size byte
            out += data[start:i]
        else:
            raise Problem(f"corrupt GIF at byte {i}")
    return found, bytes(out)


HANDLERS = {".jpg": jpeg, ".jpeg": jpeg, ".png": png, ".webp": webp, ".gif": gif}


def ext_of(path):
    return path[path.rfind("."):].lower()


def inspect(path, data, fix=False):
    return HANDLERS[ext_of(path)](data, fix)


# ---------- Size ----------

def dimensions(path, data):
    """(width, height) in pixels, read from the file's header."""
    ext = ext_of(path)
    if ext == ".png":
        return struct.unpack(">II", data[16:24])
    if ext == ".gif":
        return struct.unpack("<HH", data[6:10])
    if ext == ".webp":
        fmt = data[12:16]
        if fmt == b"VP8X":
            return (int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1)
        if fmt == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if fmt == b"VP8L":
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        raise Problem("unknown WebP format")
    for marker, start, _ in _jpeg_segments(data):  # start of frame: C0–CF, except DHT, JPG and DAC
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[start + 5:start + 9])
            return w, h
    raise Problem("JPEG has no frame header")


def size_problems(path, data):
    w, h = dimensions(path, data)
    found = []
    if max(w, h) > MAX_DIMENSION:
        found.append(f"{w}x{h} px (max {MAX_DIMENSION} on the longest side)")
    if len(data) > MAX_BYTES:
        found.append(f"{len(data) / 1024 / 1024:.1f} MiB (max {MAX_BYTES / 1024 / 1024:g} MiB)")
    return found


def shrink(path, data):
    """Resize a JPEG or PNG to fit MAX_DIMENSION, and recompress a JPEG still over MAX_BYTES, with sips."""
    ext = ext_of(path)
    if ext not in (".jpg", ".jpeg", ".png"):
        return data
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = os.path.join(tmp, "image" + ext)
        with open(tmp_path, "wb") as f:
            f.write(data)

        def sips(*args):
            try:
                subprocess.run(["sips", *args, tmp_path], check=True, capture_output=True)
            except FileNotFoundError:
                raise Problem("resizing needs macOS's sips")
            with open(tmp_path, "rb") as f:
                return f.read()

        if max(dimensions(path, data)) > MAX_DIMENSION:
            data = sips("-Z", str(MAX_DIMENSION))
        if ext != ".png" and len(data) > MAX_BYTES:
            data = sips("-s", "formatOptions", str(JPEG_QUALITY))
    return inspect(path, data, fix=True)[1]  # sips can write its own metadata back


def staged_images():
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
                         check=True, capture_output=True).stdout
    return [p for p in out.decode().split("\0") if p.lower().endswith(EXTENSIONS)]


def main(argv):
    fix = "--fix" in argv
    staged = "--staged" in argv
    paths = staged_images() if staged else [a for a in argv if not a.startswith("--")]
    bad = 0
    for path in paths:
        if not path.lower().endswith(EXTENSIONS):
            continue
        try:
            if staged:  # check what's being committed, not the working tree
                data = subprocess.run(["git", "cat-file", "blob", f":{path}"],
                                      check=True, capture_output=True).stdout
            else:
                with open(path, "rb") as f:
                    data = f.read()
            metadata, cleaned = inspect(path, data, fix)
            too_big = size_problems(path, data)
            if not fix:
                if metadata or too_big:
                    print(f"{path}: {', '.join(metadata + too_big)}")
                    bad += 1
                continue

            fixed = cleaned  # metadata stripped, and turned upright first if it was rotated
            if too_big:
                fixed = shrink(path, fixed)
            if fixed != data:
                with open(path, "wb") as f:
                    f.write(fixed)
                done = ([f"stripped {', '.join(metadata)}"] if metadata else []) + \
                       ([f"resized to {'x'.join(map(str, dimensions(path, fixed)))} px, "
                         f"{len(fixed) / 1024:.0f} KiB"] if too_big else [])
                print(f"{path}: {'; '.join(done)}")
            still = size_problems(path, fixed)
            if still:
                print(f"{path}: still {', '.join(still)}. Shrink it by hand")
                bad += 1
        except (Problem, struct.error, IndexError, zlib.error, subprocess.CalledProcessError) as e:
            print(f"{path}: {e}")
            bad += 1
    if bad and not fix:
        print(f"\n{bad} image(s) have metadata that shouldn't be published, or are too big. Fix them with:\n"
              f"  script/check_images.py --fix <files>" + ("\nthen `git add` them again." if staged else ""),
              file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
