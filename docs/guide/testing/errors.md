# Error Reference

This page lists common errors users and testers may encounter in Cadence, along with plain-English explanations and
recommended actions.

---

## HTTP Status Errors

### 401 Unauthorized

**What it means:** Your session has expired, or you are not logged in.

**When it appears:**

- After a period of inactivity (your token has expired).
- If you try to access a page directly without logging in.

**What to do:** Log out and log back in. If you were in the middle of a task, you may need to redo it after
re-authentication.

---

### 403 Forbidden

**What it means:** You are logged in, but your role does not permit this action.

**When it appears:**

- A Member tries to upload a plugin (requires Org Admin).
- An Org Admin tries to access the System Admin panel.
- An Org Admin tries to manage a different organization.

**What to do:** Contact your administrator to request the appropriate role, or confirm you are in the correct
organization.

---

### 404 Not Found (Orchestrator)

**What it means:** The orchestrator you are trying to reach does not exist, has been deleted, or belongs to a different
organization.

**When it appears:**

- A direct URL to an orchestrator that has been removed.
- Switching organizations while an orchestrator from the previous org is still selected.

**What to do:** Go back to the Orchestrators list and select a valid instance. If the orchestrator should exist, contact
your Org Admin.

---

### 503 Service Unavailable (Chat)

**What it means:** The orchestrator you are trying to chat with is in **Cold** state (not loaded) and cannot accept
messages.

**When it appears:**

- You send a message to an orchestrator that was loaded but has since been unloaded.
- The platform restarted and orchestrators were not automatically reloaded.

**What to do:** Ask your Org Admin to load (Hot) the orchestrator. While waiting, you will not be able to use that
agent.

---

## Plugin Upload Errors

### Invalid Plugin Structure

**What it means:** The ZIP file you uploaded is missing required files or has an incorrect directory layout.

**Common causes:**

- The entry point file (`plugin.py` or equivalent) is missing or misspelled.
- The metadata file is absent, incorrectly formatted, or uses the wrong file name.
- The ZIP contains only a subdirectory rather than files at the root level.

**What to do:** Unzip the archive locally and verify it contains the expected files. Ask the plugin developer to confirm
the correct structure. Re-zip and try again.

---

### Missing Entry Point

**What it means:** The platform could not find the main file that initializes the plugin.

**What to do:** Confirm the entry point file name matches what is declared in the metadata file. Re-upload after
correcting.

---

### Plugin Version Conflict

**What it means:** A plugin with the same name and version already exists.

**What to do:** Either increment the version number in the plugin metadata before re-uploading, or delete the existing
version first (if it is not assigned to any orchestrators).

---

## LLM API Errors

### Invalid API Key

**What it means:** The LLM API key configured for this orchestrator has been rejected by the LLM provider.

**When it appears:** The first message sent to a newly configured orchestrator fails with an LLM error.

**What to do:** Go to **Settings → LLM Configuration**, edit the relevant config, and verify the API key is correct and
has not been revoked.

---

### Quota Exceeded

**What it means:** Your organization's LLM API account has run out of credits or hit a rate limit.

**When it appears:** Responses suddenly stop working after previously working fine; error message may reference "rate
limit" or "quota".

**What to do:** Log in to your LLM provider's dashboard and check your usage and billing. Top up credits or request a
rate limit increase. No changes are needed in Cadence itself.

---

### Model Not Found

**What it means:** The model name entered in the LLM Config does not match any model available on your LLM provider
account.

**What to do:** Go to **Settings → LLM Configuration** and correct the model name. Use the exact model identifier as
listed by your provider (e.g., `gpt-4o`, not `gpt4o` or `GPT-4`).

---

## General Errors

### "Something went wrong" / Unexpected Error

**What it means:** An unhandled server error occurred. This is not expected during normal operation.

**What to do:**

1. Note what you were doing when the error appeared.
2. Refresh the page and try again.
3. If the error persists, contact your System Admin with the following information:
    - The page or feature you were using.
    - The orchestrator name (if applicable).
    - The approximate time of the error.

---

### Connection Lost / Streaming Interrupted

**What it means:** The streaming connection for a chat response was interrupted before the response completed.

**When it appears:** The response text stops mid-sentence and the loading indicator disappears.

**What to do:** This is usually a temporary network issue. Refresh the page and resend your message. If it recurs
consistently, check network stability or contact your System Admin.
