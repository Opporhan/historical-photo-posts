# historical-photo-posts

[![CI](https://github.com/Opporhan/historical-photo-posts/actions/workflows/ci.yml/badge.svg)](https://github.com/Opporhan/historical-photo-posts/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

🇹🇷 [Türkçe README](README.tr.md)

Turn **public-domain black-and-white historical photographs** into ready-to-post **Instagram (4:5)** and
**TikTok/Reels (9:16)** content: found, rights-checked with evidence, gently restored, laid out with a title and a
short text, and captioned in Turkish and English.

![Demo: six generated posts](docs/demo.gif)

<p align="center">
  <img src="examples/klondike-1898/instagram_4x5.jpg" width="32%" alt="Klondike Gold Rush, 1898">
  <img src="examples/steerage-1907/instagram_4x5.jpg" width="32%" alt="The Steerage, 1907">
  <img src="examples/istanbul-selamlik/instagram_4x5.jpg" width="32%" alt="Selamlik ceremony, Istanbul, 1901">
</p>

![Before / after](examples/klondike-1898/before_after.jpg)

*Klondike Gold Rush, 1898: the original scan (left) and the enhanced version used in the post (right).*

## Contents

[Why](#why) · [Features](#features) · [Quick start](#quick-start) · [Commands](#commands) ·
[`posts.yaml` reference](#postsyaml-reference) · [Output](#output-per-post) · [How rights are verified](#how-rights-are-verified) ·
[Project layout](#project-layout) · [Limitations](#limitations) · [Development](#development) · [Türkçe özet](#türkçe-özet)

## Why

Historical photos perform well on social media, but "it is old, so it is free" is a dangerous assumption:
a photo can be public domain in the US and still protected in Turkey or the EU, and a "public domain" tag on a
hosting site is only an uploader's claim. This project makes the rights question part of the pipeline: a post
is only built when the evidence (public-domain template, author death year from Wikidata, US status) holds, and
the evidence is stored next to every output.

## Features

| Step | What it does |
|---|---|
| **Find** | Searches Wikimedia Commons (text or category crawl), NASA, Smithsonian and The Met; Europeana and NARA with free API keys. Drops logos, maps, documents, colour photographs and off-topic hits; writes a numbered contact sheet so a human picks the photo. |
| **Verify** | Reads the Commons license templates and the author's death year (Wikidata), applies the US 95-year cut-off and life+70 rule, and marks each post `verified`, `us-only` or `unverified`. Only `verified` posts are built. |
| **Restore** | Mild denoise, contrast and sharpening; Real-ESRGAN only for low-resolution sources and blended with the gentle result. **No colorization, no face reconstruction, no inpainting.** A `before_after.jpg` is written for every post. |
| **Compose** | 1080×1350 and 1080×1920 images: full-bleed photo, bottom gradient, letter-spaced label, high-contrast serif title (Playfair Display, Turkish-aware capitals), 3–5 line text and a small author · source · license line, inside the TikTok/Reels safe areas. |
| **Caption** | `caption.txt` (Turkish) and `caption_en.txt` with credit, source, license, hashtags and alt text. Optional Claude drafts with claim checking. |
| **Fact-check** | Checks the claims of each text against Wikipedia through the free MediaWiki API, no API key needed. |
| **Video** | An 8-second slow-zoom `reels_tiktok.mp4` per post (needs `ffmpeg`). |
| **Review** | `histposts review` writes an HTML page; `histposts doctor` is a pre-publication checklist. |

The tool never publishes anything: you review the output and post it yourself.

## Quick start

```bash
git clone https://github.com/Opporhan/historical-photo-posts.git
cd historical-photo-posts
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
./scripts/install_realesrgan.sh              # optional: AI upscaling for low-resolution sources
export HISTPOSTS_CONTACT="you@example.org"   # sent in the User-Agent; Wikimedia asks clients to identify themselves

histposts verify posts.yaml                  # which posts have verified rights?
histposts build posts.yaml --video           # -> paylasima-hazir/NN-name/...
histposts review                             # -> paylasima-hazir/index.html
histposts doctor posts.yaml                  # final checklist
```

`HISTPOSTS_CONTACT` is only sent to Wikimedia in the User-Agent header; it is never written to files.

## Commands

| Command | Purpose |
|---|---|
| `histposts search "Wright brothers" --before 1935` | Find candidates (`output/<query>/contact.jpg` + `candidates.json`). Colour photos are dropped unless `--allow-color`. |
| `histposts search "street" --category "Black and white photographs of Amsterdam"` | Crawl a Commons category. |
| `histposts check posts.yaml` | Quick `safe` / `review` / `blocked` license report. |
| `histposts verify posts.yaml --write docs/license-audit.md` | Evidence-based rights check with source links. |
| `histposts build posts.yaml` | Build all posts. Options: `--only NAME…`, `--strict`, `--video`, `--enhance auto\|gentle\|esrgan`, `--allow-unverified` (not recommended). |
| `histposts facts facts.yaml --write docs/fact-check.md` | Check text claims against Wikipedia (no key). |
| `histposts doctor posts.yaml` | Files, verified rights, text lengths, source resolution, stale folders. |
| `histposts review` | HTML page with every post next to its license evidence. |
| `histposts caption "File.jpg" --topic "…"` | Optional Claude caption draft (needs `pip install -e ".[captions]"` and `ANTHROPIC_API_KEY`). |

## `posts.yaml` reference

```yaml
posts:
- name: klondike-1898
  file: Miners climb Chilkoot.jpg        # Wikimedia Commons file name
  year: '1898'                           # shown top right
  title: Klondike Altın Hücumu           # large serif title
  place: Alaska                          # shown in the top label
  info: 1898'de Klondike Altın Hücumu sırasında ...   # 3-5 lines printed on the image
  story: |                               # longer Turkish text for caption.txt
    ...
  title_en: The Klondike Gold Rush       # optional English title/text for caption_en.txt
  story_en: |
    ...
  tags: ['#altınhücumu', '#klondike']
  author_qid: Q5385972                   # Wikidata id of the author; the death year is read from there
  # author_died: anonymous               # manual alternative, needs rights_source: <url>;
  # rights_source: https://...           #   "anonymous" is accepted only for works over 126 years old
  credit: ...                            # optional: author line when the Commons author is not the photographer
  crop: [0, 0, 1, 0.93]                  # optional fractions (left, top, right, bottom) to trim mounts/borders
  focus: [0.5, 0.4]                      # optional point kept in frame when the photo is cropped
  series: klondike                       # optional: posts sharing a series get a "01 / 05" counter
  alt_text: ...                          # optional accessibility text (a default is generated)
```

`facts.yaml` lists, per post, the claims that go beyond the photo's own record, the Wikipedia article that should
back them and the tokens (dates, numbers, names) that must appear in it.

## Output per post

```
paylasima-hazir/01-paris-1913/
├── instagram_4x5.jpg        # 1080×1350
├── tiktok_9x16.jpg          # 1080×1920, text inside the Reels/TikTok safe area
├── reels_tiktok.mp4         # with --video
├── before_after.jpg         # original vs enhanced
├── caption.txt              # Turkish caption: story, hashtags, credit, source, license, alt text
├── caption_en.txt           # English caption (from story_en)
└── license_evidence.json    # templates, author death year, sources, source resolution
```

## How rights are verified

`build` writes a post only when its rights are **verified**:

1. the source page carries a public-domain / CC0 template;
2. the author's life+70 term has ended: death year from Wikidata (`author_qid`), or a manual `author_died` with a
   `rights_source` URL, or an anonymous work at least 126 years old;
3. it is public domain in the US: CC0, or first dated before the 95-year cut-off (1931 in 2026).

Anything else is `us-only` or `unverified` and is skipped; an older output folder of such a post is deleted.
All 19 example posts are verified; see [docs/license-audit.md](docs/license-audit.md) for every source link.
This is a **risk filter, not legal advice**: templates are community claims, the "dated" year may be a creation
rather than a publication year, and Wikidata can be wrong. Details and limits:
[docs/licensing.md](docs/licensing.md), [docs/text-verification.md](docs/text-verification.md),
[docs/fact-check.md](docs/fact-check.md).

## Project layout

```
src/histposts/
  cli.py          commands            pipeline.py   posts.yaml loading and the per-post build
  sources/        one module per      licensing.py  safe/review/blocked classification
                  photo source        verify.py     evidence-based rights check (Commons + Wikidata)
  photocheck.py   non-photo and       factcheck.py  Wikipedia claim check
                  colour detection    compose.py    post layout and fonts
  enhance.py      restoration         video.py      slow-zoom MP4
  imageprep.py    border trimming     review.py     HTML review page
  captions.py     optional Claude     doctor.py     pre-publication checklist
posts.yaml        the 19 example posts        facts.yaml   claims to check
docs/             architecture, licensing, audit reports, demo GIF
tests/            114 tests (network mocked)
```

See [docs/architecture.md](docs/architecture.md) for the data flow.

## Limitations

* The Library of Congress site answers scripted clients with a Cloudflare challenge, so it is not a source; its
  photos are used through their Commons copies and the record quoted there. Europeana and NARA are skipped
  without an API key.
* Real-ESRGAN can invent plausible-looking detail; hence it is limited to low-resolution sources, blended with the
  gentle result and always accompanied by a before/after image. Captions say the image was digitally enhanced.
* Printed captions and mounts inside scans are not detected; use `crop:` in `posts.yaml`.
* Photo and colour detection are heuristic; the contact sheet is the real check. Toned prints (sepia) are accepted.
* Publishing through the Instagram/TikTok APIs is out of scope (Instagram needs a Business account and app review;
  TikTok only allows private posts until the client passes an audit).
* The Wikipedia fact check confirms that key tokens appear in an article; it does not judge wording.

## Development

```bash
pip install -e ".[dev]"
ruff check src tests && ruff format --check src tests
pytest
```

On macOS a `.pth` file inside a virtualenv can get the *hidden* flag, after which Python 3.13+ ignores it and
`import histposts` fails. Fix with `chflags -R nohidden .venv`, or run with `PYTHONPATH=src`.
See [CONTRIBUTING.md](CONTRIBUTING.md).

Licenses: code MIT. Bundled fonts Lato and Playfair Display are under the SIL Open Font License
(`src/histposts/assets/fonts/`). Real-ESRGAN is BSD-3-Clause and is downloaded on demand, not redistributed.
The example photographs are public domain; each has its evidence in `examples/*/license_evidence.json`.

---

## Türkçe özet

Telifsiz, siyah-beyaz tarihi fotoğrafları bulur, hak durumunu kanıtla denetler (Commons lisans şablonları,
Wikidata'dan yazarın ölüm yılı, ABD kuralı), orijinale sadık kalarak iyileştirir ve Türkçe başlık ile bilgi metniyle
Instagram (4:5) ve TikTok/Reels (9:16) postlarına dönüştürür. Her post için lisans kanıtı, önce/sonra görseli,
Türkçe ve İngilizce caption, alt metin ve isteğe bağlı kısa video üretilir. Metinlerdeki iddialar Wikipedia'ya karşı
ücretsiz olarak kontrol edilebilir (`histposts facts`). Tam Türkçe rehber: [README.tr.md](README.tr.md). Araç hiçbir şeyi kendisi paylaşmaz; çıktıyı inceleyip siz
paylaşırsınız. Bu bir risk filtresidir, hukuki tavsiye değildir. Kurulum ve komutlar yukarıda; ayrıntılar için
[docs/licensing.md](docs/licensing.md).
