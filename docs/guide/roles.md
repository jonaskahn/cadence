# Roles & Permissions

Cadence has four access levels. This page shows which actions each role can perform.

---

## Role Definitions

| Role                | Description                                           |
|---------------------|-------------------------------------------------------|
| **Unauthenticated** | A visitor who has not logged in                       |
| **Member**          | A logged-in user within an organization               |
| **Org Admin**       | An administrator of a specific organization           |
| **Sys Admin**       | A platform-wide administrator with access to all orgs |

---

## Permission Matrix

| Action                        | Unauthenticated |  Member   | Org Admin | Sys Admin |
|-------------------------------|:---------------:|:---------:|:---------:|:---------:|
| **Authentication**            |                 |           |           |           |
| Log in                        |       Yes       |     —     |     —     |     —     |
| Log out                       |        —        |    Yes    |    Yes    |    Yes    |
| Switch organization           |        —        |   Yes*    |   Yes*    |    Yes    |
| **Chat**                      |                 |           |           |           |
| View chat interface           |        —        |    Yes    |    Yes    |    Yes    |
| Send a message                |        —        |    Yes    |    Yes    |    Yes    |
| Start a new conversation      |        —        |    Yes    |    Yes    |    Yes    |
| View conversation history     |        —        | Yes (own) | Yes (org) | Yes (all) |
| **Orchestrators**             |                 |           |           |           |
| View available orchestrators  |        —        |    Yes    |    Yes    |    Yes    |
| Create orchestrator instance  |        —        |     —     |    Yes    |    Yes    |
| Load instance (Hot)           |        —        |     —     |    Yes    |    Yes    |
| Unload instance (Cold)        |        —        |     —     |    Yes    |    Yes    |
| Hot-reload configuration      |        —        |     —     |    Yes    |    Yes    |
| Delete orchestrator instance  |        —        |     —     |    Yes    |    Yes    |
| **Plugins**                   |                 |           |           |           |
| Upload a plugin               |        —        |     —     |    Yes    |    Yes    |
| Assign plugin to orchestrator |        —        |     —     |    Yes    |    Yes    |
| Configure plugin settings     |        —        |     —     |    Yes    |    Yes    |
| Update plugin version         |        —        |     —     |    Yes    |    Yes    |
| **User Management**           |                 |           |           |           |
| View users in own org         |        —        |     —     |    Yes    |    Yes    |
| Add user to org               |        —        |     —     |    Yes    |    Yes    |
| Remove user from org          |        —        |     —     |    Yes    |    Yes    |
| Change user role within org   |        —        |     —     |    Yes    |    Yes    |
| **Organization Management**   |                 |           |           |           |
| View own org settings         |        —        |    Yes    |    Yes    |    Yes    |
| Edit org settings             |        —        |     —     |    Yes    |    Yes    |
| Create a new organization     |        —        |     —     |     —     |    Yes    |
| Delete an organization        |        —        |     —     |     —     |    Yes    |
| View all organizations        |        —        |     —     |     —     |    Yes    |
| **System Administration**     |                 |           |           |           |
| View platform health          |        —        |     —     |     —     |    Yes    |
| View orchestrator pool stats  |        —        |     —     |     —     |    Yes    |
| Edit global LLM config        |        —        |     —     |     —     |    Yes    |
| Edit global system settings   |        —        |     —     |     —     |    Yes    |
| Manage all users (any org)    |        —        |     —     |     —     |    Yes    |

*Members and Org Admins can only access organizations they have membership in.

---

## Notes

- A **Sys Admin** can also act as an Org Admin within any organization.
- Role assignments are per-organization — a user can be an Org Admin in one org and a Member in another.
- The **Unauthenticated** role only applies to the login page. All other areas require authentication.
