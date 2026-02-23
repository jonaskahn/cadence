# Chat with an Agent

This guide explains how to send messages to an AI agent using the Cadence chat interface.

---

## Prerequisites

- You have a Cadence account and have been added to an organization.
- At least one orchestrator in your organization is in **Hot** state (loaded and ready).

---

## Step-by-Step

### Step 1: Log In

1. Navigate to the Cadence login page.
2. Enter your email and password.
3. Click **Log In**.

You will be taken to the main chat interface.

---

### Step 2: Select Your Organization

If you belong to more than one organization, an organization selector appears at the top of the screen.

1. Click the organization dropdown.
2. Select the organization whose agents you want to use.

The chat interface will reload to show orchestrators available in that organization.

---

### Step 3: Choose an Orchestrator

1. In the chat panel, click the **Orchestrator** dropdown (or the agent selector).
2. Select the orchestrator you want to chat with.

!!! tip "Only Hot instances appear"
Only orchestrators in **Hot** state are available for selection. If the orchestrator you need is not listed, contact
your Org Admin to load it.

---

### Step 4: Type and Send Your Message

1. Click the message input box at the bottom of the chat panel.
2. Type your question or request.
3. Press **Enter** or click the **Send** button.

---

### Step 5: Read the Streamed Response

The agent's response will appear word by word as it is generated — you do not need to wait for the full answer.

**What you may see:**

- **Progress events** (shown above the response text): Intermediate steps the agent is taking, such as:
    - "Searching knowledge base..."
    - "Calling tool: web_search"
    - "Generating response..."

  These give you visibility into what the agent is doing before it produces its final answer.

- **Response text**: The agent's answer, streamed in real time.

---

### Step 6: Continue the Conversation

The chat remembers context within a conversation. You can ask follow-up questions and the agent will refer to earlier
messages.

To **start a new conversation** (clearing the context):

1. Click **New Conversation** (or the refresh/new icon in the chat panel).
2. A blank chat window opens. The agent will not remember anything from the previous conversation.

---

## Tips for Better Interactions

| Tip                        | Detail                                                                             |
|----------------------------|------------------------------------------------------------------------------------|
| Be specific                | The more context you give, the better the agent can respond                        |
| One topic per conversation | Starting fresh conversations for different topics helps the agent stay focused     |
| Check progress events      | If the agent seems slow, progress events show it is still working                  |
| Report unexpected errors   | If you see an error message, note the orchestrator name and contact your Org Admin |

---

## Common Questions

**Why is the response slow?**
The agent may be using a tool (e.g., searching a database) before generating its final response. Watch the progress
events for activity.

**Why can't I see any orchestrators in the dropdown?**
No orchestrators are currently loaded (Hot) in your organization. Contact your Org Admin.

**The response was cut off — what happened?**
This can occur if your LLM provider's token limit was reached. Try rephrasing your question to be more concise, or start
a new conversation.
