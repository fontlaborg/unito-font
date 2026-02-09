# Improve https://github.com/fontlaborg/unito-font

## YAML & Python

- ./font_sources.yaml is our main config 
- ./src/unito/ is the Python package that does the work

## Non-CJK family: 'Unito' 

Reorganize ./sources/

At this point we’re building a set of fonts 'Unito' that are non-Han, non-Hangul, non-Tangut. 

### ./sources/10base/

- ./sources/01in/01/NotoSans[wdth,wght].ttf should be in ./sources/10base/NotoSans[wdth,wght].ttf 
- there should be a control file in ./sources/10base/ that determines which Unicode codepoints (and corresponding glyphs) should be REMOVED from that font before subsequent phases 
- produce the necessary statics (static instantiated fonts) into ./sources/10base/static/
- NOTE: we must inherit the 'GSUB' and 'GPOS' tables from the base font. We don’t merge 'GSUB'/'GPOS' from other fonts. 

### ./sources/20symb/

- all fonts from ./sources/01in/02/ should be in ./sources/20symb/ 
- produce the necessary statics into ./sources/20symb/static/

### ./sources/30mult/

- all fonts from ./sources/01in/03/ should be in ./sources/30mult/ 
- we must ensure that the NotoSerifTangut-Regular.ttf font is not included here! 
- produce the necessary statics into ./sources/30mult/static/

### ./sources/40cjkb/

- the font from https://github.com/google/fonts/tree/main/ofl/notosansjp/NotoSansJP[wght].ttf should be in ./sources/40cjkb/ 
- we must ensure that we don’t merge any Hangul, Tangut or Han glyphs from this 
- produce the necessary statics into ./sources/40cjkb/static/

### ./sources/50unif/

- all fonts from ./sources/01in/05/ should be in ./sources/50unif/ 
- we must ensure that we don’t copy any Hangul, Tangut or Han glyphs here

### ./sources/60unito/ 

build 'Unito' fonts from the above constituents into ./sources/60unito/build/

## CJK families: 'Unito HK', 'Unito JP', 'Unito KR', 'Unito CN', 'Unito TW'

### ./sources/71hk/

- take ./notosanshk/NotoSansHK[wght].ttf from the https://github.com/google/fonts/tree/main/ofl/ repo
- subset it to the glyphset of https://github.com/adobe-fonts/source-han-sans/raw/refs/heads/release/SubsetOTF/HK/SourceHanSansHK-Regular.otf 
- save in ./sources/71hk/NotoSansHK[wght].ttf
- produce the necessary statics into ./sources/71hk/static/
- build 'Unito HK' fonts from ./sources/60unito/build/ statics and from ./sources/71hk/static/ fonts into ./sources/71hk/build/

### ./sources/72jp/

- take ./notosansjp/NotoSansJP[wght].ttf from the https://github.com/google/fonts/tree/main/ofl/ repo
- subset to https://github.com/adobe-fonts/source-han-sans/raw/refs/heads/release/SubsetOTF/JP/SourceHanSansJP-Regular.otf 
- save in ./sources/72jp/NotoSansJP[wght].ttf
- produce the necessary statics into ./sources/40cjkb/static/
- build 'Unito JP' fonts from ./sources/60unito/build/ statics and from ./sources/72jp/static/ fonts into ./sources/72jp/build/

### ./sources/73kr/

- NotoSerifTangut-Regular.ttf font from ./sources/01in/03/ should be in ./sources/60cjk2/NotoSerifTangut-Regular.ttf
- take ./notosanskr/NotoSansKR[wght].ttf from the https://github.com/google/fonts/tree/main/ofl/ repo
- subset to https://github.com/adobe-fonts/source-han-sans/raw/refs/heads/release/SubsetOTF/KR/SourceHanSansKR-Regular.otf 
- save in ./sources/73kr/NotoSansKR[wght].ttf
- produce the necessary statics into ./sources/73kr/static/
- build 'Unito KR' fonts from ./sources/60unito/build/ statics and from ./sources/60cjk2/NotoSerifTangut-Regular.ttf and from ./sources/73kr/static/ fonts into ./sources/73kr/build/

### ./sources/74cn/

- take ./notosanssc/NotoSansSC[wght].ttf from the https://github.com/google/fonts/tree/main/ofl/ repo
- subset to https://github.com/adobe-fonts/source-han-sans/raw/refs/heads/release/SubsetOTF/CN/SourceHanSansCN-Regular.otf
- save in ./sources/74cn/NotoSansSC[wght].ttf
- produce the necessary statics into ./sources/74cn/static/
- build 'Unito CN' fonts from ./sources/60unito/build/ statics and from ./sources/74cn/static/ fonts into ./sources/74cn/build/

### ./sources/75tw/

- take ./notosanstc/NotoSansTC[wght].ttf from the https://github.com/google/fonts/tree/main/ofl/ repo
- subset to https://github.com/adobe-fonts/source-han-sans/raw/refs/heads/release/SubsetOTF/TW/SourceHanSansTW-Regular.otf
- save in ./sources/75tw/NotoSansTC[wght].ttf
- produce the necessary statics into ./sources/75tw/static/
- build 'Unito TW' fonts from ./sources/60unito/build/ statics and from ./sources/75tw/static/ fonts into ./sources/75tw/build/

## Delivery

- Copy all 'Unito', 'Unito HK', 'Unito JP', 'Unito KR', 'Unito CN', 'Unito TW' fonts into ./fonts/

## NOTES

- Currently we build the statics into ./sources/cache/instantiation/ but we should do it with more predictable naming into the 'static' folders as shown above. 
- We should parallelize the work. 