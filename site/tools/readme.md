### Visualizer Tools (`site/tools/`)

This directory holds the browser-side helper modules the WebGPU visualizer loads alongside its
rendering core (`site/js/`), plus two maintenance files. The rendering pipeline itself is described
in [`site/js/readme.md`](../js/readme.md).

* **`poster.js` (The VRAM-Safe Print Engine):** Renders print-size posters in tiles so a canvas larger than the GPU's `MAX_TEXTURE_SIZE` can still be produced, then stitches the tiles into one image.
* **`perf_monitor.js` (The Hysteresis Sentinel):** Tracks a rolling FPS window and JavaScript heap use and shifts the rendering tier (TITAN, STANDARD, POTATO) with hysteresis so the tier does not flicker under load.
* **`ally.js` (The Semantic Shadow DOM):** Builds a hidden, semantic `<ul>` tree that mirrors the 3D galaxy, with ARIA descriptions, so a screen-reader user can tab through files and steer the camera.
* **`search.js` (The Indexer):** Flattens the hierarchical galaxy data into a searchable array for jumping to a file or function.
* **`manifest.py`:** Regenerates the museum's `manifest.json` (the gallery list `site/js/main.js` fetches from `data/manifest.json`) from the `*_galaxy.json` files in the museum directory, linking each one's `_galaxy_audit.json` and `_galaxy_llm.md` when present. Its `MUSEUM_DIR` is a hard-coded server path.
* **`style_guide.html`:** The visualizer's master style guide page.

The tests for the Python side of the output layer (the GPU recorder, the code forges) live in
[`tests/tools_recorders/`](../../tests/tools_recorders/readme.md), not here.
