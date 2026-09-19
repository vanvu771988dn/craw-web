# src/utils/ai_utils.py

import json
import datetime
from crawl4ai import AsyncWebCrawler, LLMExtractionStrategy, LLMConfig, CrawlerRunConfig
from pydantic import BaseModel
from src.database.models import ScrapedData
from src.core.instruction.extract_content_html import EXTRACTION_INSTRUCTION, EXTRACTION_INSTRUCTION_WITH_TITLE

class AIExtractedArticle(BaseModel):
    title: str | None = None
    author: str | None = None
    published_at: datetime.datetime | None = None
    top_image_url: str | None = None
    main_content: str = ""

def _parse_and_validate_data(extracted_content: str) -> list[ScrapedData]:
    """Parses the JSON string from the AI and validates it against the ScrapedData model."""
    try:
        data = json.loads(extracted_content)
        
        if isinstance(data, list) and data:
            # Handle cases where the AI returns a list of objects
            validated_data = [AIExtractedArticle.model_validate(item.get("data", item)) for item in data]
            return [ScrapedData(**item.model_dump()) for item in validated_data if item]
        
        if isinstance(data, dict):
            # Handle cases where the AI returns a single object
            validated = AIExtractedArticle.model_validate(data)
            return [ScrapedData(**validated.model_dump())]
            
        raise ValueError("Extracted content is not in a valid format (list of objects or single object).")
        
    except (json.JSONDecodeError, ValueError) as e:
        raise Exception(f"Failed to parse or validate AI-extracted content: {e}")

async def extract_content_with_ai(crawler: AsyncWebCrawler, cleaned_html: str, config: dict, title_to_find: str | None = None) -> list[ScrapedData]:
    """Configures and runs the AI extraction process, using a title to target content if provided."""
    model_name = config.get("ollama", {}).get("model", "llama3")
    llm_provider = f"ollama/{model_name}"
    
    print(f"Using title_to_find: {title_to_find}")
    # Choose the prompt based on whether a title is available for targeting
    if title_to_find:
        instruction = EXTRACTION_INSTRUCTION_WITH_TITLE.format(title=title_to_find)
        print(f"Using title-based extraction to find: '{title_to_find}'")
    else:
        instruction = EXTRACTION_INSTRUCTION

    extraction_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(provider=llm_provider),
        schema=AIExtractedArticle.model_json_schema(),
        instruction=instruction
    )
    
    run_config = CrawlerRunConfig(
        extraction_strategy=extraction_strategy,
        remove_overlay_elements=True
    )
    
    result = await crawler.arun(url=f"raw:{cleaned_html}", config=run_config)

    if result.success and result.extracted_content:
        return _parse_and_validate_data(result.extracted_content)
    
    raise Exception(result.error_message or "AI extraction failed to produce content.")

