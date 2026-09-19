# AI Web Crawler Product Requirements Document (PRD)

## Goals and Background Context

### Goals

*   Drastically decrease the developer time required to build and maintain web crawlers for complex sites.
*   Enable the rapid onboarding of new websites for data extraction without a linear increase in engineering resources.
*   Create a resilient crawling framework that is less susceptible to breaking when target website layouts change.

### Background Context

Traditional web scrapers are ill-equipped to handle modern, dynamic websites that rely on client-side JavaScript for navigation and content loading. They frequently fail when faced with common scenarios like timed redirects, cross-domain navigation, or interactive elements, leading to a high maintenance burden and slow development cycles.

This project aims to solve this problem by creating an intelligent, open-source crawling agent. By leveraging a powerful browser automation framework (`Crawl4AI`) and a local AI model (`Ollama`), the agent will be able to semantically understand and navigate these complex sites, extracting structured data reliably and adaptably.

### Change Log

| Date      | Version | Description        | Author     |
| --------- | ------- | ------------------ | ---------- |
| 2024-07-29  | 1.0     | Initial draft of PRD. | John (PM)  |
| 2025-08-25  | 2.0     | Added Phase 2 features: Intelligent Pagination and AI Content Enhancement. | John (PM)  |
| 2025-08-26  | 2.1     | Clarified pagination termination logic. | John (PM)  |


## Requirements

### Functional

1.  **FR1:** The system must accept a single starting URL, which points to a list-view page, as its initial input.
2.  **FR2:** The crawler must handle pages that automatically redirect to an external domain after a waiting period. The crawler will achieve this by pausing execution for a configured duration (e.g., 10 seconds) after the initial page load.
3.  **FR3:** The crawler must follow links that lead directly from the starting domain to an external domain.
4.  **FR4:** The crawler must be able to identify and click a specified button on a page to trigger a redirect to an external domain.
5.  **FR5:** The system must use an AI model (via `Crawl4AI` and `Ollama`) to extract the main content text and all image URLs from the final destination page.
6.  **FR6:** The data extracted by the AI must conform to a predefined Pydantic schema.
7.  **FR7:** Successfully extracted and structured data must be saved as a new record in a designated table within a local SQLite database.
8.  **FR8:** When a URL cannot be processed, the URL and a reason code (e.g., `TIMEOUT`, `MISSING_ELEMENT`, `BLOCKED`) must be saved as a new record in a designated error log table within the SQLite database.
9.  **FR9 (Pagination & Termination):** The crawler must handle "load more" buttons. For each link on a page, the crawler will check if the URL exists in the database. If it does, the entire crawl process will terminate immediately. The crawler will only click the "load more" button if all links on the current page are new.
10. **FR10 (AI Enhancement):** After extracting the main content from a page, the system will use a secondary AI call to rewrite and rephrase the text for improved clarity and readability.
11. **FR11 (Store Enhanced Content):** The new, simplified content from FR10 must be stored in the database in a new field (e.g., `enhanced_content`).

### Non-Functional

1.  **NFR1:** The entire crawling and AI data extraction process must run on a single local machine without reliance on external, paid cloud services or APIs.
2.  **NFR2:** The solution must be implemented using Python, the `Crawl4AI` library, and `Ollama`.
3.  **NFR3:** Key operational parameters, such as timeouts and element selectors for button clicks, must be configurable without changing the core application code.
4.  **NFR4:** The database implementation for the MVP must use SQLite.

## Technical Assumptions

#### Repository Structure: Monorepo

*   **Rationale:** For the MVP, a single repository (monorepo) is the simplest and most effective approach. It will contain the core crawler application, configuration files, and any future related components, making it easy to manage and deploy.

#### Service Architecture: Monolith

*   **Rationale:** The crawler is a single, self-contained application. A monolithic architecture is the most appropriate and efficient model. There is no current requirement for microservices or a serverless approach.

#### Testing Requirements: Unit + Integration

*   **Rationale:** To ensure reliability, we must have a solid testing strategy. This will include:
    *   **Unit Tests:** For individual functions, especially data transformation and database interactions.
    *   **Integration Tests:** For the end-to-end crawling and extraction process, likely using a mock website or a controlled live test environment.

#### Additional Technical Assumptions and Requests

*   **Language:** Python (version 3.10 or higher).
*   **Primary Framework:** `Crawl4AI` will be used for all browser automation, navigation, and AI extraction orchestration.
*   **AI Model Server:** `Ollama` will be used to serve the local LLM. The specific model (e.g., Llama 3, Mistral) will be configurable.
*   **Database:** SQLite will be used for all data and log storage in the MVP. The application will interact with the database using an appropriate Python library (e.g., `SQLAlchemy Core` or `sqlite3`).
*   **Data Validation:** Pydantic will be used to define the structure of the data to be extracted, ensuring all data saved to the database is clean and conforms to our schema.

## Epic List

*   **Epic 1: Core Crawler Engine with AI Extraction and SQL Persistence**
    *   **Goal:** To build and deliver a fully functional command-line web crawler that can navigate the three specified complex scenarios, extract structured data using a local AI model, and save the results and error logs to a local SQLite database.
