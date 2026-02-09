"""Multi-family font build pipeline for Unito.

This module orchestrates the entire font build process, replacing the old merger.main()
as the top-level build entry point. It handles:

1. Phase 1: Prepare sources (download + instantiate variable fonts to statics)
2. Phase 2: Build base Unito family (merge 10base → 20symb → 30mult → 40cjkb → 50unif → 51unif)
3. Phase 3: Build CJK regional families (71hk, 72jp, 73kr, 74cn, 75tw)
4. Delivery: Copy all built fonts to fonts/ output directory

CRITICAL: Unlike the old merger.main(), this pipeline PRESERVES GSUB/GPOS from the
base font. Layout tables are NOT stripped.
"""
# this_file: src/unito/pipeline.py

from __future__ import annotations

import re
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .cache import ensure_dir
from .config import default_config
from .downloader import prepare_font_sources
from .exclude import load_control_file
from .merger import (
    get_source_fonts,
    get_unicode_to_glyph_map,
    get_upm,
    instantiate_font,
    is_truetype_font,
    merge_glyphs_from_font,
    rebuild_cmap,
    set_post_format_3,
    update_font_metadata,
)
from .subsetter import subset_to_reference
from .utils import project_root

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont

    from .config import UnitoConfig


# =============================================================================
# Build Configuration
# =============================================================================


@dataclass
class BuildVariant:
    """A font variant defined by name, weight, and width.

    Attributes:
        name: Style name like "Regular", "Bold", "Condensed", "BoldCondensed".
        wght: Weight axis value (400 for Regular, 700 for Bold).
        wdth: Width axis value (100 for Normal, 75 for Condensed).
    """

    name: str
    wght: int
    wdth: int


VARIANTS: list[BuildVariant] = [
    BuildVariant("Regular", 400, 100),
    BuildVariant("Bold", 700, 100),
    BuildVariant("Condensed", 400, 75),
    BuildVariant("BoldCondensed", 700, 75),
]


@dataclass
class FamilyConfig:
    """Configuration for building a font family.

    Attributes:
        name: Display name like "Unito", "Unito HK", etc.
        slug: Filename slug like "Unito", "UnitoHK", etc.
        source_dir: Source directory name like "60unito", "71hk", etc.
        cjk_font_path: Path to regional CJK variable font (for CJK families).
        subset_ref_path: Path to SourceHanSans OTF for subsetting (for CJK families).
        extra_fonts: Additional fonts to merge (e.g., NotoSerifTangut for KR).
    """

    name: str
    slug: str
    source_dir: str
    cjk_font_path: Path | None = None
    subset_ref_path: Path | None = None
    extra_fonts: list[Path] = field(default_factory=list)


# Mapping of source folder names to merge priority and exclusion settings
# Folder order determines merge priority (earlier = higher priority)
SOURCE_FOLDERS: list[str] = ["10base", "20symb", "30mult", "40cjkb", "50unif", "51unif"]

# CJK family configurations
CJK_FAMILIES: list[FamilyConfig] = [
    FamilyConfig(name="Unito HK", slug="UnitoHK", source_dir="71hk"),
    FamilyConfig(name="Unito JP", slug="UnitoJP", source_dir="72jp"),
    FamilyConfig(name="Unito KR", slug="UnitoKR", source_dir="73kr"),
    FamilyConfig(name="Unito CN", slug="UnitoCN", source_dir="74cn"),
    FamilyConfig(name="Unito TW", slug="UnitoTW", source_dir="75tw"),
]


# =============================================================================
# Utility Functions
# =============================================================================


def _strip_axis_tags(filename: str) -> str:
    """Extract base font name by stripping axis tags from filename.

    Examples:
        NotoSans[wdth,wght].ttf -> NotoSans
        NotoSansArabic[wght].ttf -> NotoSansArabic
        NotoSansSymbols2-Regular.ttf -> NotoSansSymbols2
    """
    stem = Path(filename).stem
    # Remove axis tag brackets: [wdth,wght] or [wght]
    stem = re.sub(r"\[[^\]]+\]", "", stem)
    # Remove style suffix if present: -Regular, -Bold, etc.
    stem = re.sub(r"-(Regular|Bold|Italic|Light|Medium|Thin|Black|SemiBold|ExtraBold)$", "", stem)
    return stem


