"""
translator.py — Multi-Language Synthesis Support

Translates meeting summaries and email drafts into target languages while preserving
original transcript quotes and grounded action items.
"""
import logging
from typing import Any
from src.services.gemini_client import GeminiService

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = [
    "English", "Spanish", "French", "German",
    "Japanese", "Chinese", "Arabic", "Portuguese", "Hindi"
]


def translate_text(
    gemini: GeminiService,
    text: str,
    target_language: str,
) -> str:
    """
    Translate prose text to target_language using Gemini.
    """
    if target_language.lower() == "english" or not text.strip():
        return text

    prompt = (
        f"Translate the following executive meeting text accurately into {target_language}.\n"
        f"Preserve all formatting, markdown structure, action items, and quotation marks.\n\n"
        f"{text}"
    )

    translated = gemini.generate_text(
        prompt=prompt,
        temperature=0.2,
    )
    return translated.strip()
