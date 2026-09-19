# Project Brief: AI Web Crawler

## Executive Summary

This project will create an intelligent web crawling agent designed to extract content and images from websites with complex, dynamic navigation. The primary problem it solves is the failure of traditional scrapers to handle modern web applications that feature delayed redirects, cross-domain navigation, and client-side interactions. The initial target is list-view websites, with a flexible architecture to support various website behaviors in the future. The key value proposition is a resilient, AI-driven data extraction engine that is adaptable, cost-effective (by using local, open-source models), and capable of delivering structured data from challenging web environments.

## Problem Statement

Traditional web crawlers and scrapers are often brittle and ineffective when faced with modern, dynamic websites. They typically fail when content is not immediately available in the initial HTML payload. The specific pain points this project addresses are:

*   **Complex Navigation Paths:** Many websites, especially those aggregating links (e.g., deal sites, news aggregators), do not link directly to the final content. Instead, they use intermediate pages that may involve timers, redirects, or require user interaction (like clicking a button) to proceed. Static crawlers cannot navigate these paths.
*   **Dynamic Content Loading:** Content, images, and interactive elements (like buttons) are often loaded asynchronously with JavaScript. A scraper that only reads the initial HTML will miss this critical information.
*   **High Maintenance Overhead:** When a website changes its layout, traditional scrapers with rigid selectors (like XPath or CSS selectors) break, requiring constant and time-consuming manual updates.
*   **Scalability Issues:** Manually adapting a scraper for each new target website's unique structure is inefficient and does not scale.

Existing solutions are often either too simplistic to handle these challenges or are expensive enterprise-grade platforms. There is a clear need for an open-source, adaptable solution that can intelligently navigate and extract data from these complex web environments.

## Proposed Solution

We propose the development of an intelligent, AI-driven web crawling framework built on a modern, open-source technology stack. The core of the solution is a flexible agent capable of both robust browser automation and intelligent data extraction.

*   **Core Concept:** The solution will be a Python-based application that uses the `Crawl4AI` framework to manage all crawling and browser interaction logic. For data extraction, it will integrate with a locally-run Large Language Model (LLM) served via `Ollama`. This combination allows the agent to perceive a web page's content and structure semantically, rather than relying on brittle HTML selectors.

*   **Key Differentiators:**
    *   **All-in-One Framework:** Unlike solutions that require cobbling together separate browser automation and AI libraries, `Crawl4AI` provides a single, cohesive framework designed for this exact purpose, including built-in features for stealth, caching, and multi-page navigation.
    *   **Cost-Free Intelligence:** By leveraging local, open-source LLMs via `Ollama`, the solution avoids expensive API calls and keeps all data processing local and private.
    *   **Adaptability by Design:** Instead of writing site-specific scraping code, we will define data requirements using Pydantic schemas. The LLM will be responsible for populating these schemas, allowing the same agent to work across different site layouts with minimal to no modification.

*   **Vision:** The high-level vision is to create a "set-and-forget" crawler that a user can point at a new list-view website. The agent will autonomously handle the navigation complexities and reliably extract the desired content and images into a clean, structured format, regardless of the underlying website's design.

## Target Users

#### Primary User Segment: Data Engineers & Developers

*   **Profile:** Technical professionals responsible for building and maintaining data pipelines, integrating third-party data into internal systems, or conducting data analysis. They are comfortable with coding, particularly in Python, and are familiar with concepts like APIs, data schemas, and automation.
*   **Current Behaviors:** They currently write and maintain custom web scrapers using libraries like BeautifulSoup, Scrapy, or Selenium. A significant portion of their time is spent debugging broken scrapers when websites change and adapting code for new data sources.
*   **Pain Points:**
    *   **High Maintenance Burden:** Their existing tools are brittle and require constant updates.
    *   **Slow Development Cycle:** Building a reliable scraper for a complex, dynamic website can take days or weeks.
    *   **Inability to Scale:** The manual effort required for each new site makes it difficult to expand their data collection efforts.
*   **Goals:** They want to acquire structured, reliable data from the web with minimal manual intervention. Their goal is to build robust, scalable, and low-maintenance data pipelines so they can focus on using the data, not just acquiring it.

## Goals & Success Metrics

#### Business Objectives

*   **Reduce Manual Effort:** Drastically decrease the developer time required to build and maintain web crawlers for complex sites.
*   **Increase Scalability:** Enable the rapid onboarding of new websites for data extraction without a linear increase in engineering resources.
*   **Improve Data Reliability:** Create a resilient crawling framework that is less susceptible to breaking when target website layouts change.

#### User Success Metrics

*   A developer can successfully configure the crawler for a new, complex website in hours, not days.
*   The crawler can run for an extended period (e.g., a full week) and successfully extract data without requiring human intervention or code changes.
*   The data extraction schema (e.g., the specific fields to be captured) can be modified without altering the core crawling and navigation logic.

#### Key Performance Indicators (KPIs)

*   **Crawler Success Rate:** (Successfully processed URLs / Total attempted URLs) x 100. **Target: >95%** (excluding URLs that are permanently unavailable or intentionally block crawling).
*   **New Site Onboarding Time:** The average time it takes for a developer to configure the crawler to get structured data from a new target website. **Target: < 3 hours.**
*   **Maintenance Interventions per Month:** The number of times a developer must modify the code to fix a crawl that failed due to a website layout change. **Target: 0.**

## MVP Scope

#### Core Features (Must Have)

*   **Configurable Starting Point:** The crawler must be initializable with a single starting URL (the list-view page).
*   **Complex Navigation Handler:** The core logic must successfully handle the three specified navigation scenarios:
    1.  Same-domain page with a timed redirect. The crawler will explicitly wait for a configured period (e.g., 10 seconds) to allow client-side redirects to complete.
    2.  Direct link to a different domain.
    3.  Same-domain page requiring a button click to redirect.
*   **AI-Powered Data Extraction:** The system must use `Crawl4AI`'s `LLMExtractionStrategy` connected to a local `Ollama` model to extract the main content text and all relevant image URLs from the final destination page.
*   **Structured Data Output:** A Pydantic schema will define the desired output structure (e.g., `title`, `main_content`, `image_urls`).
*   **Persistent SQL Storage:** The extracted structured data must be saved into a local **SQLite database**. The schema of the database table will directly mirror the Pydantic schema.
*   **Robust Logging:** Implement the "log and give up" strategy. The crawler must log failed URLs to a separate table in the **SQLite database** with a clear reason for the failure (e.g., `TIMEOUT`, `MISSING_ELEMENT`, `BLOCKED`).

#### Out of Scope for MVP

*   **Automatic Retry Logic:** The MVP will not automatically retry URLs that fail.
*   **Advanced Anti-Bot Circumvention:** Beyond `Crawl4AI`'s built-in stealth mode, no advanced techniques will be implemented.
*   **Support for other databases:** The MVP will only support SQLite. PostgreSQL, MySQL, etc., are out of scope.
*   **Web UI or Dashboard:** All interaction will be via the command line.
*   **Distributed Crawling:** The crawler will run as a single process on a single machine.

#### MVP Success Criteria

The MVP will be considered a success when we can point it at a target list-view website and it demonstrably:
1.  Navigates through all three of the defined complex redirect scenarios.
2.  Extracts the desired content and images from the resulting destination pages.
3.  **Saves the structured data correctly into a local SQLite database.**
4.  **Correctly logs any failed URLs to the database.**