def _get_static_font_name(font_path: Path, variant: BuildVariant) -> str:
    """Generate predictable static font filename.

    Args:
        font_path: Path to the source font file.
        variant: Build variant with name, wght, wdth.

    Returns:
        Static font filename like "NotoSans-Regular.ttf".
    """
    base_name = _strip_axis_tags(font_path.name)
    return f"{base_name}-{variant.name}.ttf"


def _update_family_metadata(
    font: TTFont,
    family_name: str,
    style_name: str,
) -> None:
    """Update font naming tables for a specific family.

    Args:
        font: The TTFont object to modify.
        family_name: The font family name (e.g., "Unito HK").
        style_name: The style name (e.g., "Regular", "Bold").
    """
    if "name" not in font:
        return

    name_table = font["name"]
    # Construct full name
    if style_name == "Regular":
        full_name = family_name
    else:
        full_name = f"{family_name} {style_name}"

    # PostScript name (no spaces)
    ps_name = f"{family_name.replace(' ', '')}-{style_name}"

    replacements = {
        1: family_name,  # Family name
        2: style_name,  # Subfamily name
        4: full_name,  # Full name
        6: ps_name,  # PostScript name
        16: family_name,  # Typographic family name
        17: style_name,  # Typographic subfamily name
    }

    for record in name_table.names:
        if record.nameID in replacements:
            try:
                record.toUnicode()
                name_table.setName(
                    replacements[record.nameID],
                    record.nameID,
                    record.platformID,
                    record.platEncID,
                    record.langID,
                )
            except UnicodeDecodeError:
                pass


# =============================================================================
# Phase 1: Prepare Sources
# =============================================================================


def instantiate_to_static(
    font_path: Path,
    output_dir: Path,
    variant: BuildVariant,
    cache_dir: Path | None = None,
) -> Path:
    """Instantiate a variable font to a static instance with predictable naming.

    If the font is already static (no fvar table), it is copied directly.
    If the font is variable, it is instantiated at the specified weight/width.

    Args:
        font_path: Path to the source font (variable or static TTF).
        output_dir: Directory where the static font will be saved.
        variant: Build variant specifying weight and width.
        cache_dir: Optional cache directory for instantiation.

    Returns:
        Path to the output static font: output_dir/{stem}-{variant.name}.ttf

    Example:
        instantiate_to_static(
            Path("10base/NotoSans[wdth,wght].ttf"),
            Path("10base/static"),
            BuildVariant("Regular", 400, 100),
        )
        # Returns: 10base/static/NotoSans-Regular.ttf
    """
    ensure_dir(output_dir)
    output_name = _get_static_font_name(font_path, variant)
    output_path = output_dir / output_name

    # Skip if already exists
    if output_path.exists():
        print(f"  Cached: {output_path.name}")
        return output_path

    # Use merger's instantiate_font which handles caching
    font = instantiate_font(
        font_path,
        wght=variant.wght,
        wdth=variant.wdth,
        cache_dir=cache_dir,
    )

    # Save to output location
    font.save(str(output_path))
    font.close()

    print(f"  Instantiated: {font_path.name} -> {output_path.name}")
    return output_path


def prepare_source_folder(
    sources_dir: Path,
    folder_name: str,
    variant: BuildVariant,
    cache_dir: Path,
) -> list[Path]:
    """Prepare static fonts for a source folder.

    Downloads fonts if needed, then instantiates variable fonts to statics.

    Args:
        sources_dir: Root sources directory.
        folder_name: Source folder name (e.g., "10base", "20symb").
        variant: Build variant for instantiation.
        cache_dir: Cache directory for downloads and instantiation.

    Returns:
        List of paths to static font files ready for merging.
    """
    folder_path = sources_dir / folder_name
    static_dir = folder_path / "static"
    ensure_dir(static_dir)

    if not folder_path.exists():
        print(f"  WARNING: Source folder not found: {folder_path}")
        return []

    source_fonts = get_source_fonts(folder_path)
    if not source_fonts:
        print(f"  No fonts found in {folder_name}")
        return []

    print(f"  Preparing {len(source_fonts)} fonts from {folder_name}...")

    static_paths: list[Path] = []
    for font_path in source_fonts:
        try:
            static_path = instantiate_to_static(
                font_path,
                static_dir,
                variant,
                cache_dir=cache_dir,
            )
            static_paths.append(static_path)
        except Exception as exc:
            print(f"    ERROR instantiating {font_path.name}: {exc}")

    return static_paths


