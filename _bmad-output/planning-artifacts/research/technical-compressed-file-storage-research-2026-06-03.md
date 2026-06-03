---
stepsCompleted:
  - technical-research
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
workflowType: research
lastStep: 1
research_type: technical
research_topic: compressed file storage reduction strategies
research_goals: Evaluate commercial and academic strategies for reducing storage capacity when large files are already compressed, encrypted, or opaque.
user_name: Shaqsnake
date: 2026-06-03
web_research_enabled: true
source_verification: true
---

# Technical Research: Compressed File Storage Reduction

## Executive Summary

For already-compressed files, conventional chunk deduplication usually has weak and unstable results because compression hides source-level redundancy. The practical storage strategy is not one technique, but a policy stack:

1. Prefer "deduplicate first, then compress/encrypt stored objects" for data BIG controls.
2. Avoid whole-stream compressed archives for versioned working data.
3. Use compression-friendly archive formats when archives are required: per-file/per-block compression, deterministic metadata, non-solid mode, or rsyncable compression.
4. For packages/archives, consider format-aware decomposition into member-level CAS objects.
5. For opaque compressed EDA databases, use lifecycle/PPA retention and cold-tier policy first; apply delta or format-aware methods only after benchmark evidence.

The important product conclusion for BIG: compressed/opaque artifacts should not be promised block-dedup savings by default. They need a separate file-class policy.

## Commercial and Open-Source Practice

| System / Practice | Relevant Lesson for BIG |
| --- | --- |
| Data Domain deduplication file system | Production backup systems rely on segment deduplication, locality-aware layout, and cache/index techniques to make dedupe practical at high throughput. This validates dedupe as a storage engine pattern, but not as a guarantee for high-entropy compressed inputs. |
| Veeam backup settings for dedupe appliances | When the target storage performs hardware compression/deduplication, upstream compression should be disabled or made "dedupe-friendly". This supports BIG's policy that compression must be coordinated, not blindly stacked. |
| BorgBackup | Borg splits source files into content-defined chunks and stores only new chunks; compression is an optional storage step after chunking. This is the right order for BIG-controlled data. |
| zbackup | zbackup explicitly recommends feeding uncompressed/unencrypted data because it performs dedupe, then compression/encryption internally. This closely matches the BIG store design. |
| NetApp ONTAP compression | Enterprise storage compresses bounded compression groups and supports inline/postprocess efficiency. This suggests BIG should compress stored objects/chunks independently, not whole user working trees as monolithic streams. |

## Academic Findings

| Research Direction | Finding | Fit for BIG |
| --- | --- | --- |
| Z-Dedup: deduplicating compressed packages | Conventional fingerprint dedupe fails across compressed/uncompressed or differently compressed packages. Z-Dedup uses invariant package metadata such as original file length and checksums to identify hidden redundancy, reporting large savings on some package datasets. | Useful Growth reference for archive/package-aware decomposition, especially ZIP/tar-like deliverables. Not a simple MVP feature. |
| IBM DCC 2011: mixing deduplication and compression | Compression and dedupe effectiveness depends heavily on data type, CPU cost, and ordering. | Supports file-class benchmarking and policy selection. |
| IBM Middleware 2008: demystifying dedupe | Deduplication is not a universal silver bullet; space savings, CPU, and reconstruction time vary materially by technique. | Supports not over-promising FastCDC for all EDA artifacts. |
| Stream-informed delta compression | Post-dedup delta compression can add extra reduction for similar but non-identical regions, with reported additional compression benefits in backup systems. | Possible Growth/R&D path for large similar binaries, but increases restore complexity and should be bounded by chain length and benchmarked. |

## Strategy Options

### 1. Dedupe Before Compression

For files BIG controls, store data as:

```text
source bytes -> file/chunk CAS -> per-object compression -> optional encryption -> pack/bundle
```

This is the safest long-term rule. It keeps chunk identity stable and still gets local compression savings. It also allows exact restore because object hashes are defined over original source bytes while stored bytes may be compressed internally.

### 2. Per-Object Compression With Skip Heuristics

For each CAS object or future CDC chunk:

- Try fast compression such as lz4 or zstd-fast.
- Store compressed only if the output is meaningfully smaller, for example >5-10%.
- Mark high-entropy inputs as `compression_skipped`.
- Record compression method, original size, compressed size, checksum, and ratio.

This reduces waste from trying to recompress `.gz`, `.zip`, `.zst`, encrypted files, and many EDA opaque DBs.

### 3. Archive Policy: Avoid Whole-Stream Compression

For user-generated archives, recommend:

