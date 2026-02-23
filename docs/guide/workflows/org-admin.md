# Org Admin Setup

This guide walks an Organization Administrator through setting up their organization after the System Admin has created
it. Complete these steps before inviting end users to chat.

---

## Prerequisites

- Your organization has been created by a System Admin.
- You have been assigned the **Org Admin** role.
- You have an LLM API key (if using your own, rather than the system default).
- You have a plugin ZIP file ready to upload.

---

## Step-by-Step Setup

### Step 1: Add Your LLM Configuration (BYOK)

Cadence lets each organization supply its own LLM credentials.

1. Go to **Settings → LLM Configuration → Add Config**.
2. Fill in the details:
    - **Provider**: Choose your LLM provider (e.g., OpenAI, Anthropic).
    - **API Key**: Paste your API key.
    - **Model**: Enter the model identifier (e.g., `gpt-4o`, `claude-3-5-sonnet-20241022`).
    - **Name**: Give this config a recognizable name (e.g., "OpenAI GPT-4o Production").
3. Click **Save**.

Your org can have multiple LLM configs — useful for using different models for different agents.

---

### Step 2: Upload an Org Plugin

1. Go to **Plugins → Upload Plugin**.
2. Click **Choose File** and select your plugin ZIP.
3. Click **Upload**.

Cadence validates the plugin automatically. A successful upload shows the plugin in your plugins list with a green
status. If validation fails, you will see a specific error message — see [Error Reference](../testing/errors.md) for
details.

---

### Step 3: Create an Orchestrator Instance

An orchestrator is a deployed agent that combines a plugin with a specific configuration.

1. Go to **Orchestrators → New Orchestrator**.
2. Fill in the details:
    - **Name**: A human-readable name (e.g., "Support Bot v1").
    - **Plugin**: Select the plugin you uploaded.
    - **LLM Config**: Select the LLM configuration to use.
3. Click **Create**.

The orchestrator is created in **Cold** state (stored but not loaded).

---

### Step 4: Configure Plugin Settings

Some plugins expose configurable parameters (e.g., a system prompt, a knowledge base URL, or behavior flags).

1. Select your orchestrator from the list.
2. Click **Settings**.
3. Review and fill in any plugin-specific settings.
4. Click **Save Settings**.

Settings differ per plugin — refer to the plugin's documentation for details.

---

### Step 5: Load the Orchestrator (Make It Hot)

Before users can chat, the orchestrator must be in **Hot** state.

1. Select your orchestrator.
2. Click **Load** (or the play icon).
3. Wait for the status to change from **Cold** to **Hot**. This may take a few seconds.

Once the status shows **Hot**, the orchestrator is ready to receive messages.

---

### Step 6: Test via Chat

1. Go to **Chat**.
2. Select your organization (if you belong to multiple).
3. From the orchestrator dropdown, select the instance you just loaded.
4. Type a test message and press **Send**.
5. Verify that you receive a streamed response.

If the response is incorrect or missing, check:

- The plugin settings are configured correctly.
- The LLM config API key is valid and has quota remaining.
- The orchestrator shows **Hot** status.

---

## Checklist

- [ ] LLM configuration added
- [ ] Plugin uploaded and validated
- [ ] Orchestrator instance created
- [ ] Plugin settings configured
- [ ] Orchestrator loaded (Hot)
- [ ] Test chat message sent and response received

---

## Next Steps

Your agents are live. Share the Cadence URL with your team and point end users to the [Chat with an Agent](chat.md)
guide.