def prepare_cjk_family_sources(
    sources_dir: Path,
    family: FamilyConfig,
    variant: BuildVariant,
    cache_dir: Path,
) -> list[Path]:
    """Prepare CJK regional font statics: subset to reference glyphset, then instantiate.

    For each CJK family (e.g., Unito HK), the pipeline:
    1. Finds the CJK variable font in {source_dir}/ (e.g., NotoSansHK[wght].ttf)
    2. Finds the SourceHanSans reference OTF for glyphset matching
    3. Subsets the variable font to only include codepoints present in the reference
    4. Instantiates the subset font to a static variant

    Args:
        sources_dir: Root sources directory.
        family: CJK family configuration with source_dir and subset_ref info.
        variant: Build variant for instantiation.
        cache_dir: Cache directory.

    Returns:
        List of paths to prepared static fonts.
    """
    family_dir = sources_dir / family.source_dir
    static_dir = family_dir / "static"
    ensure_dir(static_dir)

    if not family_dir.exists():
        print(f"  WARNING: CJK family dir not found: {family_dir}")
        return []

    source_fonts = get_source_fonts(family_dir)
    if not source_fonts:
        print(f"  No CJK fonts found in {family.source_dir}")
        return []

    # Find reference OTF for subsetting
    ref_otfs = list(family_dir.glob("*.otf"))
    ref_path = ref_otfs[0] if ref_otfs else None

    static_paths: list[Path] = []
    for font_path in source_fonts:
        output_name = _get_static_font_name(font_path, variant)
        output_path = static_dir / output_name

        if output_path.exists():
            print(f"  Cached: {output_path.name}")
            static_paths.append(output_path)
            continue

        if ref_path:
            # Subset to reference glyphset, then instantiate
            print(f"  Subsetting {font_path.name} to {ref_path.name} glyphset...")
            try:
                result = subset_to_reference(
                    source_path=font_path,
                    reference_path=ref_path,
                    output_path=output_path,
                    wght=variant.wght,
                    wdth=variant.wdth,
                )
                static_paths.append(result)
            except Exception as exc:
                print(f"    ERROR subsetting {font_path.name}: {exc}")
        else:
            # No reference — just instantiate directly
            try:
                result = instantiate_to_static(font_path, static_dir, variant, cache_dir)
                static_paths.append(result)
            except Exception as exc:
                print(f"    ERROR instantiating {font_path.name}: {exc}")

    return static_paths


# =============================================================================
# Phase 2: Build Base Unito Family
# =============================================================================


