# Vendored third-party files

The viewer used to load these from public CDNs at run time (unpkg, cdnjs, Google Fonts). They are served from this
folder instead, so visiting gitgalaxy.io (or running the site air-gapped) contacts no third party, and the
content-security-policy can forbid every external host.

These are other people's files, kept byte-for-byte as published, with their licences next to them. Do not edit them.
The maintainer approved vendoring exactly these cases on 2026-11-21 (see `docs/research/third-party-material-policy.md`).

| What | Version | Licence | Where it came from | Files here |
|---|---|---|---|---|
| three.js | 0.183.0 | MIT (`three/LICENSE`) | npm package `three@0.183.0` | `three/build/three.core.js`, `three.module.js`, `three.webgpu.js`, `three.tsl.js`, `three/examples/jsm/tsl/display/BloomNode.js` |
| tween.js | 18.6.4 | MIT (`tween/LICENSE`) | npm package `@tweenjs/tween.js@18.6.4`, `dist/tween.umd.js` | `tween/tween.umd.js` |
| Space Grotesk, Space Mono | Google Fonts v22 / v17 | SIL OFL 1.1 (`fonts/OFL-*.txt`) | Google Fonts (the same woff2 files and unicode-range rules the site used before) | `fonts/*.woff2`, `fonts/fonts.css` |

Only the files the page can reach are included (the import graph of `index.html` was traced: three.js's other build
files and examples are not needed). The three.js and tween.js files are byte-identical to what unpkg and cdnjs served
on 2026-11-21 (compared by SHA-256 before the switch). `SHA256SUMS` lists every file here; a test checks it.

## Updating

1. `npm pack three@<version>` into an empty directory, extract it, copy the same five files, and compare any change in
   behaviour in a browser with WebGPU (headless Chrome cannot exercise the WebGPU path).
2. Update the `importmap` in `site/index.html` only if file names change.
3. Regenerate checksums: `cd site/vendor && find . -type f ! -name SHA256SUMS | sort | xargs sha256sum > SHA256SUMS`.
4. Update the versions in the table above and in the policy document.
