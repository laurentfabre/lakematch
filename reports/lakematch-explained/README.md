# LakeMatch explained

- `LakeMatch-Explained.pdf`: 11-page report for nontechnical staff.
- `LakeMatch-Explained.md`: editable source with image captions and source links.
- `assets/`: diagrams, two measured charts, two cropped screenshots, and licensed fonts.
- `figure-sources.json`: evidence paths, checksums, chart values, and screenshot crop provenance.
- `make_assets.py` / `report.css`: figure generator and PDF styling.

The report describes the tested campaign snapshot at **910a418**, not a new
acceptance run. Later static-scan fixes are documented separately in
`bench/STATIC_SCAN.md`; their local checks do not revise the frozen benchmarks.

Generate figures with `python3 reports/lakematch-explained/make_assets.py`.
The script requires Matplotlib and Pillow. It reads the preserved benchmark
tables and screenshots, never runs an experiment, and uses the packaged DM Sans
font resources under `assets/`.

Export with the installed markdown-to-pdf skill's `resources/markdown_to_pdf.py`,
using `--input LakeMatch-Explained.md --output LakeMatch-Explained.pdf
--css report.css` from this directory. Rendering is offline. The converter uses
Markdown and WeasyPrint. The distributed assets carry their font license.
