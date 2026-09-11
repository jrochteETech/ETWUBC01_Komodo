import csv
import re
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox

OUTPUT_COLS = ["Path", "Tag Type", "AlarmIndex", "AlarmName", "Priority", "Mode", "SetpointA", "Enabled", "RawAlarm",]

_FIELD_PATTERNS: dict[str, re.Pattern] = {
    "AlarmName": re.compile(r"""['"']?name['"']?\s*:\s*['"']?(?P<val>[^,}'"]+)['"']?""", re.IGNORECASE),
    "Priority":  re.compile(r"""['"']?priority['"']?\s*:\s*['"']?(?P<val>[^,}'"]+)['"']?""", re.IGNORECASE),
    "Mode":      re.compile(r"""['"']?mode['"']?\s*:\s*['"']?(?P<val>[^,}'"]+)['"']?""", re.IGNORECASE),
    "SetpointA": re.compile(r"""['"']?setpointA['"']?\s*:\s*['"']?(?P<val>[^,}'"]+)['"']?""", re.IGNORECASE),
    "Enabled":   re.compile(r"""['"']?enabled['"']?\s*:\s*['"']?(?P<val>[^,}'"]+)['"']?""", re.IGNORECASE),
}

_FIELD_DEFAULTS: dict[str, str] = {
    "AlarmName":  "",
    "Priority":   "Low",
    "Mode":       "Equal",
    "SetpointA":  "0",
    "Enabled":    "True",
}


def pick_input_file() -> Path:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = filedialog.askopenfilename(
        title="Select a CSV file to split",
        filetypes=[
            ("CSV files", "*.csv"),
            ("All files", "*.*"),
        ],
    )

    root.destroy()

    if not file_path:
        messagebox.showwarning("No file selected", "No file was selected. Exiting.")
        sys.exit(0)

    return Path(file_path)


def split_alarm_blocks(s: str) -> list[str]:
    if not isinstance(s, str):
        return []
    s = s.strip()
    if not s or s == "[]":
        return []

    first_brace = s.find("{")
    if first_brace == -1:
        return []

    blocks: list[str] = []
    depth       = 0
    in_quote    = False
    quote_char  = ""
    escape_next = False
    start_idx   = None

    for i in range(first_brace, len(s)):
        ch = s[i]

        if in_quote:
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == quote_char:
                in_quote = False
            continue

        if ch in ('"', "'"):
            in_quote   = True
            quote_char = ch
            continue

        if ch == "{":
            if depth == 0:
                start_idx = i
            depth += 1

        elif ch == "}":
            depth -= 1
            if depth == 0 and start_idx is not None:
                blocks.append(s[start_idx : i + 1])
                start_idx = None

    return blocks


def _clean_val(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    v = v.strip("'\"")
    v = v.strip()
    return v


def extract_fields(raw_alarm: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for field, pattern in _FIELD_PATTERNS.items():
        match = pattern.search(raw_alarm)
        # Store None explicitly when the field is missing — this is what
        # allows _FIELD_DEFAULTS to work correctly via `or` below.
        out[field] = _clean_val(match.group("val")) if match else None
    return out


def process_file(input_path: Path, output_path: Path) -> None:
    try:
        df = pd.read_csv(
            input_path,
            engine="python",
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:
        sys.exit(f"ERROR: Could not read CSV: {exc}")

    required = ["Path", "Tag Type", "Alarms"]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        sys.exit(f"ERROR: Missing required column(s): {missing}")

    rows_out: list[dict] = []
    tags_with_alarms = 0

    for row in df.itertuples(index=False):
        path = getattr(row, "Path", "")
        tag_type = getattr(row, "Tag Type", "")
        alarms_str = getattr(row, "Alarms", "")

        blocks = split_alarm_blocks(alarms_str)
        if blocks:
            tags_with_alarms += 1

        for idx, block in enumerate(blocks):
            fld = extract_fields(block)
            rows_out.append({
                "Path": path,
                "Tag Type": tag_type,
                "AlarmIndex": idx,
                "AlarmName": fld["AlarmName"] or _FIELD_DEFAULTS["AlarmName"],
                "Priority": fld["Priority"] or _FIELD_DEFAULTS["Priority"],
                "Mode": fld["Mode"] or _FIELD_DEFAULTS["Mode"],
                "SetpointA": fld["SetpointA"] or _FIELD_DEFAULTS["SetpointA"],
                "Enabled": fld["Enabled"] or _FIELD_DEFAULTS["Enabled"],
                "RawAlarm": block,
            })

    out_df = pd.DataFrame(rows_out, columns=OUTPUT_COLS)
    try:
        out_df.to_csv(output_path, index=False, quoting=csv.QUOTE_MINIMAL)
    except Exception as exc:
        sys.exit(f"ERROR: Could not write output CSV: {exc}")

    total_tags    = len(df)
    total_alarms  = len(rows_out)
    print("====== Summary ======")
    print(f"Input file           : {input_path}")
    print(f"Output file          : {output_path}")
    print(f"Total tags           : {total_tags:,}")
    print(f"Tags with alarms     : {tags_with_alarms:,}")
    print(f"Tags without alarms  : {total_tags - tags_with_alarms:,}")
    print(f"Total alarms (rows)  : {total_alarms:,}")


if __name__ == "__main__":
    timestamp   = datetime.now().strftime("%Y%m%dT%H%M%S")
    input_file = pick_input_file()
    print(input_file)
    input_filename = str(input_file).rsplit("\\")[-1].replace(".csv","")
    output_path = Path(f"{input_filename}_allAlarms_{timestamp}.csv")

    process_file(input_file, output_path)