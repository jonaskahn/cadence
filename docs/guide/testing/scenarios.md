# Test Scenarios

Structured test cases for validating Cadence functionality. Each scenario uses **Given / When / Then** format. Run these
scenarios after deployment or after any significant change.

---

## Authentication

### TC-AUTH-01: Successful Login

| Field     | Value                                                                                      |
|-----------|--------------------------------------------------------------------------------------------|
| **Given** | A valid user account exists with email `user@example.com` and a known password             |
| **When**  | The user enters the correct email and password on the login page and clicks Log In         |
| **Then**  | The user is redirected to the chat interface; their name appears in the top navigation bar |

---

### TC-AUTH-02: Login with Wrong Password

| Field     | Value                                                                                            |
|-----------|--------------------------------------------------------------------------------------------------|
| **Given** | A valid user account exists                                                                      |
| **When**  | The user enters the correct email but an incorrect password                                      |
| **Then**  | An error message is shown ("Invalid credentials" or similar); the user remains on the login page |

---

### TC-AUTH-03: Session Token Expiry

| Field     | Value                                                                             |
|-----------|-----------------------------------------------------------------------------------|
| **Given** | A user is logged in and their session token has expired (or has been invalidated) |
| **When**  | The user attempts any authenticated action (e.g., sends a chat message)           |
| **Then**  | The user is redirected to the login page; no data loss occurs                     |

---

### TC-AUTH-04: Organization Switching

| Field     | Value                                                                                |
|-----------|--------------------------------------------------------------------------------------|
| **Given** | A user has membership in two or more organizations                                   |
| **When**  | The user selects a different organization from the org switcher                      |
| **Then**  | The chat interface reloads showing orchestrators from the selected organization only |

---

## Chat

### TC-CHAT-01: Send Message to Hot Orchestrator

| Field     | Value                                                                                                 |
|-----------|-------------------------------------------------------------------------------------------------------|
| **Given** | An orchestrator is in **Hot** state and selected in the chat dropdown                                 |
| **When**  | The user types a message and clicks Send                                                              |
| **Then**  | The response streams back token by token; progress events appear above the response during processing |

---

### TC-CHAT-02: Send Message to Cold Orchestrator

| Field     | Value                                                                                            |
|-----------|--------------------------------------------------------------------------------------------------|
| **Given** | An orchestrator is in **Cold** state                                                             |
| **When**  | The user attempts to select it and send a message (if UI allows selection)                       |
| **Then**  | An error message is shown indicating the instance is not loaded; no partial response is returned |

---

### TC-CHAT-03: Start New Conversation

| Field     | Value                                                                                                          |
|-----------|----------------------------------------------------------------------------------------------------------------|
| **Given** | A user has an active conversation with several messages exchanged                                              |
| **When**  | The user clicks **New Conversation**                                                                           |
| **Then**  | The chat window clears; the next message is treated as the start of a fresh conversation with no prior context |

---

## Orchestrators

### TC-ORCH-01: Create Orchestrator Instance

| Field     | Value                                                                        |
|-----------|------------------------------------------------------------------------------|
| **Given** | A plugin and LLM config are available in the org                             |
| **When**  | The Org Admin creates a new orchestrator with a name, plugin, and LLM config |
| **Then**  | The orchestrator appears in the list with **Cold** status                    |

---

### TC-ORCH-02: Load Orchestrator (Cold → Hot)

| Field     | Value                                                                                                           |
|-----------|-----------------------------------------------------------------------------------------------------------------|
| **Given** | An orchestrator is in **Cold** state                                                                            |
| **When**  | The Org Admin clicks **Load**                                                                                   |
| **Then**  | The status transitions through **Warm** and settles on **Hot**; the orchestrator becomes selectable in the chat |

---

### TC-ORCH-03: Unload Orchestrator (Hot → Cold)

