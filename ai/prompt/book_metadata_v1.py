from models.book import BookRecord


def build_book_metadata_prompt(record: BookRecord) -> str:
    """
    Build prompt for AI to enrich book metadata.
    Output MUST be valid JSON according to book_metadata_v1 contract.
    """

    lines: list[str] = []

    lines.append(
        "You are a bibliographic metadata extraction engine."
    )

    lines.append(
        "Given partial information about a book file, "
        "identify the most likely edition and its original work."
    )

    lines.append("\nKnown file context:")

    lines.append(f"- Filename: {record.original_filename}")
    lines.append(f"- Extension: {record.extension}")

    if record.directories:
        lines.append(
            "- Directory context: "
            + " / ".join(record.directories)
        )

    # --- Existing edition ---
    if any([
        record.title,
        record.subtitle,
        record.authors,
        record.series,
        record.language,
        record.year,
        record.publisher,
    ]):
        lines.append("\nExisting edition metadata:")

        if record.title:
            lines.append(f"- Title: {record.title}")
        if record.subtitle:
            lines.append(f"- Subtitle: {record.subtitle}")
        if record.authors:
            lines.append(f"- Authors: {', '.join(record.authors)}")
        if record.series:
            lines.append(f"- Series: {record.series}")
        if record.series_index is not None:
            lines.append(f"- Series number: {record.series_index}")
        if record.series_total is not None:
            lines.append(f"- Series total: {record.series_total}")
        if record.language:
            lines.append(f"- Language: {record.language}")
        if record.publisher:
            lines.append(f"- Publisher: {record.publisher}")
        if record.year:
            lines.append(f"- Published year: {record.year}")

    # --- Existing original ---
    if record.original:
        lines.append("\nExisting original work metadata:")

        if record.original.title:
            lines.append(f"- Original title: {record.original.title}")
        if record.original.authors:
            lines.append(f"- Original authors: {', '.join(record.original.authors)}")
        if record.original.language:
            lines.append(f"- Original language: {record.original.language}")
        if record.original.year:
            lines.append(f"- Original year: {record.original.year}")

    # --- Instructions ---
    lines.append(
        "\nInstructions:\n"
        "- Respond ONLY with valid JSON\n"
        "- Do NOT include explanations or comments\n"
        "- Omit unknown fields\n"
        "- Use UTF-8\n"
    )

    # --- Contract ---
    lines.append(
        "JSON format (book_metadata_v1):\n"
        "{\n"
        '  "edition": {\n'
        '    "title": string,\n'
        '    "subtitle": string,\n'
        '    "authors": [string],\n'
        '    "series": string,\n'
        '    "series_index": integer,\n'
        '    "series_total": integer,\n'
        '    "language": string,\n'
        '    "publisher": string,\n'
        '    "year": integer,\n'
        '    "isbn10": string,\n'
        '    "isbn13": string,\n'
        '    "asin": string\n'
        "  },\n"
        '  "original": {\n'
        '    "title": string,\n'
        '    "authors": [string],\n'
        '    "language": string,\n'
        '    "year": integer\n'
        "  },\n"
        '  "confidence": number\n'
        "}\n"
    )

    return "\n".join(lines)
