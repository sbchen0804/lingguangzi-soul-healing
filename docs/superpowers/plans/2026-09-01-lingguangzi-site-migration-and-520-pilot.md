# Lingguangzi Site Migration and Chapter 520 Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the existing chapter 521 site into the reusable multi-chapter structure, preserve legacy links, run chapter 520 through the new manifest workflow, and prepare—but not publish—the complete responsive preview for user approval.

**Architecture:** Use the installed `lingguangzi-chapter-site` Skill and its canonical scripts to generate `/chapters/521/` and `/chapters/520/` from confirmed manifests. The repository root becomes a static chapter catalog with legacy-hash routing; `shared/` holds cross-chapter assets, visual registry, and analytics configuration. Production publication remains a separate final gate after the user reviews the generated preview and explicitly authorizes chapter publication.

**Tech Stack:** Core Skill from `skills/lingguangzi-chapter-site`; static HTML/CSS/JavaScript; Python build and QA scripts; GitHub Pages; GoatCounter; in-app Browser responsive verification.

**Spec:** `docs/superpowers/specs/2026-09-01-lingguangzi-chapter-skill-design.md`

## Global Constraints

- Complete the core Skill plan before starting this plan.
- Preserve Dr. Ke Wan-Sheng’s original covers and source wording byte-for-byte where applicable.
- Preserve the approved chapter 521 mobile typography and reading behavior.
- The root catalog may replace the old root presentation, but all old root hash links must resolve to the equivalent chapter 521 destination.
- `/#entry-521` must resolve to the top of `/chapters/521/`, not directly to the three circles.
- Chapter pages must cold-open at `scrollY === 0`; Go Top returns to the three-circle entry area without adding `#entry-N`.
- GoatCounter must not run on localhost or 127.0.0.1 and must never expose an API key.
- Every chapter gets absolute canonical/Open Graph URLs and a 1200×630 share image.
- No commit/push of generated chapter content occurs until the user says `確認發布第 N 章` in the publication turn.

---

## File Map

```text
site.config.json                         # Public base URL, author, analytics endpoint
index.html                               # Series catalog and legacy hash router
shared/
├─ styles.css                            # Catalog and shared tokens
├─ catalog.js                            # Catalog behavior and legacy redirects
└─ visual-registry.json                  # Chapter visual DNA history
chapters/
├─ 521/
│  ├─ index.html
│  └─ assets/
└─ 520/
   ├─ index.html
   └─ assets/
chapter-sources/
├─ 521.json                              # Repository copy of confirmed manifest
└─ 520.json                              # Repository copy after user confirmation
tests/site/
├─ __init__.py
├─ test_catalog.py
├─ test_chapter_521.py
├─ test_chapter_520.py
└─ test_meta_and_analytics.py
```

The original source folders remain outside the Git repository under `C:\Users\sbche\OneDrive\文件\Codex_2026\靈光子\靈魂療癒系列第 N 章`. Only approved web assets and repository manifest copies enter the site repository.

### Task 1: Create the Multi-Chapter Shell and Legacy Router

**Files:**
- Create: `site.config.json`
- Replace: `index.html`
- Create: `shared/styles.css`
- Create: `shared/catalog.js`
- Create: `shared/visual-registry.json`
- Create: `tests/site/__init__.py`
- Create: `tests/site/test_catalog.py`

**Interfaces:**
- Produces: site config keys `base_url`, `site_name`, `author`, `analytics`; root catalog cards linking to `/chapters/{chapter}/`; old-hash redirect mapping.

- [ ] **Step 1: Write the failing catalog tests**

```python
from pathlib import Path
import json
import unittest


ROOT = Path(__file__).parents[2]


class CatalogTests(unittest.TestCase):
    def test_site_config_has_absolute_base_url(self):
        config = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["base_url"], "https://sbchen0804.github.io/lingguangzi-soul-healing")

    def test_catalog_links_to_chapter_521(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="chapters/521/"', html)

    def test_legacy_hash_router_is_loaded(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "shared/catalog.js").read_text(encoding="utf-8")
        self.assertIn('src="shared/catalog.js"', html)
        self.assertIn('"#song-521": "chapters/521/#song-521"', js)
        self.assertIn('"#entry-521": "chapters/521/"', js)
```

- [ ] **Step 2: Run the test and verify it fails**

```powershell
& 'C:\Users\sbche\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.site.test_catalog -v
```

Expected: FAIL because `site.config.json` and the catalog do not exist.

- [ ] **Step 3: Implement the site config**

