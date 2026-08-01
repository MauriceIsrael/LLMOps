# Admin User Guide

Welcome to the SvelteKit Admin Dashboard. This guide explains how to manage the application, users, and permissions.

## 1. Authentication

The system uses secure session management with **bcrypt** password hashing.

- **Login**: Navigate to `/login`. Use your email and password.
- **Session**: Your session is valid for 15 minutes (Access Token) and 7 days (Refresh Token).
- **Logout**: Click your avatar in the top right and select "Sign Out".

### Demo Credentials
- **Admin**: `admin@example.com` / `admin123`
- **User**: `user@example.com` / `user123`

---

## 2. Managing Users

The **Users** tab in the Admin Panel allows you to manage the user lifecycle.

- **Add User**: Click "Add User" to create a new account. You must provide a name, email, password, and role.
- **Edit User**: Click the gear icon next to any user to update their name, role, or dynamic attributes.
- **Attributes**: JSON-based metadata used for ABAC decisions (e.g., `{"clearance": 3, "department": "Security"}`).

---

## 3. Managing Permissions (Casbin)

The **Permissions** tab provides direct access to the Casbin authorization engine.

### Policy Rules (P)
Define access rights for roles or users.
- **Subject**: Who is the rule for? (e.g., `admin`, `user`, or a specific user ID).
- **Object**: What is being accessed? (e.g., `*`, `api:users`, `ui:settings`).
- **Action**: What is allowed? (e.g., `*`, `read`, `write`).

### Grouping Rules (G)
Assign users to roles or groups.
- **User**: The subject ID or email.
- **Role/Group**: The target role (e.g., `admin`, `intern`, `manager`).

> [!IMPORTANT]
> Changes to permissions take effect immediately as the engine reloads policies on every update.

---

## 4. Understanding ABAC (Attribute-Based Access Control)

Decisions are made based on user **attributes** combined with Casbin rules.

- **Subject**: Your user profile attributes.
- **Object**: The target resource.
- **Action**: The operation.

---

## 5. Troubleshooting

- **"Internal Error"**: Check if the database is initialized (`npx prisma migrate dev`).
- **"Permission Denied"**: Your account attributes or role do not satisfy the requirements.
- **"Policy Already Exists"**: You are trying to add a duplicate rule in the Permissions tab.
