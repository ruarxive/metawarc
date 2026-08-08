## 1. Format Registry
- [x] 1.1 Define declarative OOXML, image, video, audio, and font MIME/extension sets
- [x] 1.2 Add bounded group-specific signature probes and conflict handling
- [x] 1.3 Extend OOXML package validation and aliases

## 2. Extractors
- [x] 2.1 Extend Hachoir image routing and add safe SVG metadata extraction
- [x] 2.2 Add Hachoir-backed video metadata extraction
- [x] 2.3 Add Hachoir-backed audio metadata extraction
- [x] 2.4 Add FontTools and EOT font metadata extraction
- [x] 2.5 Normalize common media and font fields without losing raw metadata

## 3. Persistence and Interfaces
- [x] 3.1 Register `videos`, `audio`, and `fonts` content sidecars
- [x] 3.2 Include new groups in stored metadata analysis and export
- [x] 3.3 Update CLI type choices, help, and documentation
- [x] 3.4 Update package dependencies and lock data

## 4. Verification
- [x] 4.1 Test PPSX and additional OOXML aliases and package validation
- [x] 4.2 Test GIF, SVG, and representative additional image formats
- [x] 4.3 Test MP3 and representative audio formats
- [x] 4.4 Test MP4, AVI, and representative video formats
- [x] 4.5 Test TTF/OTF, WOFF/WOFF2, collections, and EOT metadata
- [x] 4.6 Test MIME/extension conflicts, signatures, limits, and failure isolation
- [x] 4.7 Run focused tests, full pytest, Ruff, and MyPy