```json
{
  "base_url": "https://sbchen0804.github.io/lingguangzi-soul-healing",
  "site_name": "靈魂療癒系列",
  "author": "柯萬盛醫師（筆名靈光子）",
  "analytics": {
    "provider": "goatcounter",
    "enabled": false,
    "endpoint": ""
  }
}
```

Analytics remains disabled until the user supplies the one-time GoatCounter site code. An empty disabled endpoint is a valid pre-production state but a publication-blocking QA result.

- [ ] **Step 4: Implement the catalog and exact legacy mapping**

`shared/catalog.js` must map:

```javascript
const legacy = {
  "#entry-521": "chapters/521/",
  "#original-521": "chapters/521/#original-521",
  "#original-reader": "chapters/521/#original-reader",
  "#song-521": "chapters/521/#song-521",
  "#refined-521": "chapters/521/#refined-521"
};
const destination = legacy[location.hash];
if (destination) location.replace(destination);
```

The catalog contains the series purpose, author attribution, and a chapter 521 card. It must not auto-redirect the clean root URL.

- [ ] **Step 5: Run tests and commit**

```powershell
git add site.config.json index.html shared tests/site/test_catalog.py
git commit -m "feat: add multi-chapter catalog shell"
```

### Task 2: Inventory and Confirm Chapter 521 Migration Data

**Files:**
- Create in source folder: `靈魂療癒系列第 521 章/chapter.json`
- Create in source folder: `靈魂療癒系列第 521 章/chapter.lock.json`
- Create: `chapter-sources/521.json`
- Create: `tests/site/test_chapter_521.py`

**Interfaces:**
- Consumes: chapter 521 source directory and core scan/manifest scripts.
- Produces: confirmed manifest revision for all chapter 521 original, song, lyrics, refined, and excluded files.

- [ ] **Step 1: Run the new command behavior on chapter 521**

Invoke the Skill as if the user said `521 章重新檢查`. Generate a draft and consolidated inventory report. Set `原圖文/靈魂療癒系列第521章_追著死亡地活著_縮短版旗艦版01.pdf` as the approved original PDF; list `原圖文/靈魂療癒系列第521章_追著死亡地活著_縮短版旗艦版.pdf` as superseded. Keep `精煉篇_找回生命的靈魂處方/521_追著死亡地活著.pdf` as the refined full text and present the additional PDF copy in the refined folder as an explicit exclusion candidate for user confirmation.

- [ ] **Step 2: Present the migration manifest to the user**

The review must list every mapped and excluded file, page/document role, song/lyrics pairing, refined order, and the existing chapter 521 visual DNA. Stop until the user confirms this manifest revision.

- [ ] **Step 3: Confirm and lock only after the user replies**

Run `confirm_manifest`; verify `status == "confirmed"`, `inventory_digest` matches the lock, and every supported file is referenced or excluded.

- [ ] **Step 4: Copy the confirmed manifest into the repository**

Copy only `chapter.json` to `chapter-sources/521.json`. Do not copy the lock because it contains source-workspace state rather than deployable content.

- [ ] **Step 5: Write the failing migration test**

```python
class Chapter521Tests(unittest.TestCase):
    def test_manifest_is_confirmed_and_complete(self):
        manifest = json.loads((ROOT / "chapter-sources/521.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "confirmed")
        self.assertEqual(manifest["chapter"], 521)
        self.assertGreaterEqual(len(manifest["songs"]), 1)
        self.assertEqual([item["order"] for item in manifest["refined"]["items"]], sorted(item["order"] for item in manifest["refined"]["items"]))
```

- [ ] **Step 6: Run tests and commit the repository manifest only**

```powershell
git add chapter-sources/521.json tests/site/test_chapter_521.py
git commit -m "data: record confirmed chapter 521 sources"
```

### Task 3: Generate and Verify `/chapters/521/`

**Files:**
- Create: `chapters/521/index.html`
- Create: `chapters/521/styles.css`
- Create: `chapters/521/chapter.js`
- Create: `chapters/521/assets/**`
- Modify: `tests/site/test_chapter_521.py`

**Interfaces:**
- Consumes: confirmed chapter 521 manifest/lock, current approved assets, and the shared template.
- Produces: generated chapter 521 page and build manifest.

- [ ] **Step 1: Write failing generated-site assertions**

