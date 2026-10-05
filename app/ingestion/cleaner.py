"""
Text cleaner for the BantenPedia ingestion pipeline.

Rules follow PRD §10:
  ✅ Remove excess whitespace
  ✅ Remove non-printable / control characters
  ✅ Rejoin broken lines (heuristic)
  ✅ Clean obvious OCR artefacts
  ❌ Do NOT translate Balinese terms
  ❌ Do NOT alter cultural names (banten names, local names)
  ❌ Do NOT add information not in the source
"""

import re


# Characters that are clearly OCR noise and can be safely removed
_NOISE_PATTERN = re.compile(
    r"[^\S\n]+"          # Horizontal whitespace runs (collapse later)
    r"|[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]"  # Control chars (keep \n and \t)
)

# Detect a line that ends mid-word (no punctuation, lowercase start next line)
_BROKEN_LINE = re.compile(r"([a-zA-Z,;])\n([a-z])")


def clean_text(text: str) -> str:
    """
    Clean raw extracted text without altering cultural content.

    Steps:
    1. Strip control characters / noise.
    2. Rejoin broken OCR / PDF lines.
    3. Collapse horizontal whitespace runs.
    4. Normalise paragraph breaks (2+ newlines → double newline).
    5. Strip leading/trailing whitespace.

    Args:
        text: Raw extracted text.

    Returns:
        Cleaned text preserving all cultural terms and names.
    """
    if not text:
        return ""

    # 1. Remove control characters (preserve \n)
    text = re.sub(
        r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]",
        "",
        text
    )

    # 2. Rejoin broken lines (lowercase letter continues on next line)
    text = _BROKEN_LINE.sub(r"\1 \2", text)

    # 3. Collapse horizontal whitespace within a line
    text = re.sub(r"[^\S\n]+", " ", text)

    # 4. Normalise multiple blank lines to exactly two newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 5. Strip
    return text.strip()
