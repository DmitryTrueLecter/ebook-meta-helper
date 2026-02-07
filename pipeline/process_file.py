from pathlib import Path
import os

from models.book import BookRecord
from models.pipeline import PipelineResult
from move.mover import move_file
from naming.renamer import build_filename
from pipeline.debug import PipelineDebugger

from metadata.reader.registry import read_metadata
from ai.enrich import enrich
from metadata.merge.book_record_merger import merge_book_records
from metadata.writer.registry import write_metadata


def process_file(record: BookRecord) -> PipelineResult:
    path = Path(record.path)
    debugger = PipelineDebugger(path)
    errors: list[str] = []

    debugger.log("init", "input BookRecord from scanner", record)

    records = [record]

    # 2. Read embedded metadata
    try:
        record_with_meta = read_metadata(record)
        debugger.log("read_metadata", "metadata read from file", record_with_meta)
        records.append(record_with_meta)
    except Exception as e:
        errors.append(f"read_metadata: {e}")
        debugger.log("read_metadata_error", str(e), record)

    # 3. AI enrichment
    try:
        ai_provider = os.getenv("AI_PROVIDER")
        ai_record = enrich(record, ai_provider)
        debugger.log("ai_enrich", "AI metadata enrichment", ai_record)
        records.append(ai_record)
    except Exception as e:
        errors.append(f"ai_enrich: {e}")
        debugger.log("ai_enrich_error", str(e), record)

    # 4. Merge
    try:
        final_record = merge_book_records(records)
        debugger.log("merge", "merged metadata from all sources", final_record)
    except Exception as e:
        debugger.log("merge_error", str(e))
        return PipelineResult(False, errors=errors + [f"merge: {e}"])

    # 5. Write metadata
    write_result = write_metadata(final_record)
    if write_result.success:
        debugger.log("write_metadata", "metadata written to file", final_record)
    elif write_result.skipped:
        debugger.log("write_metadata", "metadata writing skipped", final_record)
    else:
        errors.extend(write_result.errors)
        debugger.log("write_metadata_error", "; ".join(write_result.errors), final_record)

    # 6. Rename
    try:
        template = os.environ.get("FILENAME_TEMPLATE")
        if not template:
            raise RuntimeError("FILENAME_TEMPLATE not set")

        filename = build_filename(final_record, template)
        filename = f"{filename}.{final_record.extension}"
        debugger.log("rename", f"filename built: {filename}", final_record)
    except Exception as e:
        debugger.log("rename_error", str(e), final_record)
        return PipelineResult(False, final_record, errors=errors + [f"rename: {e}"])

    # 7. Move
    try:
        target_dir = Path(os.environ.get("BOOKS_READY_DIR", "books_ready"))
        final_path = move_file(path, target_dir, filename)
        debugger.log("move", f"file moved to {final_path}", final_record)
    except Exception as e:
        debugger.log("move_error", str(e), final_record)
        return PipelineResult(False, final_record, errors=errors + [f"move: {e}"])

    return PipelineResult(
        success=len(errors) == 0,
        record=final_record,
        final_path=final_path,
        errors=errors,
    )
