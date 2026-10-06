# Book Research & Gap Analyzer MCP Server

A unified Model Context Protocol (MCP) server and REST API designed to automate book market research, map topic saturation, detect competitor white spaces, and formulate winning book concepts using the **Google Books API**.

This server provides a **dual-interface architecture**:
1. **Remote MCP (SSE & Streamable JSON-RPC 2.0)**: Connects natively to **Gemini Spark**, Claude, or any standard Remote MCP client.
2. **REST API / OpenAPI Engine**: Exposes a standard OpenAPI schema (`/openapi.json`) that can be imported directly into **ChatGPT Custom Actions (GPT Builder)**.

---

## Key Features & Tools

The server exposes 7 specialized tools structured as an end-to-end research pipeline:

1. **`search_books`**: Automated multi-query expansion and smart deduplication based on ISBN-10/13 and Google Books Volume IDs.
2. **`search_books_advanced`**: High-precision bibliographic search using native field operators (`intitle:`, `inauthor:`, `inpublisher:`, `subject:`, `isbn:`).
3. **`get_book_detail`**: Deep metadata inspection for individual volumes (descriptions, categories, page counts, preview availability, publisher info).
4. **`build_book_landscape`**: Clusters existing books into thematic segments and evaluates market saturation levels (from Very Low to Saturated).
5. **`extract_topics`**: NLP-driven frequency extraction that constructs a comprehensive **Topic-by-Book Coverage Matrix**.
6. **`find_book_gaps`**: Quantitative gap detection across 4 critical strategic dimensions:
   * **Geographic & Local Context Gap** (local vs. global market focus)
   * **Practical Actionability Gap** (actionable SOPs/workflows vs. theoretical overviews)
   * **Audience & Demographics Gap** (non-technical beginners / 40+ vs. tech-savvy specialists)
   * **Tool Ecosystem Synergy Gap** (multi-tool workflows vs. single-tool silos)
7. **`generate_book_opportunities`**: Synthesizes 3 distinct, defensible book concept proposals complete with working titles, positioning statements, primary/secondary audience profiles, 6-chapter outlines, and competitive scores.

---

## Repository Structure