def build_base_unito(
    sources_dir: Path,
    variant: BuildVariant,
    cache_dir: Path,
    control_file: Path | None = None,
) -> Path:
    """Build one variant of the base Unito family.

    Pipeline:
    1. Load base from 10base/static/{variant}
    2. Merge 20symb statics (symbols, emoji)
    3. Merge 30mult statics (world scripts)
    4. Merge 40cjkb statics (CJK base, with Han/Hangul/Tangut exclusion)
    5. Merge 50unif fonts (UnifontEX, with Han/Hangul/Tangut exclusion)
    6. Merge 51unif fonts (Unifont, with Han/Hangul/Tangut exclusion)
    7. Finalize (metadata, cmap, post format)
    8. Save to 60unito/build/Unito-{variant}.ttf

    CRITICAL: This function PRESERVES GSUB/GPOS from the base font.
    Unlike the old merger.main(), layout tables are NOT removed.

    Args:
        sources_dir: Root sources directory.
        variant: Build variant to process.
        cache_dir: Cache directory for instantiation.
        control_file: Optional YAML control file for additional exclusions.

    Returns:
        Path to the built font file.
    """
    print(f"\n{'=' * 60}")
    print(f"Building Unito {variant.name}")
    print(f"{'=' * 60}")

    # Load control file exclusions if provided
    extra_excludes: set[int] | None = None
    if control_file and control_file.exists():
        extra_excludes = load_control_file(control_file)
        print(f"  Loaded {len(extra_excludes)} exclusions from control file")

    # Setup output directory
    build_dir = sources_dir / "60unito" / "build"
    ensure_dir(build_dir)
    output_path = build_dir / f"Unito-{variant.name}.ttf"

    if output_path.exists():
        print(f"  {output_path.name} already exists. Skipping build.")
        return output_path

    # ==========================================================================
    # Step 1: Load base font from 10base
    # ==========================================================================
    print("\n[1/7] Loading base font from 10base...")
    base_static_dir = sources_dir / "10base" / "static"
    base_fonts = list(base_static_dir.glob(f"*-{variant.name}.ttf"))

    if not base_fonts:
        # Try to instantiate from source
        base_source = sources_dir / "10base"
        source_fonts = get_source_fonts(base_source)
        if not source_fonts:
            raise FileNotFoundError(f"No base fonts found in {base_source}")

        base_path = instantiate_to_static(
            source_fonts[0],
            base_static_dir,
            variant,
            cache_dir=cache_dir,
        )
    else:
        base_path = base_fonts[0]

    print(f"  Base font: {base_path.name}")
    target_font = instantiate_font(base_path, wght=variant.wght, wdth=variant.wdth, cache_dir=None)

    if not is_truetype_font(target_font):
        raise ValueError(f"Base font is not TrueType: {base_path}")

    master_upm = get_upm(target_font)
    initial_glyphs = len(target_font.getGlyphOrder())
    initial_cmap = len(get_unicode_to_glyph_map(target_font))
    print(f"  Master UPM: {master_upm}")
    print(f"  Base font: {initial_glyphs} glyphs, {initial_cmap} codepoints")

    total_glyphs_added = 0
    total_codepoints_added = 0

    # ==========================================================================
    # Step 2: Merge 20symb (symbols, emoji)
    # ==========================================================================
    print("\n[2/7] Merging 20symb (symbols, emoji)...")
    symb_static_dir = sources_dir / "20symb" / "static"
    for font_path in sorted(symb_static_dir.glob(f"*-{variant.name}.ttf")):
        source_font = instantiate_font(font_path, wght=variant.wght, wdth=variant.wdth)
        g, c = merge_glyphs_from_font(
            source_font,
            target_font,
            font_path.name,
            exclude_hani=True,
            exclude_hang=False,
            is_base_font=False,
        )
        total_glyphs_added += g
        total_codepoints_added += c
        source_font.close()

    # ==========================================================================
    # Step 3: Merge 30mult (world scripts)
    # ==========================================================================
    print("\n[3/7] Merging 30mult (world scripts)...")
    mult_static_dir = sources_dir / "30mult" / "static"
    mult_fonts = sorted(mult_static_dir.glob(f"*-{variant.name}.ttf"))
    print(f"  Found {len(mult_fonts)} fonts to merge")

    for font_path in mult_fonts:
        source_font = instantiate_font(font_path, wght=variant.wght, wdth=variant.wdth)
        g, c = merge_glyphs_from_font(
            source_font,
            target_font,
            font_path.name,
            exclude_hani=True,
            exclude_hang=False,
            is_base_font=False,
        )
        total_glyphs_added += g
        total_codepoints_added += c
        source_font.close()

    # ==========================================================================
    # Step 4: Merge 40cjkb (CJK base, excluding Han/Hangul/Tangut)
    # ==========================================================================
    print("\n[4/7] Merging 40cjkb (CJK base, excluding Han/Hangul)...")
    cjkb_static_dir = sources_dir / "40cjkb" / "static"
    cjkb_fonts = sorted(cjkb_static_dir.glob(f"*-{variant.name}.ttf"))
    print(f"  Found {len(cjkb_fonts)} fonts to merge")

    for font_path in cjkb_fonts:
        source_font = instantiate_font(font_path, wght=variant.wght, wdth=variant.wdth)
        g, c = merge_glyphs_from_font(
            source_font,
            target_font,
            font_path.name,
            exclude_hani=True,  # Strictly exclude Han
            exclude_hang=True,  # Strictly exclude Hangul
            exclude_tang=True,  # Strictly exclude Tangut
            is_base_font=False,
        )
        total_glyphs_added += g
        total_codepoints_added += c
        source_font.close()

    # ==========================================================================
    # Step 5/6: Merge 50unif and 51unif (excluding Han/Hangul/Tangut)
    # ==========================================================================
    unif_sources = [("50unif", "UnifontEX"), ("51unif", "Unifont")]
    for step_index, (unif_dir_name, unif_label) in enumerate(unif_sources, start=5):
        print(
            f"\n[{step_index}/7] Merging {unif_dir_name} ({unif_label}, excluding Han/Hangul/Tangut)..."
        )
        unif_static_dir = sources_dir / unif_dir_name / "static"
        unif_fonts = sorted(unif_static_dir.glob(f"*-{variant.name}.ttf"))

        # Also check for non-variable fonts directly in folder
        unif_folder = sources_dir / unif_dir_name
        for font_path in get_source_fonts(unif_folder):
            if (unif_static_dir / _get_static_font_name(font_path, variant)).exists():
                continue
            unif_fonts.append(font_path)

        print(f"  Found {len(unif_fonts)} fonts to merge")

        for font_path in unif_fonts:
            source_font = instantiate_font(font_path, wght=variant.wght, wdth=variant.wdth)
            g, c = merge_glyphs_from_font(
                source_font,
                target_font,
                font_path.name,
                exclude_hani=True,  # Always exclude Han from Unifont layers
                exclude_hang=True,  # Always exclude Hangul from Unifont layers
                exclude_tang=True,  # Always exclude Tangut from Unifont layers
                is_base_font=False,
            )
            total_glyphs_added += g
            total_codepoints_added += c
            source_font.close()

    # ==========================================================================
    # Step 7: Finalize font
    # ==========================================================================
    print("\n[7/7] Finalizing font...")

    # CRITICAL: Do NOT call remove_layout_tables here!
    # We preserve GSUB/GPOS from the base font.
    print("  Preserving GSUB/GPOS layout tables from base font")

    print("  Updating font metadata...")
    update_font_metadata(target_font, variant.name)

    print("  Rebuilding cmap table...")
    rebuild_cmap(target_font)

    print("  Setting post table to format 3.0 (no glyph names)...")
    set_post_format_3(target_font)

    final_glyphs = len(target_font.getGlyphOrder())
    final_cmap = len(get_unicode_to_glyph_map(target_font))

    print(f"  Saving to: {output_path}")
    target_font.save(str(output_path))
    target_font.close()

    print(f"\n{'=' * 60}")
    print("COMPLETE!")
    print(f"{'=' * 60}")
    print(f"  Output: {output_path}")
    print(f"  Base glyphs: {initial_glyphs}")
    print(f"  Glyphs added: {total_glyphs_added}")
    print(f"  Final glyphs: {final_glyphs}")
    print(f"  Base codepoints: {initial_cmap}")
    print(f"  Codepoints added: {total_codepoints_added}")
    print(f"  Final codepoints: {final_cmap}")
    print(f"  File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

    return output_path


# =============================================================================
# Phase 3: Build CJK Regional Families
# =============================================================================


def build_cjk_family(
    sources_dir: Path,
    family: FamilyConfig,
    variant: BuildVariant,
    cache_dir: Path,
) -> Path:
    """Build one variant of a CJK regional family.

    Pipeline:
    1. Load Unito base from 60unito/build/
    2. Load CJK regional font (already subset + instantiated)
    3. Merge CJK glyphs into Unito base
    4. If extra_fonts (e.g., Tangut): merge those too
    5. Update metadata for family name
    6. Save to {source_dir}/build/{FamilySlug}-{variant}.ttf

    Args:
        sources_dir: Root sources directory.
        family: Family configuration with CJK paths.
        variant: Build variant to process.
        cache_dir: Cache directory for instantiation.

    Returns:
        Path to the built font file.
    """
    print(f"\n{'=' * 60}")
    print(f"Building {family.name} {variant.name}")
    print(f"{'=' * 60}")

    # Setup output directory
    build_dir = sources_dir / family.source_dir / "build"
    ensure_dir(build_dir)
    output_path = build_dir / f"{family.slug}-{variant.name}.ttf"

    if output_path.exists():
        print(f"  {output_path.name} already exists. Skipping build.")
        return output_path

    # ==========================================================================
    # Step 1: Load Unito base
    # ==========================================================================
    print("\n[1/4] Loading Unito base...")
    base_path = sources_dir / "60unito" / "build" / f"Unito-{variant.name}.ttf"

    if not base_path.exists():
        raise FileNotFoundError(f"Unito base not found: {base_path}")

    from fontTools.ttLib import TTFont

    target_font = TTFont(base_path)

    initial_glyphs = len(target_font.getGlyphOrder())
    initial_cmap = len(get_unicode_to_glyph_map(target_font))
    print(f"  Base: {initial_glyphs} glyphs, {initial_cmap} codepoints")

    total_glyphs_added = 0
    total_codepoints_added = 0

    # ==========================================================================
    # Step 2: Load and merge CJK regional font
    # ==========================================================================
    print("\n[2/4] Merging CJK regional font...")
    cjk_static_dir = sources_dir / family.source_dir / "static"

    if cjk_static_dir.exists():
        cjk_fonts = sorted(cjk_static_dir.glob(f"*-{variant.name}.ttf"))
        print(f"  Found {len(cjk_fonts)} CJK regional fonts")

        for font_path in cjk_fonts:
            source_font = instantiate_font(font_path, wght=variant.wght, wdth=variant.wdth)
            g, c = merge_glyphs_from_font(
                source_font,
                target_font,
                font_path.name,
                exclude_hani=False,  # Include Han for CJK families
                exclude_hang=False,  # Include Hangul for CJK families
                is_base_font=False,
            )
            total_glyphs_added += g
            total_codepoints_added += c
            source_font.close()
    else:
        print(f"  WARNING: CJK static dir not found: {cjk_static_dir}")

    # ==========================================================================
    # Step 3: Merge extra fonts (e.g., NotoSerifTangut for KR)
    # ==========================================================================
    if family.extra_fonts:
        print(f"\n[3/4] Merging {len(family.extra_fonts)} extra fonts...")
        for font_path in family.extra_fonts:
            if not font_path.exists():
                print(f"  WARNING: Extra font not found: {font_path}")
                continue

            source_font = instantiate_font(
                font_path,
                wght=variant.wght,
                wdth=variant.wdth,
                cache_dir=cache_dir,
            )
            g, c = merge_glyphs_from_font(
                source_font,
                target_font,
                font_path.name,
                exclude_hani=False,
                exclude_hang=False,
                is_base_font=False,
            )
            total_glyphs_added += g
            total_codepoints_added += c
            source_font.close()
    else:
        print("\n[3/4] No extra fonts to merge")

    # ==========================================================================
    # Step 4: Finalize font
    # ==========================================================================
    print("\n[4/4] Finalizing font...")

    print(f"  Updating metadata for {family.name}...")
    _update_family_metadata(target_font, family.name, variant.name)

    print("  Rebuilding cmap table...")
    rebuild_cmap(target_font)

    print("  Setting post table to format 3.0...")
    set_post_format_3(target_font)

    final_glyphs = len(target_font.getGlyphOrder())
    final_cmap = len(get_unicode_to_glyph_map(target_font))

    print(f"  Saving to: {output_path}")
    target_font.save(str(output_path))
    target_font.close()

    print(f"\n{'=' * 60}")
    print("COMPLETE!")
    print(f"{'=' * 60}")
    print(f"  Output: {output_path}")
    print(f"  Base glyphs: {initial_glyphs}")
    print(f"  Glyphs added: {total_glyphs_added}")
    print(f"  Final glyphs: {final_glyphs}")
    print(f"  Codepoints added: {total_codepoints_added}")
    print(f"  Final codepoints: {final_cmap}")
    print(f"  File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

    return output_path


# =============================================================================
# Phase 4: Delivery
# =============================================================================


def deliver(
    sources_dir: Path,
    output_dir: Path,
) -> list[Path]:
    """Copy all built fonts to the output directory.

    Copies fonts from:
    - 60unito/build/*.ttf
    - 71hk/build/*.ttf
    - 72jp/build/*.ttf
    - 73kr/build/*.ttf
    - 74cn/build/*.ttf
    - 75tw/build/*.ttf

    Args:
        sources_dir: Root sources directory containing build folders.
        output_dir: Destination directory (typically fonts/ttf/).

    Returns:
        List of paths to copied font files in output_dir.
    """
    print(f"\n{'=' * 60}")
    print("Delivering fonts")
    print(f"{'=' * 60}")

    ensure_dir(output_dir)

    build_dirs = [
        "60unito",
        "71hk",
        "72jp",
        "73kr",
        "74cn",
        "75tw",
    ]

    delivered: list[Path] = []

    for build_dir_name in build_dirs:
        build_path = sources_dir / build_dir_name / "build"
        if not build_path.exists():
            continue

        for font_file in sorted(build_path.glob("*.ttf")):
            dest_path = output_dir / font_file.name
            shutil.copy2(font_file, dest_path)
            delivered.append(dest_path)
            print(f"  Copied: {font_file.name}")

    print(f"\n  Total: {len(delivered)} fonts delivered to {output_dir}")
    return delivered


# =============================================================================
# Main Entry Point
# =============================================================================


def _build_variant_worker(
    variant_name: str,
    sources_dir_str: str,
    cache_dir_str: str,
    build_cjk: bool,
) -> dict[str, list[str]]:
    """Worker function for parallel variant building.

    Args:
        variant_name: Name of the variant to build.
        sources_dir_str: String path to sources directory.
        cache_dir_str: String path to cache directory.
        build_cjk: Whether to also build CJK families.

    Returns:
        Dict mapping family name to list of output path strings.
    """
    sources_dir = Path(sources_dir_str)
    cache_dir = Path(cache_dir_str)

    # Find the variant
    variant = next((v for v in VARIANTS if v.name == variant_name), None)
    if variant is None:
        return {}

    results: dict[str, list[str]] = {}

    # Build base Unito
    try:
        output_path = build_base_unito(sources_dir, variant, cache_dir)
        results["Unito"] = [str(output_path)]
    except Exception as exc:
        print(f"ERROR building Unito {variant.name}: {exc}")
        results["Unito"] = []

    # Build CJK families if requested
    if build_cjk:
        for family in CJK_FAMILIES:
            try:
                output_path = build_cjk_family(sources_dir, family, variant, cache_dir)
                results[family.name] = [str(output_path)]
            except Exception as exc:
                print(f"ERROR building {family.name} {variant.name}: {exc}")
                results[family.name] = []

    return results


def build_all(
    sources_dir: Path | None = None,
    cache_dir: Path | None = None,
    download: bool = True,
    force: bool = False,
    families: list[str] | None = None,
    variants: list[str] | None = None,
    parallel: bool = True,
    build_cjk: bool = False,
    config: UnitoConfig | None = None,
) -> dict[str, list[Path]]:
    """Build all font families.

    This is the main entry point for the Unito build pipeline.

    Args:
        sources_dir: Root sources directory (default: project_root/sources).
        cache_dir: Cache directory (default: sources/cache).
        download: Whether to download fonts first.
        force: Force re-download/re-process.
        families: Filter to specific families (default: all).
        variants: Filter to specific variants (default: all 4).
        parallel: Use parallel processing (one process per variant).
        build_cjk: Whether to build CJK regional families.
        config: Optional UnitoConfig for downloader.

    Returns:
        Dict mapping family name to list of output Paths.
    """
    # Setup paths
    cfg = config or default_config()
    if sources_dir is None:
        sources_dir = cfg.paths.root / "sources"
    if cache_dir is None:
        cache_dir = sources_dir / "cache"

    ensure_dir(sources_dir)
    ensure_dir(cache_dir)

    print("\n" + "=" * 60)
    print("UNITO MULTI-FAMILY BUILD PIPELINE")
    print("=" * 60)
    print(f"  Sources: {sources_dir}")
    print(f"  Cache: {cache_dir}")
    print(f"  Download: {download}")
    print(f"  Force: {force}")
    print(f"  Parallel: {parallel}")
    print(f"  Build CJK: {build_cjk}")

    # ==========================================================================
    # Phase 0: Download sources
    # ==========================================================================
    if download:
        print("\n[PHASE 0] Downloading font sources...")
        prepare_font_sources(force=force, config=cfg)

    # ==========================================================================
    # Phase 1: Prepare source folders (instantiate statics)
    # ==========================================================================
    print("\n[PHASE 1] Preparing source folders...")

    # Determine which variants to build
    target_variants = VARIANTS
    if variants:
        target_variants = [v for v in VARIANTS if v.name in variants]

    if not target_variants:
        print("  ERROR: No valid variants specified")
        return {}

    print(f"  Building variants: {[v.name for v in target_variants]}")

    # Prepare each source folder for each variant
    for folder_name in SOURCE_FOLDERS:
        folder_path = sources_dir / folder_name
        if not folder_path.exists():
            # Map old folder names to new if needed
            old_mapping = {
                "10base": "01",
                "20symb": "02",
                "30mult": "03",
                "40cjkb": "04",
                "50unif": "05",
            }
            old_name = old_mapping.get(folder_name)
            if old_name:
                old_path = sources_dir / "01in" / old_name
                if old_path.exists():
                    # Create symlink or copy
                    ensure_dir(folder_path)
                    for font in get_source_fonts(old_path):
                        dest = folder_path / font.name
                        if not dest.exists():
                            shutil.copy2(font, dest)
                    print(f"  Migrated fonts from {old_path} to {folder_path}")

        print(f"\n  Preparing {folder_name}...")
        for variant in target_variants:
            prepare_source_folder(sources_dir, folder_name, variant, cache_dir)

    # Prepare CJK family sources (subset + instantiate) if building CJK
    if build_cjk:
        print("\n  Preparing CJK family sources...")
        for family in CJK_FAMILIES:
            if families and family.name not in families and family.slug not in families:
                continue
            print(f"\n  Preparing {family.name}...")
            for variant in target_variants:
                prepare_cjk_family_sources(sources_dir, family, variant, cache_dir)

    # ==========================================================================
    # Phase 2: Build base Unito family
    # ==========================================================================
    print("\n[PHASE 2] Building base Unito family...")

    results: dict[str, list[Path]] = {"Unito": []}

    if parallel and len(target_variants) > 1:
        # Build variants in parallel
        import os

        max_workers = min(os.cpu_count() or 1, len(target_variants))

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _build_variant_worker,
                    variant.name,
                    str(sources_dir),
                    str(cache_dir),
                    build_cjk,
                ): variant
                for variant in target_variants
            }

            for future in as_completed(futures):
                variant = futures[future]
                try:
                    variant_results = future.result()
                    for family_name, paths in variant_results.items():
                        if family_name not in results:
                            results[family_name] = []
                        results[family_name].extend(Path(p) for p in paths)
                except Exception as exc:
                    print(f"ERROR building {variant.name}: {exc}")
    else:
        # Build sequentially
        for variant in target_variants:
            try:
                output_path = build_base_unito(sources_dir, variant, cache_dir)
                results["Unito"].append(output_path)
            except Exception as exc:
                print(f"ERROR building Unito {variant.name}: {exc}")

        # ==========================================================================
        # Phase 3: Build CJK families (if requested)
        # ==========================================================================
        if build_cjk:
            print("\n[PHASE 3] Building CJK regional families...")

            for family in CJK_FAMILIES:
                # Filter by requested families
                if families and family.name not in families and family.slug not in families:
                    continue

                results[family.name] = []

                for variant in target_variants:
                    try:
                        output_path = build_cjk_family(sources_dir, family, variant, cache_dir)
                        results[family.name].append(output_path)
                    except Exception as exc:
                        print(f"ERROR building {family.name} {variant.name}: {exc}")

    # Print summary
    print("\n" + "=" * 60)
    print("BUILD SUMMARY")
    print("=" * 60)

    total_fonts = 0
    for family_name, paths in results.items():
        if paths:
            print(f"  {family_name}: {len(paths)} variants")
            total_fonts += len(paths)

    print(f"\n  Total: {total_fonts} fonts built")

    return results


# =============================================================================
# CLI Entry Point (Optional)
# =============================================================================


def main() -> None:
    """Command-line entry point for the pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Unito multi-family font build pipeline")
    parser.add_argument(
        "--sources",
        type=Path,
        help="Root sources directory",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        help="Cache directory",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Skip downloading fonts",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download/re-process",
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=["Regular", "Bold", "Condensed", "BoldCondensed"],
        help="Build only specific variants",
    )
    parser.add_argument(
        "--families",
        nargs="+",
        help="Build only specific families",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel processing",
    )
    parser.add_argument(
        "--cjk",
        action="store_true",
        help="Build CJK regional families",
    )
    parser.add_argument(
        "--deliver",
        type=Path,
        help="Copy built fonts to output directory",
    )

    args = parser.parse_args()

    # Build fonts
    results = build_all(
        sources_dir=args.sources,
        cache_dir=args.cache,
        download=not args.no_download,
        force=args.force,
        families=args.families,
        variants=args.variants,
        parallel=not args.no_parallel,
        build_cjk=args.cjk,
    )

    # Deliver if requested
    if args.deliver and results:
        root = project_root()
        sources_dir = args.sources or (root / "sources")
        deliver(sources_dir, args.deliver)


if __name__ == "__main__":
    main()
