# Unito

**A pan-Unicode glyph collection** — 6 families · 24 fonts · SIL Open Font License

Unito merges hundreds of [Noto](https://fonts.google.com/noto) fonts into single files that provide **default glyph forms** for Unicode codepoints. It does not include script-specific OpenType shaping rules (GSUB/GPOS) necessary for correct orthographic text in complex scripts — use Noto when you need proper text rendering.

Includes [Unifont](https://unifoundry.com/unifont/) glyphs for the newest Unicode additions not yet supported by Noto. Only some glyphs vary across styles — many scripts share the same form regardless of weight or width.

> **Not a text font.** Unito is a glyph collection and Unicode reference, not a Noto replacement.

## Families

Each family adds region-specific CJK glyphs to the base Unito codepoint set. All families ship in four styles: **Regular**, **Bold**, **Condensed**, and **Bold Condensed**.

| Family | Description |
|--------|-------------|
| **Unito** | Base — all Unicode scripts except Hangul, Tangut, and Han. Latin, Cyrillic, Greek, Arabic, Hebrew, Devanagari, Unifont, and hundreds more. |
| **Unito JP** | Japanese — adds Japanese Kanji to the base set. |
| **Unito CN** | Simplified Chinese — adds Simplified Chinese Hanzi. |
| **Unito HK** | Hong Kong — adds Chinese Hanzi for Hong Kong. |
| **Unito TW** | Taiwan — adds Traditional Chinese Hanzi for Taiwan. |
| **Unito KR** | Korean — adds Hangul, Hanja, and Tangut. |

## Download

All fonts are free under the [SIL Open Font License](OFL.txt). Click any link to download the TTF directly from GitHub.

### Unito (Base)

- [Unito-Regular.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/Unito-Regular.ttf)
- [Unito-Bold.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/Unito-Bold.ttf)
- [Unito-Condensed.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/Unito-Condensed.ttf)
- [Unito-BoldCondensed.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/Unito-BoldCondensed.ttf)

### Unito JP (Japanese)

- [UnitoJP-Regular.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoJP-Regular.ttf)
- [UnitoJP-Bold.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoJP-Bold.ttf)
- [UnitoJP-Condensed.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoJP-Condensed.ttf)
- [UnitoJP-BoldCondensed.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoJP-BoldCondensed.ttf)

### Unito CN (Simplified Chinese)

- [UnitoCN-Regular.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoCN-Regular.ttf)
- [UnitoCN-Bold.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoCN-Bold.ttf)
- [UnitoCN-Condensed.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoCN-Condensed.ttf)
- [UnitoCN-BoldCondensed.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoCN-BoldCondensed.ttf)

### Unito HK (Hong Kong)

- [UnitoHK-Regular.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoHK-Regular.ttf)
- [UnitoHK-Bold.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoHK-Bold.ttf)
- [UnitoHK-Condensed.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoHK-Condensed.ttf)
- [UnitoHK-BoldCondensed.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoHK-BoldCondensed.ttf)

### Unito TW (Taiwan)

- [UnitoTW-Regular.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoTW-Regular.ttf)
- [UnitoTW-Bold.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoTW-Bold.ttf)
- [UnitoTW-Condensed.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoTW-Condensed.ttf)
- [UnitoTW-BoldCondensed.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoTW-BoldCondensed.ttf)

### Unito KR (Korean)

- [UnitoKR-Regular.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoKR-Regular.ttf)
- [UnitoKR-Bold.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoKR-Bold.ttf)
- [UnitoKR-Condensed.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoKR-Condensed.ttf)
- [UnitoKR-BoldCondensed.ttf](https://github.com/fontlaborg/unito-font/raw/refs/heads/main/fonts/UnitoKR-BoldCondensed.ttf)

## Building

Fonts are built automatically by GitHub Actions — see the "Actions" tab for the latest build.

To build manually:

- `make build` — produce font files
- `make test` — run [FontBakery](https://github.com/googlefonts/fontbakery) quality assurance tests
- `make proof` — generate HTML proof files

Proof files and QA tests are also available via GitHub Actions at `https://fontlaborg.github.io/unito`.

## About

Unito is developed by [Fontlab Ltd](https://fontlab.org) and contributors.

- **Website**: [fontlaborg.github.io/unito](https://fontlaborg.github.io/unito/)
- **GitHub**: [github.com/fontlaborg/unito-font](https://github.com/fontlaborg/unito-font)

## License

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is available with a FAQ at https://openfontlicense.org

## Repository Layout

This font repository structure is inspired by [Unified Font Repository v0.3](https://github.com/unified-font-repository/Unified-Font-Repository), modified for the Google Fonts workflow.
