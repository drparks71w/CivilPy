#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""``photos`` commands: site-photo EXIF, batch rename/resize/stamp.

Wraps :mod:`civilpy.general.photos` (Pillow-based).  Every verb accepts a
single image or a folder (searched recursively) and runs a progress bar
over the set — inspection photo folders run to hundreds of files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from civilpy.cli import ui
from civilpy.cli.io_ import Column, CommandResult, ResultTable
from civilpy.cli.registry import CliError, CommandSpec

#: Extension filter, matching civilpy.general.photos.get_photos_from_file_list.
PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp",
              ".heif", ".svg")

#: EXIF tag numbers used below (PIL.ExifTags.Base values, stated here so the
#: command module needs no enum import at completion time).
_TAG_DATETIME_ORIGINAL = 36867
_TAG_DATETIME = 306
_TAG_MAKE = 271
_TAG_MODEL = 272
_IFD_GPS = 0x8825


@dataclass(frozen=True)
class PhotosPathInput:
    """Inputs for ``photos exif`` (an image or a folder of them)."""

    path: str = field(metadata={
        "positional": True, "kind": "path", "exts": PHOTO_EXTS,
        "doc": "an image file, or a folder of photos (searched recursively)",
    })


@dataclass(frozen=True)
class PhotosRenameInput:
    """Inputs for ``photos rename``."""

    folder: str = field(metadata={
        "positional": True, "kind": "path", "exts": (),
        "doc": "root photo folder; renamed copies land in Renamed_Photos/",
    })
    excel: Optional[str] = field(default=None, metadata={
        "kind": "path", "exts": (".xlsx", ".xls", ".xlsm"),
        "doc": "spreadsheet of current path (col A) and new name (col B); "
               "found inside the folder when omitted",
    })
    keep_existing: bool = field(default=False, metadata={
        "doc": "append the original filename to the new name",
    })


@dataclass(frozen=True)
class PhotosResizeInput:
    """Inputs for ``photos resize``."""

    path: str = field(metadata={
        "positional": True, "kind": "path", "exts": PHOTO_EXTS,
        "doc": "an image file, or a folder of photos (searched recursively)",
    })
    width: int = field(default=1024, metadata={
        "doc": "target width in pixels",
    })
    height: int = field(default=768, metadata={
        "doc": "target height in pixels",
    })
    dest: Optional[str] = field(default=None, metadata={
        "kind": "path", "exts": (),
        "doc": "output folder (default: Resized_Photos next to the input)",
    })


@dataclass(frozen=True)
class PhotosStampInput:
    """Inputs for ``photos stamp``."""

    path: str = field(metadata={
        "positional": True, "kind": "path", "exts": PHOTO_EXTS,
        "doc": "an image file, or a folder of photos (searched recursively)",
    })
    dest: Optional[str] = field(default=None, metadata={
        "kind": "path", "exts": (),
        "doc": "output folder (default: Stamped_Photos next to the input)",
    })


def _photo_files(target: str) -> list:
    """An image path → [it]; a folder → every photo under it, sorted
    naturally (IMG_2 before IMG_10)."""
    from natsort import natsorted

    p = Path(target).expanduser()
    if not p.exists():
        raise CliError(f"no such file or folder: {p}")
    if p.is_file():
        if p.suffix.lower() not in PHOTO_EXTS:
            raise CliError(f"{p.name} is not a recognized photo type "
                           f"({', '.join(PHOTO_EXTS)})")
        return [p]
    files = [f for f in p.rglob("*")
             if f.is_file() and f.suffix.lower() in PHOTO_EXTS]
    if not files:
        raise CliError(f"no photos under {p}")
    return natsorted(files, key=str)


