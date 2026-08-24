# House Brain add-on (experimental)

This add-on packages the same House Brain server used by the standalone container.
It stores its persistent files in the Supervisor-managed add-on configuration
directory, mounted at `/config`.

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
