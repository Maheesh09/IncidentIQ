# Verifying webhook signatures

When an incident analysis completes, IncidentIQ delivers the RCA report to your configured
webhook URL as an HTTP `POST`. Every delivery is signed with HMAC-SHA256 so you can confirm
the request actually came from IncidentIQ and wasn't forged or tampered with in transit.

**You should verify every webhook before trusting its contents.** An unverified endpoint will
accept a POST from anyone who finds the URL.

---

## What gets sent

```
POST <your webhook URL>
Content-Type: application/json
X-IncidentIQ-Signature: sha256=<hex-encoded HMAC-SHA256>
X-IncidentIQ-Event: rca.completed
User-Agent: IncidentIQ-Webhook/1.0

{
  "event": "rca.completed",
  "incident_id": "INC-20260718-A3F9C12B",
  "delivered_at": "2026-07-18T14:37:02.113Z",
  "report": { ... full RCA report ... }
}
```

The signature is computed over the **exact raw JSON body bytes** — the same string that's
sent on the wire — using the webhook secret you provided in
`POST /management/webhook`. This is the detail that trips people up: if your framework parses
the JSON and you re-serialize it before checking the signature, the bytes won't match even
though the data is identical. Always verify against the raw body, before any JSON parsing.

---

## Verification steps

1. Read the raw request body as bytes — don't let your framework parse it first.
2. Compute `HMAC-SHA256(your_webhook_secret, raw_body_bytes)`, hex-encoded.
3. Compare it to the value after `sha256=` in the `X-IncidentIQ-Signature` header.
4. Use a constant-time comparison, not `==` — a naive string comparison leaks timing
   information an attacker can use to guess the signature byte by byte.
5. Reject the request (`401`) if the signatures don't match, or if the header is missing.

---

## Example: Python (FastAPI)

```python
import hashlib
import hmac

from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI()

WEBHOOK_SECRET = "your-webhook-secret"  # from POST /management/webhook


def verify_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify an IncidentIQ webhook signature.

    Args:
        raw_body: The exact raw request body bytes.
        signature_header: The X-IncidentIQ-Signature header value, e.g. 'sha256=abc123...'.
        secret: Your organisation's webhook signing secret.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    provided_signature = signature_header.removeprefix("sha256=")
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(provided_signature, expected_signature)


@app.post("/webhooks/incidentiq")
async def receive_rca_report(
    request: Request,
    x_incidentiq_signature: str = Header(None),
):
    raw_body = await request.body()

    if not verify_signature(raw_body, x_incidentiq_signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    incident_id = payload["incident_id"]
    report = payload["report"]

    # ... handle the verified report ...
    return {"status": "received"}
```

---

## Example: Node.js (Express)

```javascript
const crypto = require("crypto");
const express = require("express");

const app = express();
const WEBHOOK_SECRET = "your-webhook-secret"; // from POST /management/webhook

// Capture the raw body — express.json() alone parses before you can verify.
app.use(
  express.json({
    verify: (req, res, buf) => {
      req.rawBody = buf;
    },
  })
);

function verifySignature(rawBody, signatureHeader, secret) {
  if (!signatureHeader || !signatureHeader.startsWith("sha256=")) {
    return false;
  }

  const provided = signatureHeader.slice("sha256=".length);
  const expected = crypto
    .createHmac("sha256", secret)
    .update(rawBody)
    .digest("hex");

  // timingSafeEqual requires equal-length buffers
  const providedBuf = Buffer.from(provided, "hex");
  const expectedBuf = Buffer.from(expected, "hex");
  if (providedBuf.length !== expectedBuf.length) return false;

  return crypto.timingSafeEqual(providedBuf, expectedBuf);
}

app.post("/webhooks/incidentiq", (req, res) => {
  const signature = req.headers["x-incidentiq-signature"];

  if (!verifySignature(req.rawBody, signature, WEBHOOK_SECRET)) {
    return res.status(401).json({ error: "Invalid webhook signature" });
  }

  const { incident_id, report } = req.body;
  // ... handle the verified report ...
  res.status(200).json({ status: "received" });
});
```

---

## Common mistakes

| Mistake | Why it breaks verification |
|---|---|
| Verifying against `JSON.stringify(parsedBody)` | Re-serialization can reorder keys or change whitespace — bytes no longer match what was signed |
| Using `===` / `==` to compare signatures | Vulnerable to timing attacks; use `hmac.compare_digest` (Python) or `crypto.timingSafeEqual` (Node) |
| Forgetting the `sha256=` prefix when comparing | The header value always includes the prefix — strip it before comparing hex digests |
| Reusing one webhook secret across environments | Rotate secrets per environment (staging vs production) via `POST /management/webhook` |

---

## Retry behaviour

If your endpoint doesn't respond with `200`, `201`, `202`, or `204`, or times out, IncidentIQ
retries delivery up to **3 times** with increasing delays (2s, 5s, 10s). Design your endpoint
to be idempotent on `incident_id` — a retried delivery carries the same `incident_id` and
`report`, so handle duplicate deliveries safely (e.g. upsert rather than insert).