# SHL Assessment Recommender Agent

A conversational AI agent that helps hiring managers and recruiters discover relevant SHL Individual Test Solutions through natural dialogue.

## Features

- **Conversational Interface**: Natural language dialogue for assessment discovery
- **Catalog Integration**: Uses official SHL product catalog with 377+ assessments
- **Smart Search**: Semantic + keyword search with FAISS vector index
- **Multi-turn Dialogue**: Handles clarification, refinement, comparison, and refusal
- **Stateless API**: Every request carries full conversation history
- **FastAPI**: Modern, fast web framework

## Tech Stack

- **Backend**: FastAPI, Python 3.10+
- **LLM**: Google Gemini API
- **Search**: Sentence Transformers, FAISS

## Quick Start

### Prerequisites

- Python 3.10+
- Google Gemini API key (free at [Google AI Studio](https://aistudio.google.com/))

### Installation

```bash
# Clone
git clone https://github.com/yourusername/shl-assessment-agent.git
cd shl-assessment-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your LLM_API_KEY

# Build catalog index
python scripts/build_catalog.py

# Run
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
---

## API Endpoints
```text
GET /health
```

---

## CHAT
```http
POST /chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "I need to hire a senior Java developer"}
  ]
}
```
---

## Example Conversation

### Recommendation
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "I need to hire a senior Java developer"}]}'
```
### Comparison
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What's the difference between Core Java (Advanced Level) and Core Java (Entry Level)?"}]}'
```
---

## Project Structure
```text
shl-assessment-agent/
├── app/
│   ├── api/          # Routes and schemas
│   ├── agent/        # Orchestrator, policy, context, prompts
│   ├── catalog/      # Loader, indexer, retriever
│   └── llm/          # LLM client
├── data/             # Catalog cache
├── scripts/          # Build scripts
├── tests/            # Tests
└── requirements.txt
```

---

## Configuration

* Create .env file
```env
LLM_API_KEY=your_google_api_key
LLM_MODEL=gemini-3.5-flash
LLM_PROVIDER=gemini
LOG_LEVEL=INFO
```



