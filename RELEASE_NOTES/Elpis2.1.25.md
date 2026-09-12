# Elpis2.1.25

## Version: v2.1.25

Elpis2.1.25 is a corrective release candidate following the immutable but unpublished Elpis2.1.24 tag.

Elpis2.1.24 successfully integrated Grid81 Canonical Publisher R1, StreamingRegexIngress/RegexHACF V2, and ECS M1A, but hosted release CI subsequently exposed two release-authority defects that were not caught by the local seal:

1. the Grid81 successor component manifests for the Candidate Constructor and Atomic Canonical Publisher still described their pre-integration tracked source inventories; and
2. the root native CI gate still required 96 registered tests even though Regex V2 raised the root registry to 105.

Elpis2.1.24 therefore remains immutable evidence but is not promoted to a GitHub Release, publication-registry entry, or PyPI release.

## Corrective changes

Elpis2.1.25:

- regenerates the two stale Grid81 successor component source inventories, inventory digests, and manifest self-hashes from the exact tracked component bytes;
- refreshes the Grid81 writer-chain successor registry to bind those corrected component manifests;
- refreshes the successor dependency graph's registry binding and graph self-hash;
- updates only the root-native CI count from 96 to 105 while preserving the standalone semantic-spine sanitizer count at 96;
- records Elpis2.1.24 in a machine-readable failed-release ledger bound to its immutable tag object, peeled commit, release manifest, and failure disposition;
- makes the tag-derived publication registry explicitly exclude failed sealed tags from publication;
- preserves `PUBLISHED_RELEASES.json` unchanged before a successfully qualified successor tag exists.

## Preserved implementation

The substantive Elpis2.1.24 implementation remains unchanged:

- Grid81 Canonical Publisher R1 mechanics;
- StreamingRegexIngress/RegexHACF V2 mechanics;
- ECS M1A code and its single consolidated `ECS/README.md`;
- frozen ECS Structural R0 authority;
- closed Branch35–40 scientific evidence.

This corrective release does not broaden runtime admission, semantic authority, cross-process authority, scientific claims, or ECS scope.

## Release cadence correction

Elpis2.1.25 is intentionally pushed to `main` **without creating a tag first**.

The exact corrective commit must pass hosted CI on `main` before the immutable `Elpis2.1.25` tag may be created. This prevents a second failed immutable tag from being minted before the hosted release gates have exercised the candidate.
