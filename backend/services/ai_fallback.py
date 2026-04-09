"""AI fallback extraction layer for low-confidence medicine scans.

This module is intentionally used only as a fallback and never as the
primary extraction or decision engine.
"""

import json
import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)


def extract_with_ai(image_base64: str) -> Dict:
    """Extract structured medicine fields using OpenAI Vision as fallback.

    Args:
        image_base64: Base64-encoded image data (without data URL prefix).

    Returns:
        Dictionary with any subset of:
        medicine_name, manufacturer, batch_number, expiry_date, dosage.
        Returns empty dict on failure.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("AI fallback unavailable: OPENAI_API_KEY not configured")
        return {}

    try:
        from openai import OpenAI
    except Exception as exc:
        logger.error(f"AI fallback unavailable: OpenAI SDK import failed: {exc}")
        return {}

    instruction = (
        "Extract the following fields from this medicine package image:\n\n"
        "* medicine_name\n"
        "* manufacturer\n"
        "* batch_number\n"
        "* expiry_date\n"
        "* dosage\n\n"
        "Return ONLY valid JSON. No explanation."
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": instruction,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
        )

        raw = (response.choices[0].message.content or "").strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            logger.warning("AI fallback returned non-dict JSON payload")
            return {}

        allowed_keys = [
            "medicine_name",
            "manufacturer",
            "batch_number",
            "expiry_date",
            "dosage",
        ]
        return {k: parsed.get(k) for k in allowed_keys if parsed.get(k)}

    except json.JSONDecodeError as exc:
        logger.warning(f"AI fallback returned invalid JSON: {exc}")
        return {}
    except Exception as exc:
        logger.warning(f"AI fallback extraction failed: {exc}")
        return {}