```python
class GeneratedChapter521Tests(unittest.TestCase):
    def test_generated_521_preserves_required_content(self):
        html = (ROOT / "chapters/521/index.html").read_text(encoding="utf-8")
        css = (ROOT / "chapters/521/styles.css").read_text(encoding="utf-8")
        js = (ROOT / "chapters/521/chapter.js").read_text(encoding="utf-8")
        self.assertIn("追著死亡地活著", html)
        self.assertIn("我要追著死亡地活著", html)
        self.assertEqual(html.count("refined-521-page-"), 15)
        self.assertIn("font-size:1.3rem", css.replace(" ", ""))
        self.assertNotIn('href="#entry-521"', html)
        self.assertIn("history.replaceState", js)
```

- [ ] **Step 2: Run and verify failure**

- [ ] **Step 3: Generate chapter 521 with the core builder**

Build from the confirmed source manifest and lock. Reuse existing approved hero, lyrics, PDF pages, and audio where their hashes match; regenerate only derived files that fail the build manifest check.

- [ ] **Step 4: Run static and media checks**

Verify original PDF page count 5, refined page count 15, all `<audio>` sources exist, original cover bytes match the source cover, and no refined figure overlaps the following audio block in normal flow.

- [ ] **Step 5: Run responsive browser checks**

Start a local static server and use the in-app Browser at all widths in the spec. Capture evidence that clean load starts at `scrollY === 0`, the hero is visible, the three circles fit the first mobile screen, Go Top reaches the choices without changing the hash, and section navigation lands correctly after previous PDF viewing.

- [ ] **Step 6: Run tests and commit generated migration**

```powershell
git add chapters/521 tests/site/test_chapter_521.py
git commit -m "feat: migrate chapter 521 to shared structure"
```

### Task 4: Add Per-Chapter Meta, Share Cards, and GoatCounter Integration

**Files:**
- Modify: `skills/lingguangzi-chapter-site/assets/chapter-template/chapter.html`
- Modify: `skills/lingguangzi-chapter-site/scripts/build_chapter.py`
- Modify: `chapters/521/index.html` through regeneration
- Create: `tests/site/test_meta_and_analytics.py`
- Modify after user setup: `site.config.json`

**Interfaces:**
- Produces: absolute canonical/Open Graph/Twitter metadata, Article JSON-LD, production-only analytics loader, and footer visit counter container.

- [ ] **Step 1: Write failing metadata tests**

```python
class MetaAnalyticsTests(unittest.TestCase):
    def test_521_has_absolute_social_metadata(self):
        html = (ROOT / "chapters/521/index.html").read_text(encoding="utf-8")
        base = "https://sbchen0804.github.io/lingguangzi-soul-healing/chapters/521/"
        self.assertIn(f'<link rel="canonical" href="{base}">', html)
        self.assertIn('property="og:image"', html)
        self.assertIn('content="1200"', html)
        self.assertIn('content="630"', html)
        self.assertIn('name="twitter:card" content="summary_large_image"', html)
        self.assertIn('"@type": "Article"', html)

    def test_analytics_is_guarded_to_production(self):
        js = (ROOT / "chapters/521/chapter.js").read_text(encoding="utf-8")
        self.assertIn('location.hostname === "sbchen0804.github.io"', js)
```

- [ ] **Step 2: Run and verify failure**

- [ ] **Step 3: Implement metadata generation**

Use `share-521.jpg` as an absolute HTTPS `og:image`. Include `og:image:alt`, `og:locale=zh_TW`, `og:type=article`, site name, precise title/description, and canonical URL. JSON-LD author is `柯萬盛醫師（筆名靈光子）`.

- [ ] **Step 4: Prepare the GoatCounter loader without enabling it**

The template reads the public endpoint from generated config. On production only, append `https://gc.zgo.at/count.js` with `data-goatcounter` set to the endpoint. On local hosts, set `window.goatcounter = { no_onload: true }`. Failure hides the numeric value and leaves the label `瀏覽統計暫時無法取得`; it never blocks reading.

- [ ] **Step 5: Request the one-time GoatCounter site code**

Ask the user to create or provide the public GoatCounter endpoint. Do not request or store the account password or API key. After receipt, set `enabled: true` and the exact `https://CODE.goatcounter.com/count` endpoint in `site.config.json`.

- [ ] **Step 6: Regenerate, test, and commit**

```powershell
git add site.config.json skills/lingguangzi-chapter-site chapters/521 tests/site/test_meta_and_analytics.py
git commit -m "feat: add chapter sharing metadata and visit counts"
```

### Task 5: Run `520 章建立` and Obtain Manifest Approval

**Files:**
- Create in source folder: `靈魂療癒系列第 520 章/chapter.json`
- Create in source folder: `靈魂療癒系列第 520 章/chapter.lock.json`
- Create only after confirmation: `chapter-sources/520.json`
- Create: `tests/site/test_chapter_520.py`

