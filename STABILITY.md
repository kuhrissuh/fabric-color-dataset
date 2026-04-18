# Stability Contract

This document describes what consumers of `fabric-color-dataset` can rely on.

## Within a major version

Schema is backward-compatible. New fields may be added; existing fields, their types, and their semantics will not change. New colors may be added; existing colors will not be removed or have their IDs changed.

## Across major versions

Breaking changes are allowed, announced at least 30 days in advance, and accompanied by a migration guide. The previous major version continues to receive data updates for 90 days after the new major ships.

## Color IDs are permanent

An ID refers to the same color for the lifetime of the project — across all versions. The `aliases` field and `status: superseded` mechanism handle the rare case where an ID needs to be corrected.

## What counts as what

| Change | Version bump |
|---|---|
| Correcting wrong data (hex, typo, broken URL) | Patch |
| Adding fields, adding colors, adding lines | Minor |
| Removing fields, renaming fields, changing field types or semantics | Major |
| Adding a new `hex_confidence` bucket (changes consumer code behavior) | Major |

## The one permanent commitment

Color IDs. Everything else can evolve through the versioning process.
