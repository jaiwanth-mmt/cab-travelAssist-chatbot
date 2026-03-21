# MakeMyTrip Cab Vendor Travel Assist Chatbot

A production-grade RAG chatbot that helps cab vendors integrate with the MakeMyTrip platform by providing accurate, contextual responses from official documentation.

## Features

- **Advanced RAG Pipeline**: Hybrid search with semantic, keyword, and metadata signals
- **Semantic Understanding**: Powered by Sentence Transformers with intelligent chunking
- **Conversational Memory**: Context-aware with automatic summarization
- **Query Enhancement**: Intent detection, expansion, and follow-up rewriting
- **Code Preservation**: Special handling for API formats and JSON
- **Production-Ready**: Comprehensive logging and error handling

## Technical Stack

- **Backend**: FastAPI with async support
- **Embeddings**: Sentence Transformers (all-MiniLM-L6-v2, 384-dim)
- **Vector Store**: Pinecone (serverless, cosine similarity)
- **LLM**: Azure OpenAI GPT-4
- **Memory**: In-memory sessions with summarization
- **Search**: Hybrid (semantic + keyword + metadata)

## Prerequisites

- Python 3.10 or higher
- Azure OpenAI account
- Pinecone account (Free tier supported)

## Quick Start

### Installation

```bash
# Clone and setup
git clone <repository-url>
cd cab-travelAssist-chatbot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
# Create a .env file in the project root and add your credentials (see Configuration section below)
```

### Configuration

Create a `.env` file with:

```env
# Azure OpenAI (REQUIRED)
AZURE_OPENAI_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# Pinecone (REQUIRED)
PINECONE_API_KEY=your_key_here
PINECONE_ENVIRONMENT=us-east-1
PINECONE_INDEX_NAME=mmt-cab-docs
```

### Running the Application

```bash
# Start the server
uvicorn backend.app.main:app --reload --port 8000

# In another terminal, ingest documentation
curl -X POST http://localhost:8000/ingest

# Test the chatbot
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-1", "user_query": "How do I call the search API?"}'
```

## API Endpoints

### Health Check
```bash
GET /health
```

### Ingest Documentation
```bash
POST /ingest
# Optional: Force re-indexing
POST /ingest -d '{"force_reindex": true}'

# Check ingestion status
GET /ingest/status
```

### Chat
```bash
POST /chat
{
  "session_id": "string",
  "user_query": "string"
}
```

### Session Management
```bash
GET /session/{session_id}
DELETE /session/{session_id}
```

## Example Queries

```bash
# API usage
"How do I call the search API?"
"What are the mandatory fields in the Block API?"

# Booking flow
"Explain the normal booking flow"
"What happens after a customer selects a cab?"

# Error handling
"How do I handle trip cancellation?"
"What should I do if a customer doesn't board?"

# Follow-up questions (maintains context)
"Tell me about the Search API"
"What are the mandatory parameters?"
```

## Interactive Documentation

Visit `http://localhost:8000/docs` for Swagger UI with interactive API testing.

## Project Structure

```
cab-travelAssist-chatbot/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI application
│       ├── api/                 # API endpoints
│       │   ├── chat.py          # Chat endpoint
│       │   └── ingest.py        # Ingestion endpoint
│       ├── core/                # Configuration & prompts
│       │   ├── config.py        # Settings & config
│       │   └── prompts.py       # LLM prompts
│       ├── services/            # Business logic
│       │   ├── chunker.py       # Document chunking
│       │   ├── embeddings.py    # Embedding generation
│       │   ├── hybrid_search.py # Hybrid search & reranking
│       │   ├── llm.py           # LLM integration
│       │   ├── memory.py        # Conversation memory
│       │   ├── query_processor.py # Query preprocessing
│       │   └── vector_store.py  # Pinecone integration
│       ├── models/              # Pydantic models
│       │   ├── requests.py      # Request models
│       │   └── responses.py     # Response models
│       └── utils/               # Utilities
│           └── logger.py        # Logging setup
├── documentation.txt            # Knowledge base
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables (create this)
└── README.md
```

## Development

### Code Quality

- Type hints throughout
- Pydantic models for validation
- Structured logging
- Comprehensive error handling

### Testing

Tests can be added using pytest:

```bash
pip install pytest pytest-cov httpx
pytest --cov=backend.app
```

## Troubleshooting

### "No relevant chunks found"
- Ensure ingestion completed: `curl http://localhost:8000/ingest/status`
- Check if vectors exist in the index
- Try rephrasing with specific API names

### Azure OpenAI errors
- Verify credentials in `.env`
- Check deployment name matches configuration
- Ensure quota is available
- Verify API version is correct

### Pinecone errors
- Verify API key and environment
- Try deleting and recreating index with `force_reindex=true`
- Check Pinecone dashboard for index status

### Module import errors
- Run commands from project root
- Ensure virtual environment is activated
- Verify all dependencies: `pip install -r requirements.txt`

### Connection errors
- Check if services (Azure OpenAI, Pinecone) are accessible
- Verify network connectivity
- Check firewall settings

## Production Considerations

### Security
- Implement API authentication (JWT/API keys)
- Add rate limiting
- Restrict CORS origins
- Use secrets manager for credentials

### Infrastructure
- Use Redis for session storage
- Deploy behind load balancer
- Enable HTTPS
- Set up health check monitoring

### Monitoring
- Application monitoring (Datadog, New Relic)
- Log aggregation (ELK stack, CloudWatch)
- Track metrics: latency, accuracy, error rates
- Set up alerts for failures

### Performance
- Cache frequent queries
- Use connection pooling
- Consider quantized models for faster inference
- Batch processing for multiple sessions

## License

[Your License Here]

## Support

For issues or questions, see the API documentation or contact the development team.
