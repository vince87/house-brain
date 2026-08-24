# Installation lifecycle management

This document defines the safety contract for the installation-management
features delivered by this branch.

## Scope

House Brain manages its persistent state exclusively inside `/config`. The
installation lifecycle API provides:

- coherent downloadable backups with a versioned manifest and SHA-256 checksums;
- SQLite consistency checks before backup and before accepting a restore;
- staged restore inspection before any persistent file is replaced;
- an automatic recoverable pre-restore snapshot;
- first-run readiness checks for policy, database, Home Assistant and LLM;
- local migration state and update availability metadata;
- an authenticated administration page shared with the Home Assistant panel.

## Safety invariants

- Archive members must be regular files with normalized relative paths.
- Absolute paths, parent traversal, links, devices and duplicate members are
  rejected.
- Extraction occurs in a private temporary directory outside `/config`.
- A restore is never applied during upload or inspection.
- Applying a restore requires the server-issued inspection token and an explicit
  confirmation value.
- The current configuration is backed up before replacement.
- Database and policy validation happen before replacement and again after the
  staged files are installed.
- A failed replacement rolls back from the pre-restore snapshot.
- Historical backups and legacy Docker volumes are never deleted automatically.
- API keys, Home Assistant tokens and provider credentials are not written to
  manifests, audit data or diagnostic exports.
- No Docker socket access is required or supported.

## Archive format

The downloadable archive is a ZIP file containing:

```text
manifest.json
config/autonomy.yaml
config/house_brain.db
config/autonomy-backups/...
```

SQLite sidecars are not copied directly. The database entry is created with the
SQLite backup API after a passive WAL checkpoint. The manifest records the
archive format version, House Brain version, creation time, file size and
SHA-256 checksum for every payload file.

## Restore lifecycle

1. Upload and inspect the archive.
2. Validate paths, member types, limits, manifest and checksums.
3. Validate the staged policy and SQLite database.
4. Show the exact files that would be replaced.
5. Confirm using the short-lived server-issued restore token.
6. Create a pre-restore snapshot.
7. Replace managed files atomically.
8. Reopen and validate the restored database and policy.
9. Roll back automatically if validation fails.
10. Record a redacted administrative audit event.

The running process may keep open SQLite connections, so database replacement is
performed through SQLite's backup API rather than replacing an open database
inode.

## Update and migration model

Update checks are informational and never pull images, restart containers or
modify files. Schema/config migrations expose their current version and create a
backup before any future write migration. Container upgrade and rollback remain
operator-controlled and documented.
