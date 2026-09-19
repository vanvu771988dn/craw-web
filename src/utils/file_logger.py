# src/utils/file_logger.py

import os
import datetime
import json
from src.database.models import ScrapedData

_CRAWL_EVENTS_PATH = os.path.join("data", "crawl_events.jsonl")


def log_crawl_results(final_html: str, scraped_data: ScrapedData):
    """
    Logs the raw HTML and the extracted data to files in the data/ directory.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    html_log_filename = os.path.join("data", f"crawl_html_{timestamp}.html")
    result_log_filename = os.path.join("data", f"crawl_result_{timestamp}.txt")
    
    with open(html_log_filename, "w", encoding="utf-8") as f:
        f.write(final_html)
        
    with open(result_log_filename, "w", encoding="utf-8") as f:
        f.write(str(scraped_data))
        
    print("----------------------")
    print(f"Logged HTML to {html_log_filename}")
    print(f"Logged result to {result_log_filename}")
    print("----------------------")


def clear_crawl_events() -> None:
    """Xóa sạch file crawl_events.jsonl khi bắt đầu một run mới.

    Chỉ giữ lại những tracker URL chưa resolve được từ run trước
    (được quản lý hoàn toàn bởi retry_failed_urls).
    Gọi hàm này một lần duy nhất ở đầu run_capture().
    """
    os.makedirs("data", exist_ok=True)
    # Truncate về 0 byte – nhanh hơn xóa rồi tạo lại
    with open(_CRAWL_EVENTS_PATH, "w", encoding="utf-8") as _f:
        pass
    print(f"[crawl_events] Log cleared -> {_CRAWL_EVENTS_PATH}")


def log_pending_tracker(tracker_url: str, league: str, timestamp: str) -> None:
    """Ghi một tracker URL chưa resolve được vào crawl_events.jsonl.

    Format đơn giản – chỉ 3 fields:
        {"tracker_url": "...", "league": "...", "timestamp": "..."}

    File này sẽ được retry_failed_urls.py đọc ra, resolve, và xóa dòng
    khi resolve thành công.
    """
    os.makedirs("data", exist_ok=True)
    payload = {
        "tracker_url": tracker_url,
        "league": league,
        "timestamp": str(timestamp),
    }
    with open(_CRAWL_EVENTS_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def log_debug_artifact(name: str, content: str) -> str:
    """Writes a debug artifact to the data directory and returns the file path."""
    os.makedirs("data", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    file_path = os.path.join("data", f"{name}_{timestamp}.html")
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(content)
    return file_path


def log_structured_event(stage: str, event_type: str, **kwargs) -> None:
    """
    Ghi log sự kiện có cấu trúc ra file JSONL.
    """
    os.makedirs("data", exist_ok=True)
    timestamp = datetime.datetime.now().isoformat()
    payload = {
        "timestamp": timestamp,
        "stage": stage,
        "event_type": event_type,
        **kwargs
    }
    with open(os.path.join("data", "structured_events.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