**Interfaces:**
- Consumes: chapter 520 source directory.
- Produces: a user-confirmed chapter 520 manifest with original, one current song, lyrics, wisdom card, refined PDF, Podcast, video, excluded duplicate/reference files, and visual DNA.

- [ ] **Step 1: Invoke the installed Skill with `520 章建立`**

The scan must discover the known cover, original PDF, song MP3, lyrics PDF, wisdom image, refined presentation PDF, Podcast M4A, feature MP4, and additional refined/source PDF candidate.

- [ ] **Step 2: Inspect source documents for semantic classification**

Use file names, PDF page/text inspection, media metadata, and folder context to decide the primary refined PDF and any excluded or supporting file. Do not silently discard the second refined PDF candidate.

- [ ] **Step 3: Produce the complete draft and visual DNA**

The visual concept must center on wind passing through an open inner doorway, with a composition, palette, objects, lighting, and avoid-list that differ from chapter 521 in at least three dimensions. The avoid list includes lake sunrise and distant mountain silhouette.

- [ ] **Step 4: Present one consolidated manifest review to the user**

Show chapter title/subtitle, all mapped files, excluded files, display order, lyric source, Podcast/video titles, and visual DNA. Stop; do not build chapter 520 until the user confirms or supplies corrections.

- [ ] **Step 5: Confirm, lock, and copy the repository manifest**

After explicit confirmation, run the manifest validator and copy the confirmed manifest to `chapter-sources/520.json`.

- [ ] **Step 6: Add and run the manifest test**

```python
class Chapter520Tests(unittest.TestCase):
    def test_confirmed_manifest_maps_video_and_podcast(self):
        manifest = json.loads((ROOT / "chapter-sources/520.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "confirmed")
        types = {item["type"] for item in manifest["refined"]["items"]}
        self.assertIn("audio", types)
        self.assertIn("video", types)
        self.assertGreaterEqual(len(manifest["visual"]["distinctive_elements"]), 2)
```

- [ ] **Step 7: Commit the confirmed manifest**

```powershell
git add chapter-sources/520.json tests/site/test_chapter_520.py
git commit -m "data: record confirmed chapter 520 sources"
```

### Task 6: Generate the Chapter 520 Visuals and Static Page

**Files:**
- Create: `chapters/520/index.html`
- Create: `chapters/520/styles.css`
- Create: `chapters/520/chapter.js`
- Create: `chapters/520/assets/**`
- Modify: `shared/visual-registry.json`
- Modify: `index.html`
- Modify: `tests/site/test_chapter_520.py`

**Interfaces:**
- Consumes: confirmed chapter 520 manifest and matching source lock.
- Produces: distinct hero/share art, converted content, complete chapter page, catalog card, and visual registry entry.

- [ ] **Step 1: Generate the text-free watercolor hero**

Use the image-generation skill with chapter 520 visual DNA. The hero may use an open doorway, moving translucent curtain, wind-carried leaves, and warm light leading toward nature; it must not reuse chapter 521’s lake, distant mountains, or sunrise arrangement.

- [ ] **Step 2: Generate the 1200×630 share card**

Derive it from the same chapter-specific artwork and add only the series label, chapter number, and concise chapter title. Keep all website hero text in HTML, not baked into `hero-520.jpg`.

- [ ] **Step 3: Compare with the recent-six registry**

Run deterministic visual metadata validation and create a side-by-side contact sheet of available recent heroes. If fewer than three dimensions differ from chapter 521 or the result reads as the same safe landscape, regenerate before building.

- [ ] **Step 4: Convert sources and build the page**

Render original and refined PDFs to ordered pages, extract lyrics from the searchable PDF or route to OCR review, copy audio/video, and generate the static page. Video must occupy its own normal-flow block after the configured preceding item.

- [ ] **Step 5: Update catalog and tests**

```python
class GeneratedChapter520Tests(unittest.TestCase):
    def test_generated_520_has_all_media(self):
        html = (ROOT / "chapters/520/index.html").read_text(encoding="utf-8")
        self.assertIn("讓風穿過心的門", html)
        self.assertIn("<video", html)
        self.assertIn("<audio", html)
        self.assertIn("閱讀歌詞", html)
        self.assertNotIn('href="#entry-520"', html)
```

- [ ] **Step 6: Run tests and commit the local preview build**

```powershell
git add chapters/520 shared/visual-registry.json index.html tests/site/test_chapter_520.py
git commit -m "feat: build chapter 520 preview"
```

