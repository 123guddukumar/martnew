# Deployment Guide for WhatsApp Backend

This guide outlines the steps to push only the `backend` directory to GitHub, deploy it to Render, and set up your WhatsApp webhook with the Cloud API credentials.

## 1. Push Backend to GitHub

I have already initialized a separate git repository inside your `backend/` folder and created a `.gitignore` to protect your sensitive data (like `.env`).

**Steps to push:**
1. Create a **new, empty repository** on [GitHub](https://github.com/new).
2. Open your terminal at `whatsapp-ordering-system/backend` and run:
   ```bash
   git remote add origin YOUR_GITHUB_REPO_URL
   git branch -M main
   git push -u origin main
   ```

---

## 2. Deploy to Render

### Step 1: Create a PostgreSQL Web Service
1. Go to [Render Dashboard](https://dashboard.render.com/).
2. Click **New** > **Web Service**.
3. Connect your new GitHub repository.
4. **Name**: `whatsapp-backend` (or similar).
5. **Runtime**: `Docker` (Render will detect the `Dockerfile` automatically).
6. Click **Advanced** and add the following Environment Variables:

| Key | Value |
| :--- | :--- |
| `SECRET_KEY` | *Generate a random long string* |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `whatsapp-backend.onrender.com` (Use your actual Render URL) |
| `DATABASE_URL` | *Use Render's Internal Database URL* |
| `REDIS_URL` | *Provided by Upstash or Render Redis* |
| `WHATSAPP_ACCESS_TOKEN` | *Your Meta Permanent Token* |
| `WHATSAPP_PHONE_NUMBER_ID` | *Meta Phone ID* |
| `WHATSAPP_VERIFY_TOKEN` | `my_custom_verify_token_123` (Same as in `.env`) |

---

## 3. Configure Meta Webhook

Once your backend is live (e.g., `https://myapp.onrender.com`), set up the webhook in your [Meta App Dashboard](https://developers.facebook.com):

1. **Callback URL**: `https://YOUR_APP_URL.onrender.com/api/whatsapp/webhook/`
2. **Verify Token**: `my_custom_verify_token_123`
3. Click **Verify and Save**.
4. Subscribe to the `messages` fields under **Webhooks**.

---

## Webhook Verification Logic
The backend already contains the logic to handle Meta's verification handshake and incoming messages.

```python
# whatsapp/views.py (Handled automatically)
def get(self, request):
    mode = request.GET.get('hub.mode')
    token = request.GET.get('hub.verify_token')
    challenge = request.GET.get('hub.challenge')

    if mode == 'subscribe' and token == settings.WHATSAPP_VERIFY_TOKEN:
        return HttpResponse(challenge, content_type='text/plain')
    return HttpResponse('Forbidden', status=403)
```
