import pandas as pd
import math
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime

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


def split_csv(input_path: Path, rows_per_file: int) -> None:
    df = pd.read_csv(
        input_path,
        engine="python",
        dtype=str,
        keep_default_na=False,
    )

    total_rows = len(df)
    num_files  = math.ceil(total_rows / rows_per_file)
    timestamp  = datetime.now().strftime("%Y%m%dT%H%M%S")
    stem       = input_path.stem
    output_folder = input_path.parent / "{}_split_{}".format(stem, timestamp)
    output_folder.mkdir(parents=True, exist_ok=True)

    print("Total rows     : {:,}".format(total_rows))
    print("Rows per file  : {:,}".format(rows_per_file))
    print("Files to create: {}".format(num_files))
    print("Output folder  : {}".format(output_folder))
    print()

    for i in range(num_files):
        start    = i * rows_per_file
        end      = start + rows_per_file  # pandas iloc will clamp this safely
        chunk    = df.iloc[start:end]

        out_path = output_folder / "{}_part{}of{}_{}.csv".format(
            stem, i + 1, num_files, timestamp
        )

        chunk.to_csv(out_path, index=False)

        print("  Written: {}  ({:,} rows)".format(out_path.name, len(chunk)))

    print("\nDone. {} files created in: {}".format(num_files, output_folder))


ROWS_PER_FILE = 1000

if __name__ == "__main__":
    input_file = pick_input_file()
    split_csv(input_file, ROWS_PER_FILE)