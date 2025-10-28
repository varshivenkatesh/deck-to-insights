# Deck to Insights - Automated Pitch Deck Analyzer

This project was developed as part of a **technical round assessment**.  
It is an **AI-powered due diligence pipeline** that takes a startup's **pitch deck (PDF/PPT)**, performs **web research**, validates **key claims**, and generates a **structured investment report** for early-stage investors.

Note: Developed my first agent! And first ever multi-agent orchestrated pipeline. Pulled an all-nighter for this because it was too interesting, spent a lot of time navigating through a couple challenges with agent prompting, 202 site blockage errors (which I did not realize was due to iteratively testing my web scrapers) and I could NOT find any startup pitch decks (yes even with Google search hacks).

---

## Overview

### Goal
To build a Python app/script that:
- Ingests **pitch decks in PDF/PPT format**
- Extracts **key information** and **claims**
- Conducts **external research** beyond the deck
- Validates startup claims using multi-agent reasoning
- Outputs a **well-structured Markdown report** for an **Investment Manager**

### Target User
Investment managers or analysts evaluating early-stage startups.

---

## Architecture

The system uses three coordinated **AI agents**, each with distinct roles:

| Agent | Description |
|--------|--------------|
| **Orchestrator Agent** | Analyzes the deck, extracts company data, identifies gaps, and generates a research plan |
| **Research Agent** | Conducts parallel DuckDuckGo searches, scrapes content (via Selenium/Requests), and summarizes findings |
| **Validator Agent** | Fact-checks and verifies startup claims using structured evidence reasoning |

---

## Usage
```text
pip install requirements.txt

python pipeline.py <.pptx or .pdf file>
```

## Pipeline Flow

```text
Input: Pitch deck (PDF or PPTX)
   ↓
Orchestrator → Extracts company info and creates research plan
   ↓
Research Agent → Executes searches, scrapes evidence
   ↓
Validator Agent → Validates claims using evidence
   ↓
Output: Markdown investment report  
    ├── *_deck_analysis.json
    ├── *_research_results.json
    ├── *_validation_report.json
    └── *_FINAL_REPORT.md           # Main deliverable
```

--- 
## Future Enhancements
### Slack Integration
- Add Slack bot, easy to use for Investment Manager
- Respond with markdown report in thread

### Other Enhancements
- Support for more file formats
- Cached research results to avoid re-scraping
- Configurable validation thresholds
- Export to PDF/DOCX for sharing
