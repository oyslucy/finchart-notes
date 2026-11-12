"""News PDF translation through the Claude API (paid; enabled by ANTHROPIC_API_KEY)."""

import base64
import json
import logging

import anthropic
from anthropic import transform_schema
from pydantic import ValidationError

from finchart_api.domain.articles import ArticleTranslation, TranslationResult, TranslatorError

log = logging.getLogger("finchart.translate")

# Original plus Korean roughly doubles the article's length in output tokens; a 30-page
# cap on input keeps ordinary news well under this.
MAX_OUTPUT_TOKENS = 32_000

SYSTEM = """You turn a news article PDF into a bilingual reading copy for a Korean investor.

Rules:
- Rebuild the article body in reading order. Join lines broken by the page layout and \
undo hyphenation, but do not reword, shorten or summarise the original.
- Leave out page furniture: running headers and footers, page numbers, navigation, ads, \
subscription prompts, share buttons, related-article lists and image credits.
- Keep the article's own paragraphs; use kind "heading" for section headings inside it.
- Translate each paragraph into natural, fluent Korean as a financial journalist would \
write it. Keep numbers, units, dates, tickers and percentages exact. For companies and \
people use the common Korean name, adding the original in parentheses the first time \
when it is not obvious.
- If the article is already in Korean, copy it into original and leave translated empty.
- If the PDF holds several articles, use the main one.
- summary: at most three Korean sentences with the points an investor needs."""

INSTRUCTION = "Return the article as JSON in the given schema."


class ClaudeTranslator:
    def __init__(
        self, api_key: str, model: str, client: anthropic.AsyncAnthropic | None = None
    ) -> None:
        # The SDK retries rate limits, overloads and 5xx responses itself.
        self._client = client or anthropic.AsyncAnthropic(api_key=api_key, max_retries=3)
        self._model = model
        self._schema = transform_schema(ArticleTranslation)

    async def translate(self, pdf: bytes) -> TranslationResult:
        document = base64.standard_b64encode(pdf).decode()
        try:
            # Streamed because a long article can take minutes to write out.
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": document,
                                },
                            },
                            {"type": "text", "text": INSTRUCTION},
                        ],
                    }
                ],
                output_config={"format": {"type": "json_schema", "schema": self._schema}},
            ) as stream:
                message = await stream.get_final_message()
        except anthropic.BadRequestError as exc:
            # Malformed, protected or oversized PDFs are rejected up front.
            raise TranslatorError("unreadable") from exc
        except anthropic.APIError as exc:
            raise TranslatorError("failed") from exc

        log.info(
            "translated with %s: %s in, %s out",
            message.model,
            message.usage.input_tokens,
            message.usage.output_tokens,
        )
        if message.stop_reason == "max_tokens":
            raise TranslatorError("too_long")
        text = "".join(block.text for block in message.content if block.type == "text")
        try:
            translation = ArticleTranslation.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise TranslatorError("failed") from exc
        return TranslationResult(translation=translation, model=message.model)