- Prefer `tar`/directory input into BIG, then let BIG dedupe and compress internally.
- Avoid `tar.gz` / `tar.zst` for data that will be versioned often.
- If compression is mandatory, prefer per-file or per-block compression instead of solid whole-archive compression.
- For gzip workflows that must sync compressed files, use `gzip --rsyncable` when available.
- Use deterministic metadata: stable file order, normalized mtime, owner/group, permissions, and compression parameters.

This sacrifices a small amount of compression ratio to preserve dedup and delta locality.

### 4. Format-Aware Package Decomposition

For archive formats BIG can parse, store a logical package as:

```text
package manifest
  + normalized metadata
  + per-member content hash
  + per-member compressed/raw bytes
  + restore recipe
```

This allows entry-level dedupe even when the outer package changes. It is suitable for ZIP-like non-solid packages and BIG-created archives. For third-party packages requiring byte-exact restoration, BIG must either keep the original package bytes or prove that its recipe can reproduce the exact stream.

### 5. Transcoding / Canonical Recompression

If byte-exact restoration is not required, BIG can decompress an archive, store members in CAS, and regenerate a canonical archive on checkout or publish. This can save a lot of space, but it changes the byte representation and therefore should be opt-in.

Good candidate: generated delivery packages where semantic equivalence is acceptable.

Bad candidate: tool databases, signed artifacts, or any artifact where checksum identity matters.

### 6. Similarity / Delta Compression

For large binaries that are similar but not chunk-identical, delta compression can store a new version as a delta against a base version. This can help when compression did not completely randomize the stream or when the format has stable internal regions.

BIG should treat this as Growth/R&D:

- Limit delta chain length.
- Keep periodic full bases.
- Verify restore integrity continuously.
- Avoid applying it to files with low similarity scores.
- Benchmark read amplification before productizing.

### 7. Lifecycle, PPA Ranking, and Tiering

For truly high-entropy opaque compressed files, storage algorithms may have little to exploit. The correct reduction strategy becomes product policy:

- Keep only selected full DBs for Exploring runs.
- Retain Top-K or candidate versions by PPA score.
- Move old candidates to cold archive.
- Keep recipes/provenance for reproducibility.
- Allow explicit pinning for important artifacts.

This is not less elegant; it is the honest lower bound when the bytes are already near-random.

## Recommended BIG Design

### MVP

- Keep file-level CAS.
- Add per-CAS-object compression with skip heuristics.
- Classify file types into likely-compressible, already-compressed, encrypted/high-entropy, and opaque DB.
- Do not enable FastCDC or delta compression for compressed/opaque classes by default.
- Rely on lifecycle/PPA retention for storage reduction of large opaque artifacts.

### Growth

- Add `big archive` or publish-time packaging that creates BIG-native dedupe-friendly archives.
- Introduce format-aware parsers for selected formats after benchmarks.
- Enable FastCDC only for file classes with proven chunk reuse.
- Add optional delta compression for large similar binaries with bounded chains.

### Design Rule

BIG should preserve this invariant:

> User-visible checkout is byte-exact unless a command explicitly opts into semantic/canonical archive regeneration.

That keeps the tool predictable for EDA flows while still allowing aggressive storage reduction in controlled paths.

## Sources

- USENIX FAST 2008, Data Domain deduplication file system: https://www.usenix.org/conference/fast-08/avoiding-disk-bottleneck-data-domain-deduplication-file-system
- Veeam compression/deduplication guidance: https://helpcenter.veeam.com/docs/vbr/userguide/compression_deduplication_hv.html
- BorgBackup documentation: https://borgbackup.readthedocs.io/en/stable/index.html
- zbackup README in Debian Sources: https://sources.debian.org/src/zbackup/1.5-4/README.md
- NetApp ONTAP compression concept: https://docs.netapp.com/us-en/ontap/concepts/compression-concept.html
- GNU gzip `--rsyncable`: https://www.gnu.org/software/gzip/manual/gzip.html
- tarlz compression granularity: https://www.nongnu.org/lzip/manual/tarlz_manual.html
- Z-Dedup paper: https://par.nsf.gov/servlets/purl/10095182
- IBM Research, Mixing deduplication and compression on active data sets: https://research.ibm.com/publications/mixing-deduplication-and-compression-on-active-data-sets
- IBM Research, Demystifying data deduplication: https://research.ibm.com/publications/demystifying-data-deduplication
- USENIX HotStorage 2012, Delta compressed and deduplicated storage: https://www.usenix.org/conference/hotstorage12/workshop-program/presentation/shilane
