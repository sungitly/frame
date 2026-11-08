# AfterFrame reference

Reviewed https://github.com/YIWANG3/AfterFrame on 2026-11-08 (MIT; reference commit c005c6f203bb915d8d862feac7a1f4606e1fc49a).

Useful ideas from the documented product:
- Local-first catalog: original files stay on disk, thumbnails/previews are independent of source files.
- Perceptual hashes and Apple Vision featureprints support visual similarity grouping.
- Pick/reject/star decisions and manual metadata belong in a persistent catalog, with manual values overriding AI output.
- Large libraries need bounded rendering; AfterFrame uses a virtualized grid.
- Its MCP bridge offers catalog search, thumbnail access, selections and export, potentially useful for future agent-assisted ongoing curation.

Applied here: a shared local analysis cache, original-file preservation, separate automatic/editorial/manual decision layers, local-only editing, bounded 60-item pages, and review of excluded/duplicate images. JSON/JSONL is sufficient for this 5,193-photo pilot; migrating to SQLite is sensible when indexing multiple years. No AfterFrame source code was copied.

Not adopted yet: installing its desktop app, its MCP bridge, face identity clustering, or Vision featureprint clustering. Our deduplication currently uses SHA-256 and dual perceptual hashes. Our on-device aesthetic and face-quality scorer uses Apple Vision directly; this is not a claim that AfterFrame performs final aesthetic selection for us.

AfterFrame's optional AI annotations use a user-configured provider (BYOK), so they should not be confused with completely local analysis. This implementation sends no photos to that service. Do not infer that every low model score is a failed photograph.
