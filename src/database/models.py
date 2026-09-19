from typing import Optional
from pydantic import BaseModel, Field
import datetime

class ScrapedData(BaseModel):
    canonical_url: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    url: Optional[str] = None
    tracker_url: Optional[str] = None
    tracker_article_id: Optional[str] = None
    final_url: Optional[str] = None
    list_page_url: Optional[str] = None
    grid_title: Optional[str] = None
    grid_source: Optional[str] = None
    grid_time_text: Optional[str] = None
    grid_position: Optional[int] = None
    redirect_delay_ms: Optional[int] = None
    manual_redirect: Optional[bool] = None
    tracker_og_title: Optional[str] = None
    tracker_og_image: Optional[str] = None
    published_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    source_site: Optional[str] = None
    top_image_url: Optional[str] = None
    normalized_title: Optional[str] = None
    content_fingerprint: Optional[str] = None
    duplicate_status: str = "unique"
    duplicate_of: Optional[int] = None
    story_cluster_id: Optional[str] = None
    similarity_score: Optional[float] = None
    main_content: str = ""
    crawled_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

class ErrorLog(BaseModel):
    url: str # HttpUrl validation might fail for non-standard URLs
    reason: str
    stage: Optional[str] = None
    code: Optional[str] = None
    context: Optional[str] = None
    timestamp: datetime.datetime
