# Upload & Manage a Plugin

This guide explains the plugin lifecycle: uploading, validating, assigning, configuring, and updating plugins in
Cadence.

---

## What Is a Plugin?

A plugin is a ZIP archive that contains the logic and tool definitions for an AI agent. Plugins are created by
developers and uploaded by Org Admins (or System Admins). Once uploaded, a plugin can be assigned to one or more
orchestrator instances.

---

## Uploading a Plugin

### What the ZIP Must Contain

Before uploading, verify the plugin archive has a valid structure:

- A recognized **entry point** file (e.g., `plugin.py` or as specified in the plugin's metadata).
- A **metadata file** (e.g., `plugin.json` or `manifest.yml`) describing the plugin name, version, and required
  settings.
- Any supporting files (models, utilities, data files) the plugin needs.

If these are missing or incorrectly structured, the upload will be rejected with a validation error.

### Upload Steps

1. Go to **Plugins → Upload Plugin**.
2. Click **Choose File** and select your `.zip` file.
3. Click **Upload**.

Cadence will automatically validate the archive. You will see one of two outcomes:

| Outcome     | What it means                                                                  |
|-------------|--------------------------------------------------------------------------------|
| **Success** | Plugin appears in the list with version number and a green status              |
| **Error**   | A message explains what is wrong (see [Error Reference](../testing/errors.md)) |

---

## Assigning a Plugin to an Orchestrator

A plugin must be assigned to an orchestrator instance before it becomes a live agent.

1. Go to **Orchestrators → New Orchestrator** (or edit an existing one).
2. In the **Plugin** field, select the uploaded plugin from the dropdown.
3. Select an **LLM Config** to pair with the plugin.
4. Click **Create** (or **Save**).

The orchestrator now uses this plugin. It will be in **Cold** state until you load it.

---

## Configuring Per-Instance Plugin Settings

Each orchestrator instance can have its own plugin settings, independent of other instances using the same plugin.

1. Select the orchestrator from the Orchestrators list.
2. Click **Settings**.
3. Fill in the plugin-specific fields. Common settings include:
    - **System prompt**: Instructions given to the agent at the start of every conversation.
    - **Tool configurations**: API keys or endpoints the plugin's tools use.
    - **Behavior flags**: Options that alter how the agent responds.
4. Click **Save Settings**.

Settings take effect the next time the orchestrator is loaded (or after a hot-reload if it is already Hot).

---

## Updating a Plugin Version

When a new version of a plugin is available:

1. Go to **Plugins → Upload Plugin**.
2. Upload the new ZIP file. If the plugin name matches an existing plugin, Cadence will create a new version.
3. Go to **Orchestrators** and select the orchestrator(s) you want to update.
4. In the **Plugin** dropdown, select the new version.
5. Click **Save**.
6. If the orchestrator is currently **Hot**, click **Hot-Reload** to apply the new version without unloading the
   instance.

!!! warning "Settings may change between versions"
A new plugin version may introduce new settings or remove old ones. Review the plugin settings after updating and fill
in any new required fields before reloading.

---

## Removing a Plugin

Plugins can only be removed if no orchestrators are currently assigned to them.

1. Unassign or delete all orchestrators using the plugin.
2. Go to **Plugins**, find the plugin, and click **Delete**.

---

## Summary

| Task                    | Where                                            |
|-------------------------|--------------------------------------------------|
| Upload plugin           | Plugins → Upload Plugin                          |
| Assign to orchestrator  | Orchestrators → New/Edit → Plugin dropdown       |
| Configure settings      | Orchestrators → Select → Settings                |
| Update version          | Plugins → Upload (new ZIP) → update orchestrator |
| Hot-reload after update | Orchestrators → Select → Hot-Reload              |
