# Glossary

Plain-English definitions for terms used throughout the Cadence platform.

---

**Organization (Org)**
A self-contained tenant within the Cadence platform. Each organization has its own users, plugins, orchestrators, and
LLM credentials. Think of it like a separate workspace — one Cadence server can host many organizations simultaneously,
and they cannot see each other's data.

---

**Plugin**
A ZIP archive containing an AI agent's logic, tool definitions, and metadata. Plugins are uploaded by admins and define
what an agent can do. A plugin is like a software package — it must be uploaded, validated, and assigned to an
orchestrator instance before it becomes a live agent.

---

**Orchestrator**
A configured, deployable instance of a plugin. An orchestrator combines a plugin with a specific set of settings (such
as which LLM to use and how to configure the agent's tools). You can have multiple orchestrators using the same plugin
with different configurations.

---

**Instance**
Often used interchangeably with "orchestrator." Refers to a single running (or stored) deployment of a plugin
configuration. Each instance has its own state (Hot, Cold, or Warm) and its own settings.

---

**Hot / Cold / Warm**
The three lifecycle states of an orchestrator instance:

- **Hot** — The instance is loaded in memory and ready to accept chat messages immediately.
- **Cold** — The instance exists in storage but is not loaded. Sending a message to a Cold instance will return an error
  until it is loaded.
- **Warm** — The instance is in transition (being loaded or unloaded). This state is temporary.

---

**Conversation**
A single chat session between a user and an orchestrator. Each conversation has its own message history. Starting a new
conversation resets the context — the agent does not remember previous conversations unless the plugin is specifically
designed to retain memory.

---

**LLM Config**
A set of credentials and settings for connecting to a Large Language Model provider (e.g., OpenAI GPT-4, Anthropic
Claude). Each LLM Config stores the API key, model name, and any provider-specific parameters. Organizations supply
their own LLM Config (see BYOK).

---

**BYOK (Bring Your Own Key)**
The model where each organization provides its own LLM API credentials. Cadence does not include a built-in LLM
subscription — organizations pay their AI provider directly and configure the key in Cadence.

---

**System Admin**
A platform-level administrator with access to all organizations and global settings. System Admins can create
organizations, manage global LLM configs, view platform health, and monitor the orchestrator pool.

---

**Org Admin**
An administrator scoped to a single organization. Org Admins can manage users, upload plugins, create and manage
orchestrators, and configure org-level LLM credentials. They cannot see or affect other organizations.

---

**Tier**
A classification applied to organizations or users that may affect resource limits or feature access. Tiers are
configured by the System Admin and can be used to differentiate service levels (e.g., Free, Pro, Enterprise).

---

**RabbitMQ**
The message broker used internally by Cadence to route chat messages and orchestration tasks between components. Users
do not interact with RabbitMQ directly — it is a background infrastructure component. Its health is visible in the
System Admin panel.

---

**SSE (Server-Sent Events)**
The technology that enables real-time streaming of chat responses. When you type a message in the chat interface, the
agent's response is sent back word by word via SSE, so you see the text appear progressively rather than waiting for the
full response.
