import os
import requests
import hashlib
import base64
import datetime
import json
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

load_dotenv()

OCI_USER = os.getenv("OCI_USER")
OCI_FINGERPRINT = os.getenv("OCI_FINGERPRINT")
OCI_TENANCY = os.getenv("OCI_TENANCY")
OCI_REGION = os.getenv("OCI_REGION")
OCI_KEY_FILE = os.getenv("OCI_KEY_FILE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def load_private_key():
    with open(os.path.expanduser(OCI_KEY_FILE), "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def sign(key, message: str) -> str:
    signature = key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("utf-8")


def build_auth_header(method: str, host: str, path: str, body: str = "") -> dict:
    now = datetime.datetime.now(datetime.UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")

    body_bytes = body.encode("utf-8")
    body_hash = base64.b64encode(hashlib.sha256(body_bytes).digest()).decode("utf-8")

    signing_string = (
        f"date: {now}\n"
        f"(request-target): {method.lower()} {path}\n"
        f"host: {host}\n"
        f"content-length: {len(body_bytes)}\n"
        f"content-type: application/json\n"
        f"x-content-sha256: {body_hash}"
    )

    key = load_private_key()
    signature = sign(key, signing_string)
    key_id = f"{OCI_TENANCY}/{OCI_USER}/{OCI_FINGERPRINT}"

    auth = (
        f'Signature version="1",'
        f'keyId="{key_id}",'
        f'algorithm="rsa-sha256",'
        f'headers="date (request-target) host content-length content-type x-content-sha256",'
        f'signature="{signature}"'
    )

    return {
        "Authorization": auth,
        "Date": now,
        "Content-Type": "application/json",
        "x-content-sha256": body_hash,
        "Content-Length": str(len(body_bytes)),
    }


def build_get_auth_header(method: str, host: str, path: str) -> dict:
    """Build auth header for GET requests (no body)."""
    now = datetime.datetime.now(datetime.UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")

    signing_string = (
        f"date: {now}\n"
        f"(request-target): {method.lower()} {path}\n"
        f"host: {host}"
    )

    key = load_private_key()
    signature = sign(key, signing_string)
    key_id = f"{OCI_TENANCY}/{OCI_USER}/{OCI_FINGERPRINT}"

    auth = (
        f'Signature version="1",'
        f'keyId="{key_id}",'
        f'algorithm="rsa-sha256",'
        f'headers="date (request-target) host",'
        f'signature="{signature}"'
    )

    return {
        "Authorization": auth,
        "Date": now,
    }


def send_telegram(message: str):
    """Send a message to Telegram."""
    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
        timeout=10,
    )
    if response.status_code != 200:
        print(f"[telegram] failed to send: {response.text}")


def get_usage_costs() -> float:
    """Query daily usage costs for the current month."""
    now = datetime.datetime.now(datetime.UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # If it's the first day of the month, there's no range to query
    if start == end:
        return 0.0

    host = f"usageapi.{OCI_REGION}.oci.oraclecloud.com"
    path = "/20200107/usage"

    body = json.dumps({
        "tenantId": OCI_TENANCY,
        "timeUsageStarted": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "timeUsageEnded": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "granularity": "DAILY",
        "queryType": "COST",
    })

    headers = build_auth_header("POST", host, path, body)
    response = requests.post(f"https://{host}{path}", headers=headers, data=body, timeout=30)

    if response.status_code != 200:
        raise Exception(f"Usage API error: {response.status_code} - {response.text}")

    items = response.json().get("items", [])
    total = sum(item.get("computedAmount") or 0 for item in items)

    print(f"[usage]    daily computed amount this month: {total:.6f} BRL ({len(items)} days)")
    return total


def get_invoice_costs() -> float:
    """Query open/unpaid invoices to catch charges not yet reflected in usage API."""
    host = "invoicing.us-ashburn-1.oci.oraclecloud.com"
    path = f"/20181115/invoices?compartmentId={OCI_TENANCY}&invoiceStatus=OPEN"

    headers = build_get_auth_header("GET", host, path)
    response = requests.get(f"https://{host}{path}", headers=headers, timeout=30)

    if response.status_code == 404:
        print("[invoices] no open invoices found")
        return 0.0

    if response.status_code != 200:
        raise Exception(f"Invoices API error: {response.status_code} - {response.text}")

    items = response.json().get("items", [])
    total = sum(float(item.get("invoiceAmount") or 0) for item in items)

    print(f"[invoices] open invoice total: {total:.6f} BRL ({len(items)} invoices)")
    return total


def main():
    now_str = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Checking OCI billing — {now_str}\n")

    usage_total = 0.0
    invoice_total = 0.0
    errors = []

    try:
        usage_total = get_usage_costs()
    except Exception as e:
        errors.append(f"Usage API failed: {e}")
        print(f"[usage]    ERROR: {e}")

    try:
        invoice_total = get_invoice_costs()
    except Exception as e:
        errors.append(f"Invoices API failed: {e}")
        print(f"[invoices] ERROR: {e}")

    grand_total = usage_total + invoice_total
    print(f"\nTotal (usage + invoices): {grand_total:.6f} BRL")

    both_failed = len(errors) == 2

    if both_failed:
        # Both APIs failed — send a warning, result is unreliable
        message = (
            f"⚠️ <b>OCI ANTI FRAUD — APIs Failed</b>\n"
            f"📅 {now_str}\n\n"
            f"Unable to verify charges:\n"
            + "\n".join(f"• {e}" for e in errors)
        )
        print("\n⚠️  WARNING: both APIs failed, result is unreliable!")
    elif grand_total > 0:
        # Charges detected — send alert
        message = (
            f"🚨 <b>OCI ANTI FRAUD — CHARGES DETECTED</b>\n"
            f"📅 {now_str}\n\n"
            f"Usage API:      <b>{usage_total:.6f} BRL</b>\n"
            f"Open Invoices: <b>{invoice_total:.6f} BRL</b>\n"
            f"Total:          <b>{grand_total:.6f} BRL</b>\n\n"
            f"🚨 ALERTA DE RESENHA 🚨 INFELIZMENTE OS BANDIDOS VENCERAM, HORA DE NOS RENDERMOS..."
        )
        print("\n🚨 ALERT: charges detected!")
    else:
        # All clear — send daily summary
        message = (
            f"✅ <b>OCI ANTI FRAUD — NO CHARGES TODAY</b>\n"
            f"📅 {now_str}\n\n"
            f"Usage API:       0.000000 BRL\n"
            f"Open Invoices: 0.000000 BRL\n\n"
            f"Bandits are sleeping peacefully... 💤"
        )
        print("✅ No charges detected.")

    send_telegram(message)


main()