This commit remains local until publication authorization.

### Task 7: Full Responsive and Interaction QA

**Files:**
- Create: `qa/chapter-520-report.md`
- Create: `qa/chapter-521-regression-report.md`
- Create: `qa/screenshots/520/**`
- Create: `qa/screenshots/521/**`
- Modify: `test-site.cjs`
- Modify generated/template files only when a test proves a defect.

**Interfaces:**
- Produces: evidence-backed QA reports with no blocking issues.

- [ ] **Step 1: Run all automated tests**

```powershell
& 'C:\Users\sbche\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -p 'test_*.py' -v
& 'C:\Users\sbche\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' test-site.cjs
```

Expected: all tests PASS. Modify `test-site.cjs` to read `chapters/521/index.html`, `chapters/521/styles.css`, and `chapters/521/chapter.js`; keep its existing chapter 521 content and typography assertions as an additional regression layer.

- [ ] **Step 2: Start a local static server**

Serve the repository root on an available localhost port and record the exact preview URL.

- [ ] **Step 3: Verify all responsive widths**

At 320, 375, 390, 430, mobile landscape, 768, 1024, 1280, 1440, and 1920 px, verify no horizontal overflow, correct hero crop, stable circles, 521-derived font minima, non-overlapping PDF/media blocks, and unobstructed Go Top/mini-player controls.

- [ ] **Step 4: Verify navigation state transitions**

For both chapters: cold-open canonical URL at top; click original/song/refined and assert selected green state plus accurate target; scroll deeply through PDF pages; click Go Top and assert entry alignment with no `#entry-N`; reload clean URL and assert top-of-page hero is restored.

- [ ] **Step 5: Verify media behavior**

Start song audio, navigate to refined, confirm fixed controls remain; start Podcast/video and confirm previous media pauses; leave the page and confirm all media stops. Confirm controls remain accessible on mobile.

- [ ] **Step 6: Verify Meta, share assets, and counter behavior**

Confirm absolute canonical/OG URLs, accessible share image paths, correct 1200×630 dimensions, precise descriptions, production-only analytics guard, and graceful counter fallback locally.

- [ ] **Step 7: Produce reports and fix only evidenced defects**

Each report lists `manifest`, `source_lock`, `content`, `pdf_pages`, `media`, `responsive`, `navigation`, `visual_distinctiveness`, `meta`, and `counter` as PASS, WARNING, or BLOCKED with evidence. Repeat the failing check after each focused fix.

- [ ] **Step 8: Commit QA evidence**

```powershell
git add qa skills/lingguangzi-chapter-site chapters shared index.html tests
git commit -m "test: verify chapter 520 and 521 experiences"
```

### Task 8: User Preview and Publication Gate

**Files:**
- No file changes before user review.
- Production files change only if the user requests corrections.

**Interfaces:**
- Consumes: local preview and clean QA reports.
- Produces: either a correction cycle or explicit authorization for publication.

- [ ] **Step 1: Open the local preview for the user**

Open the root catalog, chapter 520, and migrated chapter 521 in the in-app Browser. Provide the preview URLs and a concise summary of mapped content, visual differences, and QA results.

- [ ] **Step 2: Stop for user review**

Do not push. Ask the user to review both desktop and mobile behavior. Corrections return to the smallest relevant task and repeat its tests.

- [ ] **Step 3: Require exact publication authorization**

Proceed only after the user says `確認發布第 520 章` for chapter 520 and separately authorizes any chapter 521 migration publication if it changes the existing public structure.

- [ ] **Step 4: Run final verification immediately before push**

Confirm clean test results, intended Git diff, enabled GoatCounter endpoint, no secrets, and correct public base URLs.

- [ ] **Step 5: Commit any final approved corrections and push**

Push only the approved commits to `origin/main`; do not create a GitHub Release package unless separately requested.

- [ ] **Step 6: Verify GitHub Pages after deployment**

Wait for deployment, then verify HTTP 200 for root, chapters 520/521, share images, original/refined pages, audio, and video. Re-run initial scroll, legacy hash routing, Meta, and Counter checks against production.

- [ ] **Step 7: Report the release evidence**

Return the public chapter URLs, final commit, deployment status, and pass/fail summary. State any Counter cache delay without representing it as a failure.

## Migration Plan Completion Gate

This plan is complete only when chapter 520 and migrated chapter 521 pass all automated and responsive checks, the user has reviewed the local preview, and each public change has its own explicit publication authorization. Without that authorization, the correct terminal state is a local committed preview that is ahead of `origin/main`.
