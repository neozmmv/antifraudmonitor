# OCI ANTI FRAUD

WE DO NOT TRUST ORACLE!

Monitors your Oracle Cloud Infrastructure (OCI) account for unexpected charges and sends a daily Telegram notification. Useful if you're on a PAYG account using Always Free resources and want to know the moment Oracle starts billing you.

Checks two independent sources:

- **Usage API** — daily computed costs for the current month
- **Invoices API** — open/unpaid invoices not yet reflected in usage

---

## Requirements

- Python 3.10+
- A Telegram account
- An OCI account (PAYG or free tier)

---

## 1. Generate OCI API Keys

Run this on your machine (Linux/macOS/WSL):

```bash
mkdir -p ~/.oci
openssl genrsa -out ~/.oci/oci_api_key.pem 2048
openssl rsa -pubout -in ~/.oci/oci_api_key.pem -out ~/.oci/oci_api_key_public.pem
chmod 600 ~/.oci/oci_api_key.pem
```

---

## 2. Register the Public Key in OCI Console

1. Go to [cloud.oracle.com](https://cloud.oracle.com) and sign in
2. Click your avatar (top right) → **My profile**
3. In the left menu → **API keys** → **Add API key**
4. Select **Paste a public key**
5. Paste the contents of `~/.oci/oci_api_key_public.pem`
6. Click **Add**

OCI will show a config preview like this — copy the values:

```
user=ocid1.user.oc1..xxxxxxxxxx
fingerprint=xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx
tenancy=ocid1.tenancy.oc1..xxxxxxxxxx
region=sa-saopaulo-1
```

---

## 3. Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** (format: `123456789:ABCdef...`)
4. Send any message to your new bot (e.g. "hi")
5. Open this URL in your browser to get your chat ID:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
6. Find `"chat": {"id": 123456789}` — that number is your **chat ID**

---

## 4. Set Up the Project

```bash
git clone https://github.com/neozmmv/antifraudmonitor
cd antifraudmonitor
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
OCI_KEY_FILE=/home/youruser/.oci/oci_api_key.pem
OCI_REGION=sa-saopaulo-1
OCI_USER=ocid1.user.oc1..xxxxxxxxxx
OCI_FINGERPRINT=xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx
OCI_TENANCY=ocid1.tenancy.oc1..xxxxxxxxxx
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=123456789
```

---

## 5. Test It

```bash
source env/bin/activate
python main.py
```

You should see output like:

```
Checking OCI billing — 2026-06-18 20:27 UTC

[usage]    daily computed amount this month: 0.000000 BRL (17 days)
[invoices] no open invoices found

Total (usage + invoices): 0.000000 BRL
✅ No charges detected.
```

And a message in your Telegram chat.

---

## 6. Schedule with Cron (runs daily at 9am)

Open your crontab:

```bash
crontab -e
```

Add this line (adjust paths as needed):

```
0 9 * * * /home/youruser/antifraudmonitor/env/bin/python /home/youruser/antifraudmonitor/main.py >> /home/youruser/antifraudmonitor/watcher.log 2>&1
```

> **Note:** cron doesn't load `.bashrc` or activate virtualenvs, so we call the Python binary directly from inside the `env/` folder. The `>> watcher.log` part saves all output to a log file for debugging.

Verify it's registered:

```bash
crontab -l
```

---

## Telegram Notifications

| Status              | Message                                |
| ------------------- | -------------------------------------- |
| ✅ No charges       | Daily summary confirming zero billing  |
| 🚨 Charges detected | Alert with usage and invoice breakdown |
| ⚠️ Both APIs failed | Warning that the result is unreliable  |

---

## .env Reference

| Variable             | Description                                    |
| -------------------- | ---------------------------------------------- |
| `OCI_KEY_FILE`       | Path to your OCI private key `.pem` file       |
| `OCI_REGION`         | Your OCI home region (e.g. `sa-saopaulo-1`)    |
| `OCI_USER`           | Your user OCID from OCI console                |
| `OCI_FINGERPRINT`    | Key fingerprint shown after adding the API key |
| `OCI_TENANCY`        | Your tenancy OCID from OCI console             |
| `TELEGRAM_BOT_TOKEN` | Token from @BotFather                          |
| `TELEGRAM_CHAT_ID`   | Your Telegram user/chat ID                     |
