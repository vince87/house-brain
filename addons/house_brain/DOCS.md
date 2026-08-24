# House Brain add-on

This experimental add-on runs the same House Brain service as the standalone
container. It requires Home Assistant OS or Supervised. Home Assistant Core and
Home Assistant Container users must use the standalone container plus the native
custom integration.

## Persistent storage

Supervisor owns the host directory
`/addon_configs/<repository>_house_brain` and mounts it at `/config` inside
this add-on. House Brain always uses:

- `/config/house_brain.db`;
- `/config/autonomy.yaml`;
- `/config/autonomy-backups`;
- `/config/context-views.yaml`;
- `/config/system-backups`.

Supervisor keeps the configuration-page options separately in
`/data/options.json`. Persistent paths are fixed and cannot be overridden from
the options page.

## Configuration

Set a strong API key, select the language and LLM provider, and configure the
provider URL and model. Keep autonomous execution disabled during first-run
validation. OpenAI-compatible servers may use the optional base URL, key and
model fields.

Home Assistant access is supplied by Supervisor through its token and
`http://supervisor/core`; do not enter a Home Assistant token manually.

Do not connect this add-on and a standalone House Brain container to the same
persistent directory. Use House Brain backup, inspection and explicit restore
for an intentional migration.
