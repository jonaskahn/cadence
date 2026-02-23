# System Admin Onboarding

This guide walks a System Administrator through the initial setup of a new Cadence deployment. Follow these steps in
order when setting up a new organization for the first time.

---

## Prerequisites

- You have System Admin credentials.
- The Cadence platform is running and accessible.
- You have an LLM API key (e.g., from OpenAI or Anthropic) to use as the global default.

---

## Step-by-Step Setup

### Step 1: Log In as System Admin

1. Navigate to the Cadence login page.
2. Enter your System Admin email and password.
3. Click **Log In**.

You will land on the main dashboard. The admin panel is accessible via the **Admin** menu in the top navigation bar.

---

### Step 2: Create an Organization

1. Go to **Admin → Organizations → New Organization**.
2. Fill in the required fields:
    - **Name**: The display name of the organization (e.g., "Acme Corp").
    - **Tier**: Select the service tier for this org (e.g., Free, Pro).
3. Click **Create Organization**.

The organization is created and you will see it in the organizations list.

---

### Step 3: Create a User Account

1. Go to **Admin → Users → New User**.
2. Fill in the user details:
    - **Email**: The user's login email.
    - **Password**: Set a temporary password (the user should change this on first login).
    - **Role**: Select **Member** for a regular user, or **Org Admin** to grant admin access.
3. Click **Create User**.

---

### Step 4: Assign User to Organization

1. Go to **Admin → Organizations** and select the organization you created.
2. Click **Members → Add Member**.
3. Search for the user by email and select them.
4. Set their **role within this org** (Member or Org Admin).
5. Click **Add**.

The user can now log in and access this organization.

---

### Step 5: Upload a System-Level Plugin (Optional)

If you have platform-wide plugins to make available:

1. Go to **Admin → Plugins → Upload Plugin**.
2. Click **Choose File** and select the plugin ZIP archive.
3. Click **Upload**.

Cadence will validate the plugin structure. If valid, the plugin will appear in the plugins list and can be assigned to
orchestrators by Org Admins.

---

### Step 6: Set Global LLM Configuration

1. Go to **Admin → Settings → LLM Configuration**.
2. Click **Add LLM Config**.
3. Fill in the details:
    - **Provider**: Select your LLM provider (e.g., OpenAI, Anthropic).
    - **API Key**: Enter your API key.
    - **Model**: Enter the model name (e.g., `gpt-4o`, `claude-3-5-sonnet`).
4. Click **Save**.

This config will be available as a default for all organizations. Org Admins can also add their own org-specific LLM
configs.

---

### Step 7: Monitor Platform Health

1. Go to **Admin → Health**.
2. Review the status indicators:
    - **API**: The backend service status.
    - **Database**: Connection to the database.
    - **Message Broker**: RabbitMQ connectivity.
    - **Orchestrator Pool**: How many instances are loaded and available.

All indicators should show green (healthy) before allowing users to start chatting.

---

## Checklist

- [ ] Logged in as System Admin
- [ ] Created at least one organization
- [ ] Created user accounts
- [ ] Assigned users to their organizations with correct roles
- [ ] Uploaded system plugins (if applicable)
- [ ] Configured global LLM credentials
- [ ] Verified platform health is green

---

## Next Steps

Hand off to the Org Admin by sharing their login credentials. Point them to the [Org Admin Setup](org-admin.md) guide.
