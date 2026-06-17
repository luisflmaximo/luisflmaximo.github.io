# Task Checklist

- [x] Modify `secret/media-studio.html` (header nav, remove chips and badges, add visual options in pdf panel, add new image watermark visual panel)
- [x] Modify `assets/css/media-studio.css` (selector card stacking context, transition delay on dropdown menus)
- [x] Modify `assets/js/media-studio.js` (rename tool, add pdf-to-image/image-to-pdf configurations and processors, implement rotation/opacity sliders handlers and drawing support, add replicator on all pages, implement visual image watermark editor and processor)
- [x] Run validation and loading test scripts to ensure zero errors
- [x] Add Back FAB to return to normal tools page (`#backFab`)
- [x] Redesign file/folder upload box so clicking it opens the dialog and the buttons switch the active mode
- [x] Fix dropdown menu layering bug via CSS `z-index` on hover and horizontal scrolling on mobile
- [x] Add global paste (Ctrl+V) handler to import files from clipboard
- [x] Clean up HTML linter errors (move toolbar inline styles to CSS)
- [x] Add `-webkit-backdrop-filter` prefix to CSS classes for Safari support
- [x] Implement CSS hover bridge (`.tool-type-item::after`) to solve hover-out diagonal cursor menu switching bugs
- [x] Remove legacy scrollbar styling compatibility warnings
- [x] Make the download of video/images/audio native via direct Cobalt API requests, fallback to Cobalt redirect page on failure
- [x] Add June 17, 2026 Expanded Media Tool Suite (10 new tools):
  - [x] Add document and media compressors (`pdf-compress`, `image-compress`, `video-compress`)
  - [x] Add exporters (`pdf-to-pptx` using `pptxgenjs` and `pdf-to-word` using `docx.js`)
  - [x] Add vectorizer (`image-to-svg` using `ImageTracer.js`)
  - [x] Add video merger (`video-merge` using `FFmpeg.wasm` copy concat)
  - [x] Add auto-subtitles burner (`video-subtitle` using `FFmpeg.wasm` drawtext with UTF-8 Portuguese accents support)
  - [x] Add link shortener and QR generator (`link-shorten-qr` using `qrcode.js`, is.gd API, and logo overlays)
  - [x] Add image quality enhancer (`image-enhance` using Laplacian kernel digital sharpening, contrast, and brightness canvas filters)
  - [x] Run automated loading validation tests to confirm zero console errors on compiling all new tools and dynamic dynamic-CDN scripts loaders.

