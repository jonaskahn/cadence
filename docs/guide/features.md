# Feature Overview

Cadence is a plugin-based AI agent platform that lets organizations deploy, manage, and interact with AI assistants —
without writing application code.

---

## Multi-Tenant Organization Management

Cadence is built around the concept of **organizations** (tenants). Each organization is an isolated workspace with its
own users, plugins, orchestrators, and LLM credentials. A single Cadence deployment can serve many organizations
simultaneously without any data leakage between them.

| What you can do                 | Who can do it |
|---------------------------------|---------------|
| Create and manage organizations | System Admin  |
| Add users to your organization  | Org Admin     |
| Configure org-specific settings | Org Admin     |

---

## Bring Your Own LLM Keys (BYOK)

Cadence does not bundle an LLM API key. Each organization supplies its own credentials for the AI model it wants to
use (e.g., OpenAI, Anthropic, or any compatible provider). This means:

- Your API costs stay with your organization.
- You choose which model powers your agents.
- Different orchestrators within the same org can use different LLM configs.

---

## Plugin-Based Agents

Agents in Cadence are powered by **plugins** — ZIP archives that contain the agent's logic and tool definitions. Plugins
are uploaded through the UI or API, validated by the platform, and then assigned to orchestrator instances.

Key points:

- No deployment pipeline required — upload a ZIP, configure, and go.
- A plugin can define multiple **tools** (capabilities the agent can use, e.g., search, database lookup).
- Plugin settings can be customized per orchestrator instance.
- Plugins can be versioned and updated without downtime.

---

## Real-Time Chat with Streaming Responses

Users interact with agents through a chat interface that streams responses in real time — text appears word by word as
the agent generates it, rather than waiting for the full response.

The chat interface also shows **progress events**: intermediate steps the agent takes before producing its final
answer (e.g., "searching knowledge base", "calling tool X").

---

## Orchestrator Lifecycle Management

An **orchestrator** is a running instance of a plugin configuration. Think of it as a deployed agent with a specific set
of settings. Orchestrators have a lifecycle:

| State    | Meaning                                                |
|----------|--------------------------------------------------------|
| **Hot**  | Loaded in memory, ready to accept messages immediately |
| **Cold** | Stored but not loaded — must be loaded before use      |
| **Warm** | Being loaded or transitioning between states           |

Org admins can load (Hot), unload (Cold), or hot-reload orchestrators without restarting the system.

---

## System Admin Panel

A global administrator can:

- View the health of the entire platform (API, message broker, database).
- Monitor the orchestrator pool (how many instances are loaded, available capacity).
- Manage all organizations and users across tenants.
- Set global LLM configurations and system-wide defaults.

---

## Summary

| Feature                | Benefit                                                 |
|------------------------|---------------------------------------------------------|
| Multi-tenant isolation | Each org's data and agents are fully separated          |
| BYOK                   | Control your AI costs and model choice                  |
| Plugin system          | Extend agent capabilities without platform code changes |
| Streaming chat         | Responsive, real-time user experience                   |
| Orchestrator lifecycle | Fine-grained control over which agents are active       |
| System admin panel     | Platform-wide visibility and control                    |
