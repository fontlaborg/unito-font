# AGENTS.md - Unito Architecture and Extension Guide

## Project Overview
Unito is a Pan-Unicode font builder that merges multiple open-source fonts (primarily Noto, Unifont, and UnifontEX) into a single, comprehensive font family. It handles downloading, caching, instantiation, and merging of fonts based on a YAML configuration.

## Project Architecture
The core logic resides in `src/unito/` and consists of the following components:

### 1. Configuration (`config.py` & `font_sources.yaml`)
- **Role**: Defines the blueprint for the font.
- **File**: `src/unito/font_sources.yaml`
- **Logic**: `config.py` parses this YAML file, resolving paths and validating sources.
- **Structure**:
  - `repos`: Base URLs for font repositories (Google Fonts, Unifoundry, etc.).
  - `sources`: Organized into folders (01-06) determining priority and coverage.
  - `output`: Defines family name and variants (Regular, Bold, Condensed, BoldCondensed).
  - `build`: Global build settings (cache dirs, output dirs).

### 2. Downloader (`downloader.py`)
- **Role**: Fetches font files from remote repositories.
- **Logic**: 
  - Supports GitHub raw file downloads and direct URLs.
  - Uses `sources/cache/` to store downloaded files, preventing redundant network requests.
  - Handles versioning and file integrity checks where applicable.

### 3. Cache Manager (`cache.py`)
- **Role**: Manages local storage of intermediate files.
- **Logic**:
  - Ensures downloaded fonts are available for the merger.
  - Handles "instantiation" (converting variable fonts to static instances like Regular/Bold).
  - Stores files in `sources/cache/`.

### 4. Merger (`merger.py`)
- **Role**: The core engine that combines fonts.
- **Logic**:
  - Takes a list of source fonts (from `config.py`).
  - Merges them in a specific order (Folder 01 has highest priority, Folder 06 lowest).
  - Resolves glyph conflicts: If a glyph exists in a higher-priority font, it keeps that version.
  - Handles metrics, names, and OpenType tables (OS/2, hhea, name, etc.).
  - Uses `fonttools` for low-level font manipulation.

## Font Sources Structure
Fonts are organized into logical "folders" in `font_sources.yaml`. The merge process respects this order (usually 01 is the base, filling gaps with subsequent folders).

- **Folder 01 (Base)**: Noto Sans Variable (Primary Latin/Greek/Cyrillic).
- **Folder 02 (Symbols)**: Noto Emoji, Noto Sans Symbols (Iconography).
- **Folder 03 (World)**: Massive collection of Noto Sans scripts (Arabic, Devanagari, Thai, etc.).
- **Folder 04 (CJK)**: Noto Sans CJK (Chinese, Japanese, Korean) - typically large files.
- **Folder 05 (UnifontEX)**: UnifontEX (Bitmap-like outline fallback).
- **Folder 06 (Unifont)**: Original Unifont (Requires OTF->TTF conversion).
- **Hani**: Special source for Han frequency analysis (Noto Sans SC, used for CN family).

## Data Flow
1. **Config Load**: `unito-build` starts, reads `font_sources.yaml`.
2. **Download**: Checks `sources/cache/`. If missing, downloads fonts via `downloader.py`.
3. **Instantiation**: Variable fonts (e.g., `NotoSans[wdth,wght].ttf`) are instantiated into static TTFs (e.g., `NotoSans-Regular.ttf`) using `fonttools`.
4. **Merge**: 
   - Starts with an empty font or the base font (Folder 01).
   - Iteratively merges fonts from Folders 02 -> 06.
   - Glyphs are added only if they don't already exist (or based on specific overwrite rules).
5. **Output**: Final TTF files are saved to `fonts/ttf/`.

## How to Extend

### Adding New Fonts
1. Open `src/unito/font_sources.yaml`.
2. Locate the appropriate `folder_XX` section (or create a new one if it's a distinct category).
3. Add an entry under `fonts`:
   ```yaml
   - path: "path/to/font-in-repo.ttf"
     description: "Description of the font"
   ```
   *Note: If the font is in a new repository, define it under `repos` first.*

### Modifying Merge Logic
1. Edit `src/unito/merger.py`.
2. Key areas to check:
   - `merge_fonts()`: The main loop iterating through sources.
   - Conflict resolution strategies: How duplicate glyphs are handled.
   - Table merging: Logic for combining `GSUB`/`GPOS` or metric tables.

### Adding Build Steps
1. Edit `scripts/build.py` or `src/unito/cli.py`.
2. Add pre-processing (before merge) or post-processing (after merge) steps.
3. Example: Running a script to fix specific glyph issues before merging.
