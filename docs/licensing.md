# Licensing policy

The tool is a **risk filter, not legal advice**. Copyright terms differ by country, and a "public domain" tag on
a hosting site is a claim by an uploader, not a legal guarantee.

## Levels

| Level | Meaning | Rules (see `src/histposts/licensing.py`) |
|---|---|---|
| `safe` | Very low risk | CC0 / Public Domain Mark; works of US federal agencies (NASA, FSA/OWI); works dated before the US 95-year cut-off (1931 in 2026). |
| `review` | Tagged "public domain", legal basis unclear | Dated after the cut-off; no date; press-agency credit; "no notice"/"not renewed" arguments (US-only). Check the source page before publishing. |
| `blocked` | Not usable | Attribution, share-alike, non-commercial or unknown licenses. Never built. |

`histposts check posts.yaml` prints the level for every post; `histposts build --strict` builds only `safe` posts.
Every built post gets a `license_evidence.json` with the license name and URL, usage terms, credit line, author,
date, source page and the retrieval time.

## Known limits

* "Published before the cut-off" is a **US** rule. In countries with life+70 terms, a photo from 1925 can still be
  protected if its photographer died after 1955. The reasons text says so explicitly.
* Dates come from uploader metadata and can be wrong (a placeholder date such as `1920-01-02` is treated as a date).
* Personality/privacy rights and museum reproduction terms are outside the scope of copyright and are not checked.
* Sources that require API keys (Europeana, NARA) are skipped without a key. The Library of Congress site is not a
  supported source: its API answers scripted clients with a Cloudflare challenge, and this project does not try to
  bypass it. Many LoC photographs are mirrored on Wikimedia Commons and are found there.

## Verified rights (`histposts verify`, default for `build`)

`safe` is a US-law statement. Countries with life+70 terms, such as Turkey and EU states, protect a work until 70
years after the author's death, and US-government photographs by recent authors (e.g. Lange, Rothstein) are *not*
free there. `build` therefore only writes posts whose rights are **`verified`**:

1. the source page carries a public-domain / CC0 template (Commons templates are read via the API);
2. the author's life+70 term has ended: death year from Wikidata (`author_qid`), or `author_died` plus a
   `rights_source` URL, or an anonymous work (`author_died: anonymous`, `rights_source`) that is at least 126 years
   old (an unidentified author would have had to outlive the work by 55+ years);
3. it is public domain in the US: CC0, or first dated before the 95-year cut-off (1931 in 2026).

Everything else is `us-only` or `unverified` and is skipped (its old output folder is deleted). The evidence per
post is in `license_evidence.json` (`rights`) and in `docs/license-audit.md`.

Known limits: Commons templates are uploader/community claims; the "dated" year may be a creation rather than a
publication year; Wikidata may be wrong. The audit lists every source link so each claim can be re-checked. LoC item
pages are not reachable by script (Cloudflare), so LoC-derived posts rely on the record quoted on the Commons page.
