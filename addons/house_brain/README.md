# House Brain add-on (experimental)

This add-on packages the same House Brain server used by the standalone container.
It stores its persistent files in the Supervisor-managed add-on configuration
directory. Supervisor exposes that directory on the host below
`/addon_configs/<repository>_house_brain` and mounts it explicitly at `/config`
inside the add-on. Runtime options remain separately managed in
`/data/options.json`.

The fixed persistent paths inside the add-on are:

- `/config/house_brain.db`;
- `/config/autonomy.yaml`;
- `/config/autonomy-backups`;
- `/config/context-views.yaml`;
- `/config/system-backups`.

These paths are intentionally not configurable from the add-on options page.

## Safety boundary

- Home Assistant access uses the short-lived Supervisor token.
- No Docker socket, host network, privileged mode, or broad Home Assistant
  configuration mount is requested.
- The add-on never imports or deletes a standalone installation automatically.
- Entity visibility and control remain governed by House Brain Autonomy.
- The native Home Assistant integration remains the recommended user interface.

## First start

1. Add this repository to the Home Assistant add-on store.
2. Install the experimental House Brain add-on.
3. Set a strong `api_key`, the LLM provider settings, and leave autonomous
   execution disabled for the first validation.
4. Start the add-on and open its web UI.
5. Add the House Brain integration using the add-on host name and the same API key.

Do not run the standalone and add-on installations against the same persistent
directory. Use the documented backup/inspect/restore workflow for an intentional
migration and keep the original installation stopped but intact until validation
is complete.

## Home Assistant Core and Container

Home Assistant Core and Home Assistant Container do not provide the Supervisor
add-on store. Use the standalone House Brain container and install the native
House Brain custom integration instead. The integration can connect to the
standalone service without sharing its `/config` directory.
