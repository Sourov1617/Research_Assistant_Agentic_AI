"""
Robust JSON parsing utilities for LangChain pipelines.

LLMs frequently produce JSON with trailing commas before ] or } which
json.loads() rejects.  The helpers here clean up common issues before
parsing, and RobustJsonOutputParser is a drop-in replacement for
langchain_core.output_parsers.JsonOutputParser that applies the cleanup.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.output_parsers import BaseOutputParser

logger = logging.getLogger(__name__)


def robust_json_parse(text: str) -> dict:
    """
    Parse a JSON string that may contain common LLM output quirks:
      - Markdown fences  ```json ... ```
      - Trailing commas before ] or }
      - Leading/trailing whitespace

    Returns an empty dict on any remaining parse failure.
    """
    text = text.strip()

    # Strip markdown fences (```json ... ``` or ``` ... ```)
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    # Remove trailing commas directly before ] or } (handles whitespace/newlines)
    text = re.sub(r',\s*([\]}])', r'\1', text)

    # Attempt to extract a JSON object if there's surrounding noise
    if not text.startswith('{'):
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            text = m.group(0)
            # Re-apply trailing-comma removal on the extracted block
            text = re.sub(r',\s*([\]}])', r'\1', text)

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("robust_json_parse: final parse failed: %s", exc)
        return {}


class RobustJsonOutputParser(BaseOutputParser):
    """
    Drop-in replacement for JsonOutputParser.
    Uses robust_json_parse() so trailing commas in LLM output
    no longer cause an OutputParsingFailure exception.
    """

    def parse(self, text: str) -> Any:
        result = robust_json_parse(text)
        if not result:
            # Return minimal dict so downstream code doesn't crash on .get()
            logger.warning("RobustJsonOutputParser: parse returned empty dict.")
        return result

    def get_format_instructions(self) -> str:
        return "Return ONLY valid JSON. No markdown fences, no trailing commas."

    @property
    def _type(self) -> str:
        return "robust_json_output_parser"