| Field     | Value                                                                                |
|-----------|--------------------------------------------------------------------------------------|
| **Given** | An orchestrator is in **Hot** state                                                  |
| **When**  | The Org Admin clicks **Unload**                                                      |
| **Then**  | The status changes to **Cold**; the orchestrator is no longer selectable in the chat |

---

### TC-ORCH-04: Hot-Reload Configuration

| Field     | Value                                                                                                                |
|-----------|----------------------------------------------------------------------------------------------------------------------|
| **Given** | An orchestrator is **Hot** and its plugin settings have been updated                                                 |
| **When**  | The Org Admin clicks **Hot-Reload**                                                                                  |
| **Then**  | The orchestrator reloads with the new settings without going Cold; existing chat sessions may be interrupted briefly |

---

### TC-ORCH-05: Delete Loaded Orchestrator

| Field     | Value                                                                                                                                                                                                      |
|-----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Given** | An orchestrator is currently in **Hot** state                                                                                                                                                              |
| **When**  | The Org Admin attempts to delete it                                                                                                                                                                        |
| **Then**  | Either: (a) the system prevents deletion with an error message ("Unload the instance first"), or (b) the system automatically unloads and then deletes it — confirm expected behavior with your deployment |

---

## Plugins

### TC-PLUG-01: Upload Valid Plugin ZIP

| Field     | Value                                                                              |
|-----------|------------------------------------------------------------------------------------|
| **Given** | A correctly structured plugin ZIP is available                                     |
| **When**  | The Org Admin uploads the ZIP via Plugins → Upload Plugin                          |
| **Then**  | The plugin appears in the plugin list with its name, version, and a success status |

---

### TC-PLUG-02: Upload Invalid Plugin ZIP

| Field     | Value                                                                                            |
|-----------|--------------------------------------------------------------------------------------------------|
| **Given** | A ZIP file with missing entry point or invalid metadata                                          |
| **When**  | The Org Admin attempts to upload it                                                              |
| **Then**  | An error message is shown describing the validation failure; the plugin is NOT added to the list |

---

### TC-PLUG-03: Assign Plugin to Orchestrator

| Field     | Value                                                                                                        |
|-----------|--------------------------------------------------------------------------------------------------------------|
| **Given** | A plugin has been uploaded and an orchestrator instance exists                                               |
| **When**  | The Org Admin edits the orchestrator and selects the plugin                                                  |
| **Then**  | The orchestrator is updated with the new plugin; settings fields update to reflect the plugin's requirements |

---

## Administration

### TC-ADMIN-01: Create Organization

| Field     | Value                                                                    |
|-----------|--------------------------------------------------------------------------|
| **Given** | Logged in as System Admin                                                |
| **When**  | Creating a new organization via Admin → Organizations → New Organization |
| **Then**  | The organization appears in the org list; an Org Admin can be assigned   |

---

### TC-ADMIN-02: Add User to Organization

| Field     | Value                                                                         |
|-----------|-------------------------------------------------------------------------------|
| **Given** | A user account and an organization exist                                      |
| **When**  | The System Admin (or Org Admin) adds the user to the org with the Member role |
| **Then**  | The user can log in and see the organization in their org switcher            |

---

### TC-ADMIN-03: Change Membership Role

| Field     | Value                                                                                                       |
|-----------|-------------------------------------------------------------------------------------------------------------|
| **Given** | A user is a Member of an organization                                                                       |
| **When**  | The Org Admin changes their role to Org Admin                                                               |
| **Then**  | The user gains access to admin features (plugin upload, orchestrator management) on next page load or login |

---

### TC-ADMIN-04: Edit Global Setting

| Field     | Value                                                                                    |
|-----------|------------------------------------------------------------------------------------------|
| **Given** | Logged in as System Admin                                                                |
| **When**  | Editing a global setting in Admin → Settings and saving                                  |
| **Then**  | The setting is persisted and reflected immediately (or after a defined propagation time) |
