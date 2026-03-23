"""n8n workflow trigger plugin.

Sends a POST request to an n8n webhook endpoint, allowing the agent to
kick off automation workflows with arbitrary payloads.
"""

import httpx

from api.plugins import tool

_N8N_BASE_URL = "http://ai-n8n:5678"
_REQUEST_TIMEOUT = 15.0  # seconds


@tool(
    name="trigger_workflow",
    description="Trigger an n8n workflow by webhook ID with a payload",
)
async def trigger_workflow(webhook_id: str, payload: dict) -> dict:
    """Trigger an n8n workflow via its webhook URL.

    Args:
        webhook_id: The n8n webhook ID (appears after /webhook/ in the URL).
        payload: Arbitrary JSON-serialisable dict to send as the request body.

    Returns:
        A dict with keys ``status_code`` and ``response``.  ``response`` is
        the parsed JSON body when the server returns JSON, otherwise the raw
        text.
    """
    url = f"{_N8N_BASE_URL}/webhook/{webhook_id}"

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        resp = await client.post(url, json=payload)

    try:
        response_body = resp.json()
    except Exception:
        response_body = resp.text

    return {
        "status_code": resp.status_code,
        "response": response_body,
    }
