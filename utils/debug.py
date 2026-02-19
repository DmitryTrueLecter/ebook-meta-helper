import json
import os
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from models.book import BookRecord


class Debugger:
    def __init__(self, source_path: Path):
        self.enabled = os.environ.get("DEBUG") == "1"
        if not self.enabled:
            return

        base_dir = Path(os.environ.get("DEBUG_DIR", "debug_logs"))
        base_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = source_path.name.replace(".", "_")

        self.log_path = base_dir / f"{safe_name}_{ts}.jsonl"

    def log(
        self,
        step: str,
        message: str,
        record: Optional[BookRecord] = None,
    ) -> None:
        if not self.enabled:
            return

        entry = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "message": message,
        }

        if record is not None:
            entry["record"] = asdict(record)

        def _json_default(obj):
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            return str(obj)

        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=_json_default) + "\n")