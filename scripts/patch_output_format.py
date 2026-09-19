"""Patch write_output_txt to output plain URLs only."""

path = "src/url_capture.py"
content = open(path, encoding="utf-8").read()

# Find and replace the write_output_txt function
start_marker = "\ndef write_output_txt("
end_marker = "\n    print(f\"\\n[SUCCESS] Output written -> {out_file}  ({len(records)} URLs)\")\n"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f"ERROR: markers not found. start={start_idx}, end={end_idx}")
else:
    end_idx += len(end_marker)
    new_func = """
def write_output_txt(
    out_file: Path,
    records: list[dict],
    sources: list[dict],
    time_window_hours: float,
    cursor: dict,
) -> None:
    valid_records = [r for r in records if r.get("final_url")]

    with open(out_file, "w", encoding="utf-8") as fh:
        for rec in valid_records:
            fh.write(rec["final_url"] + "\\n")

    print(f"\\n[SUCCESS] Output written -> {out_file}  ({len(valid_records)} URLs)")
"""
    new_content = content[:start_idx] + new_func + content[end_idx:]
    open(path, "w", encoding="utf-8").write(new_content)
    print("Done! write_output_txt updated.")
    print(f"New file size: {len(new_content)} chars")
