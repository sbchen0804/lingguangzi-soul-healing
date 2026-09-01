# `chapter.json` Schema

`chapter.json` is the human-reviewed source of truth for one chapter. The first generated version is a `draft`; only `confirm_manifest` may write `status: "confirmed"`.

## Required top-level fields

| Field | Meaning |
| --- | --- |
| `schema_version` | Manifest format version (currently `1`). |
| `revision` | Integer incremented for every successful confirmation and for invalidation of a confirmed source change. |
| `status` | Either `draft` or `confirmed`. |
| `inventory_digest` | Current `sha256:` aggregate source-inventory digest. |
| `chapter` | Chapter number. |
| `title` | Chapter title. |
| `subtitle` | Chapter subtitle. |
| `theme` | Theme metadata; use `keywords` and optional `visual_notes`. |
| `visual` | Visual DNA, described below. |
| `original` | Original-author cover and PDF sources. |
| `songs` | Ordered, extensible song array. |
| `refined.items` | Ordered, extensible refined-content array. |
| `sharing` | Optional sharing overrides (`description`, `image_alt`, ISO `published_at`, ISO `modified_at`). |
| `excluded_files` | Supported source paths deliberately not used on the page. |

Every supported source path in the inventory must be mapped exactly once by `original`, `visual.hero`, `visual.share`, a song, or a refined item, or listed exactly once in `excluded_files`. A path named by the manifest must exist in the inventory.

## Nested fields

- `original` has `cover` and `pdf`.
- Each song has `id`, `title`, `audio`, `lyrics_source`, and `order`. Song `id` and `order` values must each be unique; add as many songs as needed.
- `refined` has `title` and `items`. Each refined item has `type`, `role`, `title`, `file`, `order`, and optional `display`. Valid types are `image` (`.png`, `.jpg`, `.jpeg`), `document` (`.pdf`), `audio` (`.mp3`, `.m4a`), and `video` (`.mp4`); type and file extension must agree.
- `visual` must contain `style_family`, `concept`, `composition`, `palette`, `mood`, `distinctive_elements`, and `avoid` before confirmation. `hero` and `share` are optional at draft/confirmation time but, when present, are mapped local source files. A build requires both; `share` must be a 1200×630 image.
- `publication_authorization` records the author's permission as `{ "approved": true, "note": "..." }`; it is required by pre-publication QA.

## Example

```json
{
  "schema_version": 1,
  "revision": 2,
  "status": "confirmed",
  "inventory_digest": "sha256:example",
  "chapter": 520,
  "title": "讓風穿過心的門",
  "subtitle": "本章副標題",
  "theme": {"keywords": ["健康", "安穩"], "visual_notes": "門與風"},
  "visual": {
    "style_family": "watercolor",
    "concept": "風穿過打開的心門",
    "composition": "從室內望向自然",
    "palette": ["霧藍", "鼠尾草綠"],
    "mood": ["釋放", "安穩"],
    "distinctive_elements": ["打開的門", "窗簾"],
    "lighting": "午後柔光",
    "avoid": ["湖面日出"]
  },
  "original": {"cover": "原圖文/cover.png", "pdf": "原圖文/original.pdf"},
  "songs": [
    {"id": "song-01", "title": "第一首詩歌", "audio": "詩歌創作/song-01.mp3", "lyrics_source": "詩歌創作/song-01.txt", "order": 1},
    {"id": "song-02", "title": "第二首詩歌", "audio": "詩歌創作/song-02.m4a", "lyrics_source": "詩歌創作/song-02.docx", "order": 2}
  ],
  "refined": {
    "title": "找回生命的靈魂處方",
    "items": [
      {"type": "image", "role": "wisdom-card", "title": "圖卡", "file": "精煉篇/summary.png", "order": 1},
      {"type": "audio", "role": "podcast", "title": "Podcast", "file": "精煉篇/podcast.m4a", "order": 2, "display": "player"}
    ]
  },
  "sharing": {},
  "publication_authorization": {"approved": true, "note": "作者已同意公开分享"},
  "excluded_files": []
}
```
