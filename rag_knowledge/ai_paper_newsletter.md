# AI Paper Newsletter Project

## Summary
The AI Paper Newsletter project is an automated research-newsletter pipeline that fetches recent AI and machine learning papers, filters and ranks them, generates summaries and deeper analysis, builds an HTML newsletter, and emails it to subscribers.

## Key Facts
- Project type: AI research newsletter / automated content pipeline
- Main purpose: Send a weekly-style or recurring email summary of important AI/ML papers
- Paper source: arXiv API
- Default paper categories: cs.AI, cs.LG, cs.CL, cs.CV, cs.NE, cs.MA, cs.RO, cs.SE, cs.IR, and stat.ML
- Topic queries include LLMs, agents, reasoning, multimodal models, alignment, interpretability, safety, attention, architecture, inference, and efficient training
- Candidate filtering: Keyword scoring, recency scoring, category diversity, and deduplication
- Model-assisted ranking: Uses an Anthropic model to select papers worth featuring
- Summary generation: Creates short structured summaries and deeper analyses for standout papers
- Newsletter output: Generates HTML newsletter files and LinkedIn post text
- Email delivery: Sends HTML email through Gmail SMTP
- Subscriber support: Includes subscribe and unsubscribe commands plus a simple signup app
- Storage: Supports SQLite by default and Postgres when DATABASE_URL is configured
- Deployment-related files: Includes Railway worker/web configuration files

## My Role
- Built the end-to-end paper discovery, ranking, summarization, and email pipeline
- Implemented arXiv fetching, paper deduplication, keyword scoring, and candidate shortlisting
- Used an LLM to rank papers and produce structured summaries
- Added persistence for papers, newsletter runs, and subscribers
- Created the email delivery flow and subscription interface
- Designed the project to reduce the AI-paper flood into a smaller set of high-signal research updates

## Technologies
- Python
- arXiv API
- Anthropic API
- SQLite
- Postgres
- Gmail SMTP
- HTML email generation
- WSGI simple server
- Railway configuration

## Safe Answer Guidance
The bot can say this project automates AI/ML paper discovery, ranking, summarization, newsletter generation, and email delivery. Do not claim the ranking is objectively authoritative, that every important paper is captured, or that the newsletter has a large subscriber base unless that is documented elsewhere.