*   **Epic 2: Intelligent Content Expansion & Enhancement**
    *   **Goal:** To enhance the crawler with intelligent pagination to handle "infinite scroll" pages and to add an AI-powered content simplification feature to improve the readability of the extracted text.

## Epic 1: Core Crawler Engine with AI Extraction and SQL Persistence

**Goal:** To build and deliver a fully functional command-line web crawler that can navigate the three specified complex scenarios, extract structured data using a local AI model, and save the results and error logs to a local SQLite database.

#### Story 1.1: Project Foundation and Environment Setup
*As a Developer, I want a well-defined project structure with all necessary dependencies installed, so that I can begin development efficiently.*

**Acceptance Criteria:**
1.  A `requirements.txt` file is created listing `crawl4ai[all]`, `pydantic`, and `sqlalchemy`.
2.  A basic directory structure (e.g., `src/`, `config/`, `data/`) is created.
3.  A configuration file (e.g., `config.yaml`) is created with placeholders for the start URL, timeouts, and the SQLite database path.
4.  A main entry point script (`main.py`) is created that can be executed without errors and can load the configuration.

#### Story 1.2: Database and Schema Initialization
*As a Developer, I want to define the data schemas and initialize the database, so that the application has a place to store extracted data and error logs.*

**Acceptance Criteria:**
1.  A Pydantic model is created defining the structure of the extracted data (e.g., `title: str`, `main_content: str`, `image_urls: List[str]`).
2.  A data structure is defined for the error log (e.g., `url: str`, `reason: str`, `timestamp: datetime`).
3.  A module is created that uses SQLAlchemy to generate the SQLite database file if it doesn't exist.
4.  The module creates two tables: `scraped_data` and `error_logs`, with columns that match the defined data structures.

#### Story 1.3: Basic Crawler Navigation to Start URL
*As a Crawler Agent, I want to navigate to the initial list-view URL, so that I can begin the crawling process.*

**Acceptance Criteria:**
1.  The application reads the start URL from the configuration file.
2.  The application uses `Crawl4AI` to launch a browser and navigate to the start URL.
3.  The application successfully retrieves and logs the title of the list-view page to confirm a successful connection.
4.  The application correctly handles and logs a basic navigation error (e.g., an invalid URL).

#### Story 1.4: Implement Complex Navigation Logic
*As a Crawler Agent, I want to handle different navigation patterns (direct links, timed redirects, button-click redirects), so that I can successfully reach the final content page.*

**Acceptance Criteria:**
1.  The crawler can successfully navigate to the final destination URL for all three specified scenarios.
2.  The logic for identifying the redirect button (e.g., by a CSS selector) is configurable.
3.  The waiting time for timed redirects is configurable.
4.  If navigation for a specific link fails, the URL and reason are logged to the `error_logs` table in the SQLite database.

#### Story 1.5: AI-Powered Data Extraction from Destination Page
*As a Crawler Agent, I want to use a local AI model to extract content and images from a destination page, so that I can gather the required data in a structured format.*

**Acceptance Criteria:**
1.  The application configures `Crawl4AI`'s `LLMExtractionStrategy` to connect to a local `Ollama` provider.
2.  The strategy is provided with the Pydantic schema defined in Story 1.2.
3.  Given the HTML of a destination page, the agent successfully populates the Pydantic model with the extracted data.
4.  The populated Pydantic model is logged to the console for verification.

#### Story 1.6: Persist Extracted Data to SQLite
*As a Crawler Agent, I want to save the structured data extracted by the AI into the SQLite database, so that the data is permanently stored for later use.*

**Acceptance Criteria:**
1.  After the AI successfully populates the Pydantic model, the application connects to the SQLite database.
2.  A new record is inserted into the `scraped_data` table.
3.  The data in the newly inserted record correctly matches the data from the Pydantic model.
4.  The application logs a success message indicating that the record has been saved.

## Epic 2: Intelligent Content Expansion & Enhancement

**Goal:** To enhance the crawler with intelligent pagination to handle "infinite scroll" pages and to add an AI-powered content simplification feature to improve the readability of the extracted text.

#### Story 2.1: Implement "Load More" Pagination with URL-Based Termination
*As a Crawler Agent, I want to repeatedly click a 'load more' button to reveal more content, but stop immediately if I encounter an article I've already saved, so that I can efficiently gather all new content.*

**Acceptance Criteria:**
1. The CSS selector for the "load more" button is configurable.
2. The crawler enters a loop, clicking the "load more" button at the end of each cycle.
3. In each loop, the crawler checks every article link's URL against the database.
4. If a URL is found that already exists in the database, the entire crawl process stops immediately and logs a "Crawl complete" message.
5. If the "load more" button cannot be found, the crawl process stops and logs a "Crawl complete" message.

#### Story 2.2: AI-Powered Content Simplification
*As a Data Consumer, I want the extracted article text to be simplified and rephrased for clarity, so that the main points are easier to understand.*

**Acceptance Criteria:**
1. After the main content is extracted, a new AI call is made with a prompt to simplify the text.
2. The `ScrapedData` model and the `scraped_data` database table are updated with a new `enhanced_content` text field.
3. The simplified text returned by the AI is saved in the `enhanced_content` field for the corresponding record.
4. The process handles failures in the simplification step gracefully (e.g., by saving the original content as a fallback) and logs a warning.
