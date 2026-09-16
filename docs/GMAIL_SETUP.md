# Setting Up Gmail / Google App Password Authentication

This application supports delivering repository discovery reports directly to your inbox using Gmail and Google's official App Authorization mechanism (**Google App Passwords**).

## Why Google App Passwords?

For automated CLI scripts and background services, Google recommends using an **App Password**. 

An App Password is a 16-character passcode that grants an application access to your Google Account without exposing your primary account password or requiring interactive OAuth web authorization prompts.

---

## Step-by-step Setup Guide

### Step 1: Enable 2-Step Verification
Google requires 2-Step Verification to generate App Passwords.

1. Go to your [Google Account Security Settings](https://myaccount.google.com/security).
2. Under **"How you sign in to Google"**, verify that **2-Step Verification** is turned **ON**.
3. If it is off, follow Google's instructions to enable it.

### Step 2: Generate an App Password
1. Visit:
   ```text
   https://myaccount.google.com/apppasswords
   ```
   *(Alternatively, in Google Account search for "App Passwords".)*
2. Under **App name**, enter a descriptive name, for example:
   ```text
   github-repo-finder
   ```
3. Click **Create**.
4. Google will display a 16-character password formatted like:
   ```text
   abcd efgh ijkl mnop
   ```
5. Copy this password. You will not be shown this password again.

### Step 3: Configure `.env`
Open your `.env` file in the project root:

```env
# Enable email reporting
EMAIL_NOTIFICATIONS_ENABLED=true

# Your Gmail address
GMAIL_USER=your_username@gmail.com

# The 16-character Google App Password generated in Step 2
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop

# Destination email address where reports will be delivered
EMAIL_RECIPIENT=your_destination_email@example.com
```

*(Note: Spaces in `GMAIL_APP_PASSWORD` are automatically stripped by the application.)*

---

## Safe Testing & Dummy Values

When `EMAIL_NOTIFICATIONS_ENABLED=false` or when placeholder values (like `your_email@gmail.com`) are present in `.env`, email sending is cleanly skipped and logged without generating any errors.

---

## Security Best Practices

- **Never commit `.env` to version control.** `.env` is listed in `.gitignore`.
- If an App Password is compromised, instantly revoke it under [Google App Passwords](https://myaccount.google.com/apppasswords).
- Never share your App Password in screenshots, bug reports, or pull requests.