def _dest_folder(inp_dest: Optional[str], target: str, default_name: str) -> Path:
    if inp_dest:
        dest = Path(inp_dest).expanduser()
    else:
        p = Path(target).expanduser()
        dest = (p if p.is_dir() else p.parent) / default_name
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _gps_decimal(gps: dict):  # noqa: ANN001
    """GPS EXIF IFD (already GPSTAGS-named) → (lat, lon) in signed decimal
    degrees, or (None, None)."""
    try:
        def to_deg(dms, ref, negative_ref):  # noqa: ANN001
            deg = float(dms[0]) + float(dms[1]) / 60 + float(dms[2]) / 3600
            return -deg if ref in negative_ref else deg

        lat = to_deg(gps["GPSLatitude"], gps.get("GPSLatitudeRef", "N"), "S")
        lon = to_deg(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E"), "W")
        return lat, lon
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        return None, None


def run_exif(inp: PhotosPathInput, ctx) -> CommandResult:  # noqa: ANN001
    from PIL import Image
    from PIL.ExifTags import GPSTAGS

    files = _photo_files(inp.path)
    rows, unreadable = [], []
    with ui.progress("Reading EXIF", total=len(files)) as advance:
        for f in files:
            try:
                with Image.open(f) as img:
                    exif = img.getexif()
                    taken = exif.get(_TAG_DATETIME_ORIGINAL) or exif.get(_TAG_DATETIME)
                    make = (exif.get(_TAG_MAKE) or "").strip()
                    model = (exif.get(_TAG_MODEL) or "").strip()
                    camera = " ".join(x for x in (make, model) if x) or None
                    gps_ifd = exif.get_ifd(_IFD_GPS)
                    gps = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
                    lat, lon = _gps_decimal(gps)
                    rows.append((f.name, taken, img.width, img.height,
                                 camera, lat, lon))
            except Exception as exc:  # corrupt files happen in bulk
                unreadable.append(f"{f.name}: {exc}")
            advance(note=f.name)
    if not rows:
        raise CliError("no readable photos found")

    table = ResultTable(
        title="Photo EXIF",
        columns=[
            Column("File"), Column("Taken"), Column("Width", "px"),
            Column("Height", "px"), Column("Camera"),
            Column("Latitude", None, ".6f"), Column("Longitude", None, ".6f"),
        ],
        rows=rows,
        notes=[f"unreadable: {msg}" for msg in unreadable],
    )
    return CommandResult(tables=[table])


def run_rename(inp: PhotosRenameInput, ctx) -> CommandResult:  # noqa: ANN001
    import shutil

    import pandas as pd

    from civilpy.general.photos import slugify

    folder = Path(inp.folder).expanduser()
    if not folder.is_dir():
        raise CliError(f"not a folder: {folder}")

    excel = Path(inp.excel).expanduser() if inp.excel else None
    if excel is None:
        candidates = sorted(
            f for f in folder.rglob("*")
            if f.suffix.lower() in (".xlsx", ".xls", ".xlsm")
            and not f.name.startswith("~$")
        )
        if not candidates:
            raise CliError(f"no rename spreadsheet found under {folder}; "
                           "pass one with --excel")
        excel = candidates[0]
    if not excel.exists():
        raise CliError(f"no such file: {excel}")

    plan = pd.read_excel(excel, 0, header=None)
    if plan.shape[1] < 2:
        raise CliError(f"{excel.name}: expected current path in column A "
                       "and new name in column B (no header)")

    dest = folder / "Renamed_Photos"
    dest.mkdir(exist_ok=True)
    rows, skipped = [], []
    pairs = list(zip(plan[0].tolist(), plan[1].tolist()))
    with ui.progress("Renaming photos", total=len(pairs)) as advance:
        for old, new in pairs:
            if pd.isna(old) or pd.isna(new):
                skipped.append(f"row with empty cell: {old!r} → {new!r}")
                advance()
                continue
            src = Path(str(old)).expanduser()
            if not src.is_absolute():
                src = folder / src
            if not src.exists():
                skipped.append(f"missing source: {src}")
                advance(note=src.name)
                continue
            suffix = src.suffix.lower() or ".jpg"
            stem = slugify(new)
            if inp.keep_existing:
                stem = f"{stem}-{slugify(src.stem)}"
            target = dest / f"{stem}{suffix}"
            shutil.copy(src, target)
            rows.append((src.name, target.name))
            advance(note=src.name)
    if not rows:
        raise CliError("no photos renamed — check the spreadsheet paths")

    table = ResultTable(
        title=f"Renamed into {dest}",
        columns=[Column("Original"), Column("New file")],
        rows=rows,
        notes=[f"skipped {msg}" for msg in skipped],
    )
    return CommandResult(tables=[table], input_files=[str(excel)])


def run_resize(inp: PhotosResizeInput, ctx) -> CommandResult:  # noqa: ANN001
    from PIL import Image

    from civilpy.general.photos import resize_image

    files = _photo_files(inp.path)
    dest = _dest_folder(inp.dest, inp.path, "Resized_Photos")
    rows, skipped = [], []
    with ui.progress("Resizing photos", total=len(files)) as advance:
        for f in files:
            try:
                with Image.open(f) as img:
                    original = f"{img.width}×{img.height}"
                    resized = resize_image(img, inp.width, inp.height)
                out = dest / f.name
                resized.save(out)
                rows.append((f.name, original,
                             f"{resized.width}×{resized.height}", str(out)))
            except Exception as exc:
                skipped.append(f"{f.name}: {exc}")
            advance(note=f.name)
    if not rows:
        raise CliError("no photos resized")

    table = ResultTable(
        title=f"Resized into {dest}",
        columns=[
            Column("File"), Column("Original", "px"), Column("Resized", "px"),
            Column("Output"),
        ],
        rows=rows,
        notes=[f"skipped {msg}" for msg in skipped],
    )
    return CommandResult(tables=[table])


def run_stamp(inp: PhotosStampInput, ctx) -> CommandResult:  # noqa: ANN001
    from PIL import Image

    from civilpy.general.photos import add_timestamp, get_photo_creation_date

    files = _photo_files(inp.path)
    dest = _dest_folder(inp.dest, inp.path, "Stamped_Photos")
    rows, skipped = [], []
    with ui.progress("Stamping photos", total=len(files)) as advance:
        for f in files:
            try:
                img = Image.open(f)
                date = get_photo_creation_date(img)
            except Exception:
                date = None
            if not date:
                skipped.append(f"{f.name}: no EXIF timestamp")
                advance(note=f.name)
                continue
            stamped = add_timestamp(img, date)
            if stamped is None:
                skipped.append(f"{f.name}: could not draw timestamp")
                advance(note=f.name)
                continue
            out = dest / f.name
            stamped.save(out)
            rows.append((f.name, date, str(out)))
            advance(note=f.name)
    if not rows:
        raise CliError(
            "no photos stamped — none had an EXIF timestamp to stamp"
        )

    table = ResultTable(
        title=f"Stamped into {dest}",
        columns=[Column("File"), Column("Timestamp"), Column("Output")],
        rows=rows,
        notes=[f"skipped {msg}" for msg in skipped],
    )
    return CommandResult(tables=[table])


SPECS = [
    CommandSpec(
        name="photos exif",
        summary="Extract timestamps, camera, and GPS from photo EXIF data",
        description=(
            "Reads EXIF metadata from an image or a folder of inspection "
            "photos: capture timestamp, camera make/model, pixel size, and "
            "GPS position converted to signed decimal degrees — ready for "
            "a photo location log or a GIS import."
        ),
        input_model=PhotosPathInput,
        runner="civilpy.cli.commands.photos:run_exif",
    ),
    CommandSpec(
        name="photos rename",
        summary="Batch-rename photos from a two-column spreadsheet",
        description=(
            "Copies photos into Renamed_Photos/ using a spreadsheet map: "
            "column A the current file path, column B the new name (no "
            "header row). Names are slugified — spaces and characters "
            "like '/', '#', ',' are cleaned — and the original extension "
            "is kept."
        ),
        input_model=PhotosRenameInput,
        runner="civilpy.cli.commands.photos:run_rename",
    ),
    CommandSpec(
        name="photos resize",
        summary="Resize photos to a fixed frame, preserving aspect ratio",
        description=(
            "Fits each photo inside the target width × height, padding "
            "with bars instead of stretching — the standard prep for "
            "report layouts and slide decks."
        ),
        input_model=PhotosResizeInput,
        runner="civilpy.cli.commands.photos:run_resize",
    ),
    CommandSpec(
        name="photos stamp",
        summary="Stamp each photo's EXIF date/time onto the image",
        description=(
            "Draws the capture date and time from EXIF metadata onto the "
            "bottom-right corner of each photo, writing stamped copies to "
            "a new folder. Photos without an EXIF timestamp are skipped "
            "and reported."
        ),
        input_model=PhotosStampInput,
        runner="civilpy.cli.commands.photos:run_stamp",
    ),
]
