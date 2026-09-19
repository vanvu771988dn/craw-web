import asyncio
from src.utils.config_loader import load_config
from src.database.persistence import get_db_instance
from src.core.crawler import run_crawl

def main():
    print("Crawler application starting...")
    config = load_config()
    db_path = config.get("database", {}).get("path", "data/crawler.db")
    
    # Initialize the database using the singleton instance
    db_instance = get_db_instance(db_path)
    db_instance.init_database()
    print("Database initialized.")

    print("Initializing crawler...")
    try:
        asyncio.run(run_crawl(config))
    except KeyboardInterrupt:
        print("\nCrawl interrupted by user. Exiting gracefully.")
    finally:
        print("Crawl complete.")

if __name__ == "__main__":
    main()
