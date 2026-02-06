from models.book import BookRecord


def build_book_metadata_prompt(record: BookRecord) -> str:
    """
    Build prompt for AI to enrich book metadata.
    Output MUST be valid JSON according to book_metadata.v2 contract.
    """

    lines = []

    # --- Role ---
    lines.append(
        "You are a bibliographic metadata expert. "
        "Your task is to enrich book metadata."
    )

    # --- Task ---
    lines.append(
        "Given partial information about a book file, "
        "identify the most likely book and its original work."
    )

    # --- Context: file & directories ---
    lines.append("\nKnown information:")

    lines.append(f"- Filename: {record.original_filename}")
    lines.append(f"- File extension: {record.extension}")

    if record.directories:
        lines.append(
            "- Directory path context: "
            + " / ".join(record.directories)
        )

    # --- Existing edition metadata ---
    if any(
        [
            record.title,
            record.authors,
            record.series,
            record.language,
            record.year,
        ]
    ):
        lines.append("\nExisting edition metadata:")

        if record.title:
            lines.append(f"- Title: {record.title}")
        if record.authors:
            lines.append(f"- Authors: {', '.join(record.authors)}")
        if record.series:
            lines.append(f"- Series: {record.series}")
        if record.series_index is not None:
            lines.append(f"- Series index: {record.series_index}")
        if record.language:
            lines.append(f"- Language: {record.language}")
        if record.year:
            lines.append(f"- Year: {record.year}")

    # --- Existing original metadata ---
    if record.original:
        lines.append("\nExisting original work metadata:")

        if record.original.title:
            lines.append(f"- Original title: {record.original.title}")
        if record.original.authors:
            lines.append(
                f"- Original authors: {', '.join(record.original.authors)}"
            )
        if record.original.language:
            lines.append(f"- Original language: {record.original.language}")
        if record.original.year:
            lines.append(f"- Original year: {record.original.year}")

    # --- Instructions ---
    lines.append(
        "\nInstructions:\n"
        "- Respond ONLY with valid JSON\n"
        "- Do NOT include explanations or comments\n"
        "- Use UTF-8\n"
        "- All fields are optional\n"
        "- Unknown information must be omitted\n"
    )

    # --- Contract ---
    lines.append(
        "JSON format (book_metadata v2):\n"
        "{\n"
        '  "edition": {\n'
        '    "title": string,\n'
        '    "authors": [string],\n'
        '    "series": string,\n'
        '    "series_index": integer,\n'
        '    "language": string,\n'
        '    "year": integer\n'
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
