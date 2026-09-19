# src/database/persistence.py
import json
import sqlalchemy
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, Float, select, insert, or_, inspect, text, desc
from src.database.models import ScrapedData, ErrorLog
import datetime

class Database:
    """Handles all database interactions for the web crawler."""
    
    def __init__(self, db_path: str):
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.metadata = MetaData()
        self._define_tables()

    def _define_tables(self):
        """Defines the database schema."""
        self.scraped_data = Table(
            "scraped_data", self.metadata,
            Column("id", Integer, primary_key=True),
            Column("canonical_url", String, index=True),
            Column("title", String),
            Column("author", String),
            Column("url", String, index=True, unique=True),
            Column("tracker_url", String, index=True),
            Column("tracker_article_id", String, index=True),
            Column("final_url", String, index=True),
            Column("list_page_url", String),
            Column("grid_title", String),
            Column("grid_source", String),
            Column("grid_time_text", String),
            Column("grid_position", Integer),
            Column("redirect_delay_ms", Integer),
            Column("manual_redirect", Integer),
            Column("tracker_og_title", String),
            Column("tracker_og_image", String),
            Column("published_at", DateTime),
            Column("updated_at", DateTime),
            Column("source_site", String),
            Column("top_image_url", String),
            Column("normalized_title", String, index=True),
            Column("content_fingerprint", String, index=True),
            Column("duplicate_status", String, index=True),
            Column("duplicate_of", Integer, index=True),
            Column("story_cluster_id", String, index=True),
            Column("similarity_score", Float),
            Column("main_content", String),
            Column("crawled_at", DateTime),
        )
        self.error_logs = Table(
            "error_logs", self.metadata,
            Column("id", Integer, primary_key=True),
            Column("url", String),
            Column("stage", String),
            Column("code", String),
            Column("reason", String),
            Column("context", String),
            Column("timestamp", DateTime),
        )

    def init_database(self):
        """Creates the database and tables if they don't exist."""
        self.metadata.create_all(self.engine)
        self._ensure_optional_columns()

    def _ensure_optional_columns(self):
        """Adds newly introduced columns to existing SQLite tables when needed."""
        inspector = inspect(self.engine)
        existing_columns = {column["name"] for column in inspector.get_columns("scraped_data")}
        required_columns = {
            "canonical_url": "ALTER TABLE scraped_data ADD COLUMN canonical_url VARCHAR",
            "author": "ALTER TABLE scraped_data ADD COLUMN author VARCHAR",
            "tracker_url": "ALTER TABLE scraped_data ADD COLUMN tracker_url VARCHAR",
            "tracker_article_id": "ALTER TABLE scraped_data ADD COLUMN tracker_article_id VARCHAR",
            "final_url": "ALTER TABLE scraped_data ADD COLUMN final_url VARCHAR",
            "list_page_url": "ALTER TABLE scraped_data ADD COLUMN list_page_url VARCHAR",
            "grid_title": "ALTER TABLE scraped_data ADD COLUMN grid_title VARCHAR",
            "grid_source": "ALTER TABLE scraped_data ADD COLUMN grid_source VARCHAR",
            "grid_time_text": "ALTER TABLE scraped_data ADD COLUMN grid_time_text VARCHAR",
            "grid_position": "ALTER TABLE scraped_data ADD COLUMN grid_position INTEGER",
            "redirect_delay_ms": "ALTER TABLE scraped_data ADD COLUMN redirect_delay_ms INTEGER",
            "manual_redirect": "ALTER TABLE scraped_data ADD COLUMN manual_redirect INTEGER",
            "tracker_og_title": "ALTER TABLE scraped_data ADD COLUMN tracker_og_title VARCHAR",
            "tracker_og_image": "ALTER TABLE scraped_data ADD COLUMN tracker_og_image VARCHAR",
            "published_at": "ALTER TABLE scraped_data ADD COLUMN published_at DATETIME",
            "updated_at": "ALTER TABLE scraped_data ADD COLUMN updated_at DATETIME",
            "source_site": "ALTER TABLE scraped_data ADD COLUMN source_site VARCHAR",
            "top_image_url": "ALTER TABLE scraped_data ADD COLUMN top_image_url VARCHAR",
            "normalized_title": "ALTER TABLE scraped_data ADD COLUMN normalized_title VARCHAR",
            "content_fingerprint": "ALTER TABLE scraped_data ADD COLUMN content_fingerprint VARCHAR",
            "duplicate_status": "ALTER TABLE scraped_data ADD COLUMN duplicate_status VARCHAR DEFAULT 'unique'",
            "duplicate_of": "ALTER TABLE scraped_data ADD COLUMN duplicate_of INTEGER",
            "story_cluster_id": "ALTER TABLE scraped_data ADD COLUMN story_cluster_id VARCHAR",
            "similarity_score": "ALTER TABLE scraped_data ADD COLUMN similarity_score FLOAT",
        }
        error_log_required_columns = {
            "stage": "ALTER TABLE error_logs ADD COLUMN stage VARCHAR",
            "code": "ALTER TABLE error_logs ADD COLUMN code VARCHAR",
            "context": "ALTER TABLE error_logs ADD COLUMN context VARCHAR",
        }

        with self.engine.connect() as connection:
            for column_name, alter_sql in required_columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(alter_sql))
            existing_error_columns = {column["name"] for column in inspector.get_columns("error_logs")}
            for column_name, alter_sql in error_log_required_columns.items():
                if column_name not in existing_error_columns:
                    connection.execute(text(alter_sql))
            connection.commit()

    def save_scraped_data(self, data: ScrapedData):
        """Saves a ScrapedData object to the database."""
        stmt = insert(self.scraped_data).values(
            canonical_url=data.canonical_url,
            title=data.title,
            author=data.author,
            url=data.url,
            tracker_url=data.tracker_url,
            tracker_article_id=data.tracker_article_id,
            final_url=data.final_url,
            list_page_url=data.list_page_url,
            grid_title=data.grid_title,
            grid_source=data.grid_source,
            grid_time_text=data.grid_time_text,
            grid_position=data.grid_position,
            redirect_delay_ms=data.redirect_delay_ms,
            manual_redirect=1 if data.manual_redirect is True else 0 if data.manual_redirect is False else None,
            tracker_og_title=data.tracker_og_title,
            tracker_og_image=data.tracker_og_image,
            published_at=data.published_at,
            updated_at=data.updated_at,
            source_site=data.source_site,
            top_image_url=data.top_image_url,
            normalized_title=data.normalized_title,
            content_fingerprint=data.content_fingerprint,
            duplicate_status=data.duplicate_status,
            duplicate_of=data.duplicate_of,
            story_cluster_id=data.story_cluster_id,
            similarity_score=data.similarity_score,
            main_content=data.main_content,
            crawled_at=data.crawled_at,
        )
        with self.engine.connect() as connection:
            connection.execute(stmt)
            connection.commit()

    def url_exists(self, url: str) -> bool:
        """Checks if a URL already exists in the scraped_data table."""
        stmt = select(self.scraped_data).where(
            or_(
                self.scraped_data.c.url == url,
                self.scraped_data.c.final_url == url,
                self.scraped_data.c.tracker_url == url,
            )
        )
        with self.engine.connect() as connection:
            result = connection.execute(stmt).fetchone()
            return result is not None

    def article_exists(
        self,
        tracker_url: str | None = None,
        final_url: str | None = None,
        canonical_url: str | None = None,
        tracker_article_id: str | None = None,
        content_fingerprint: str | None = None,
        normalized_title: str | None = None,
    ) -> bool:
        """Checks whether an article is already present by the strongest known identity fields."""
        predicates = []
        if tracker_url:
            predicates.append(self.scraped_data.c.tracker_url == tracker_url)
        if canonical_url:
            predicates.append(self.scraped_data.c.canonical_url == canonical_url)
        if tracker_article_id:
            predicates.append(self.scraped_data.c.tracker_article_id == tracker_article_id)
        if final_url:
            predicates.append(self.scraped_data.c.final_url == final_url)
            predicates.append(self.scraped_data.c.url == final_url)
        if content_fingerprint:
            predicates.append(self.scraped_data.c.content_fingerprint == content_fingerprint)
        if normalized_title:
            predicates.append(self.scraped_data.c.normalized_title == normalized_title)

        if not predicates:
            return False

        stmt = select(self.scraped_data.c.id).where(or_(*predicates)).limit(1)
        with self.engine.connect() as connection:
            result = connection.execute(stmt).fetchone()
            return result is not None

    def find_existing_article(self, data: ScrapedData) -> tuple[int | None, str | None]:
        """Returns the strongest exact-identity duplicate match in priority order."""
        checks = (
            ("canonical_url", data.canonical_url, self.scraped_data.c.canonical_url),
            ("url", data.url, self.scraped_data.c.url),
            ("final_url", data.final_url, self.scraped_data.c.final_url),
            ("content_fingerprint", data.content_fingerprint, self.scraped_data.c.content_fingerprint),
            ("tracker_article_id", data.tracker_article_id, self.scraped_data.c.tracker_article_id),
            ("tracker_url", data.tracker_url, self.scraped_data.c.tracker_url),
        )
        with self.engine.connect() as connection:
            for reason, value, column in checks:
                if not value:
                    continue
                stmt = select(self.scraped_data.c.id).where(column == value).limit(1)
                row = connection.execute(stmt).fetchone()
                if row:
                    return row[0], reason
        return None, None

    def list_recent_articles(self, limit: int = 200) -> list[dict]:
        stmt = (
            select(self.scraped_data)
            .order_by(desc(self.scraped_data.c.crawled_at), desc(self.scraped_data.c.id))
            .limit(limit)
        )
        with self.engine.connect() as connection:
            rows = connection.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    def list_failed_items(self, limit: int = 100, stage: str | None = None) -> list[dict]:
        stmt = select(self.error_logs)
        if stage:
            stmt = stmt.where(self.error_logs.c.stage == stage)
        stmt = stmt.order_by(desc(self.error_logs.c.timestamp), desc(self.error_logs.c.id)).limit(limit)
        with self.engine.connect() as connection:
            rows = connection.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    def log_error(
        self,
        url: str,
        reason: str,
        stage: str | None = None,
        code: str | None = None,
        context: str | None = None,
    ):
        """Logs a crawling error to the database."""
        serialized_context = None
        if context:
            serialized_context = context if isinstance(context, str) else json.dumps(context, ensure_ascii=False)

        error = ErrorLog(
            url=url,
            reason=reason,
            stage=stage,
            code=code,
            context=serialized_context,
            timestamp=datetime.datetime.now(),
        )
        stmt = insert(self.error_logs).values(
            url=error.url,
            stage=error.stage,
            code=error.code,
            reason=error.reason,
            context=error.context,
            timestamp=error.timestamp
        )
        with self.engine.connect() as connection:
            connection.execute(stmt)
            connection.commit()

# --- Singleton Instance ---
# This approach ensures that other parts of the app can easily get a database
# connection without needing to manage the config path everywhere.
_db_instance = None

def get_db_instance(db_path: str = None) -> Database:
    """Initializes and returns the singleton Database instance."""
    global _db_instance
    if _db_instance is None:
        if db_path is None:
            raise ValueError("Database path must be provided for the first initialization.")
        _db_instance = Database(db_path)
    return _db_instance
