# Accessible drawings — tagged PDF (PDF/UA) experiments

A personal sandbox for one question: **can a parametric drawing pipeline
emit accessible, tagged PDFs automatically, instead of someone remediating
every published sheet by hand in Acrobat?**

Engineering drawings are close to the worst case for document
accessibility. Every mainstream CAD PDF exporter (Rhino's `FilePdf`,
Bentley Print Organizer, AutoCAD plot drivers) writes raw vectors and
text runs in draw order with no logical structure — no `/StructTreeRoot`,
no marked content, no alt text. Screen readers get nothing, and
WCAG / Section 508 / PDF/UA (ISO 14289) compliance is normally bolted on
afterward by a human dragging tag boxes around in Acrobat Pro, sheet by
sheet, again after every revision. Meanwhile the civilpy SCD catalog
(`civilpy.structural.odot`, see `SCD_BUILD_LOG.md`) already *knows* what
each drawing depicts — the semantic model exists before the drawing does.
This document tracks the experiment of wiring the two together.

Not a product, not a mandate, not anyone's official workflow — one
person's experiment on public standard drawings.

## The three-tier map

Retro-tagging an *existing* CAD PDF at full semantic granularity means
parsing anonymous content streams, spatially segmenting thousands of path
operators, and rewriting them with marked-content wrappers — that's a
commercial-remediation-tool-sized project (Tier 3) and explicitly **out
of scope**. The tractable tiers:

- **Tier 1 — retrofit, whole-sheet-as-Figure.** A drawing sheet genuinely
  *is* one figure. Wrap each page's entire content stream in a single
  marked-content sequence, attach one `Figure` structure element with
  rich alt text (generated from the parametric model that drew the
  sheet), add the document plumbing PDF/UA wants (metadata, language,
  title, tab order). Cheap, batchable, honest about what it is.
- **Tier 2 — regenerate instead of retrofit.** Emit the sheet as
  HTML/SVG from the model and render with an engine that writes tags
  natively (WeasyPrint's `pdf_variant='pdf/ua-1'` — free; PrinceXML —
  not). Real reading order, notes as live text, tables as `Table` tags,
  details as `Figure`s with per-detail alt text. Requires a sheet
  composition layer that doesn't exist yet.
- **Tier 3 — full retro-tagging of exporter output.** Don't. Buy
  CommonLook/axesPDF if this is ever truly needed.

## TODO

### Tier 1 — `civilpy.general.pdf_ua` (built; validation pending)

- [x] Research: what minimal PDF/UA-1 conformance requires for a
      vector-drawing sheet (marked content + structure tree + XMP
      `pdfuaid:part`, `/MarkInfo`, `/Lang`, `/ViewerPreferences
      /DisplayDocTitle`, `/Tabs`, embedded fonts, `Figure` alt + BBox).
- [x] `SheetManifest` dataclass + JSON round-trip — title, language,
      per-page alt text. The JSON schema is the contract for anything
      upstream (Rhino user text, SCD generators) that wants to feed the
      tagger.
- [x] `tag_drawing_pdf(src, dst, manifest)` — pikepdf retrofit:
      one `Figure` per page via prepend/append content streams (never
      touches the exporter's stream bytes), structure tree + parent
      tree, XMP with `pdfuaid:part=1`, doc-info/title sync.
- [x] Refuse to double-tag: raise if the source already has a
      `/StructTreeRoot` rather than silently stacking structure.
- [x] Font-embedding audit in the returned report (PDF/UA requires all
      fonts embedded; the tagger can't fix that, but it must not be
      silent about it). Type0/CID descent included; Type3 skipped.
- [x] Tests on synthetic vector PDFs (built with pikepdf, no fixtures
      to license): structure tree shape, MCID wiring, parent tree,
      XMP assertions, alt-text broadcast, double-tag refusal,
      non-embedded-font warning. (`tests/general/test_pdf_ua.py`;
      note the `pdf` extra isn't in the CI install list, so these
      skip in CI like the other pikepdf/fitz-gated suites.)
- [x] `pikepdf` added to the `pdf` extra.
- [x] CLI: `civilpy pdf tag <in.pdf> --alt "..." --title "..."` (+
      `--manifest`/`--dest` variants), registry-driven like the other
      groups.
- [ ] Validate real output in PAC 2024 (Windows-only, manual) and
      veraPDF (java — not on this box; a `verapdf --flavour ua1`
      test is already wired and auto-skips until it's installed).
      **Structural assertions are not a conformance verdict — do this
      before trusting the output anywhere.**
- [ ] Try it on a real Rhino layout export end-to-end; check what
      Rhino does about font embedding and `ToUnicode` CMaps for sheet
      text.

### Tier 1.5 — feed the tagger from models, not by hand

- [ ] Alt-text builders on the SCD catalog: a `describe()` /
      `alt_text()` convention that turns a catalog entry's parameters
      into one competent paragraph ("42 in single-slope concrete
      bridge railing, Type B1, per SCD SBR-1-20 rev. 2024-07 …").
      Docstrings already cite SCD + revision date; reuse that.
- [ ] Rhino manifest exporter: read `PDF_Title` / `PDF_AltText` user
      text off layout objects (rhino3dm for `.3dm` files, script-side
      for live documents) → `SheetManifest` JSON sitting next to the
      exported PDF.
- [ ] Batch runner: directory of PDFs + manifests in, tagged +
      veraPDF-checked PDFs out, one summary table.

### Tier 2 — structured regeneration (not started)

- [ ] Spike: one simple sheet (a drip strip or headwall) as HTML —
      title block, general notes as real text, the drawing as inline
      SVG with `role="img"`/alt — through WeasyPrint `pdf/ua-1`;
      validate in PAC/veraPDF and eyeball fidelity against the
      exporter's PDF.
- [ ] SVG fidelity study: Rhino 8 layout→SVG export vs drawing the SVG
      directly from model geometry (lineweights, hatches, fonts,
      exact scale). Per-element identity is the whole point — the
      exporter's SVG is as anonymous as its PDF.
- [ ] Sheet composition layer (the big one): views, dimension strings,
      annotation placement, title block template. Decide build/skip
      based on how the spike feels. WeasyPrint's UA output is labeled
      experimental — keep the validator in the loop, and keep Prince
      as the fallback if it can't pass.
- [ ] Tables from source data (the models have the tables the sheets
      tabulate — regenerating beats scraping, always).

### Parking lot / open questions

- Adobe's PDF Accessibility Auto-Tag API on drawing sheets: almost
  certainly garbage on linework, possibly fine for notes-only pages.
  Cheap to benchmark someday.
- Multi-sheet publications: `Document` → per-sheet grouping, bookmarks,
  and whether reading order across sheets matters to any real AT user.
  Find an actual screen-reader user to sanity-check the alt-text style
  before generating hundreds of these.
- What granularity of tagging drawing-type publications actually
  satisfies reviewers in practice varies; Tier 1 is a floor, not a
  ceiling. The manifest schema is deliberately one-element-per-entry so
  Tier 2 granularity is an upgrade, not a rewrite.
