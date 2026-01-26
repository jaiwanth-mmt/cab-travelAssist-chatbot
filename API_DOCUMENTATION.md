# API Documentation

## Base URL
```
http://localhost:8000
```

## Endpoints

### 1. Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "embeddings": "ok",
    "vector_store": "ok (vectors: 250)",
    "llm": "ok"
  }
}
```

**Example:**
```bash
curl http://localhost:8000/health
```

---

### 2. Chat

**Endpoint:** `POST /chat`

**Request Body:**
```json
{
  "session_id": "vendor-session-123",
  "user_query": "How do I call the search API?"
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | Yes | Unique session identifier (1-100 chars) |
| `user_query` | string | Yes | User's question (1-2000 chars) |

**Response:**
```json
{
  "session_id": "vendor-session-123",
  "answer": "The Search API is called by sending a POST request...",
  "sources": ["Normal Booking Flow - Search", "API Flowchart"],
  "confidence": "high",
  "metadata": {
    "retrieved_chunks": 4,
    "avg_similarity": 0.82,
    "latency_ms": 450.5
  }
}
```

**Confidence Levels:**
- `high`: avg_similarity >= 0.80
- `medium`: avg_similarity >= 0.70
- `low`: avg_similarity >= 0.65
- `none`: No relevant context found

**Example:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "vendor-session-123",
    "user_query": "How do I call the search API?"
  }'
```

---

### 3. Ingest Documentation

**Endpoint:** `POST /ingest`

**Request Body (Optional):**
```json
{
  "force_reindex": false
}
```

**Parameters:**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `force_reindex` | boolean | No | `false` | Force re-indexing if index exists |

**Response (Success):**
```json
{
  "status": "success",
  "stats": {
    "chunks_created": 250,
    "chunks_uploaded": 250,
    "time_taken_seconds": 45.2
  },
  "message": "Documentation ingested successfully"
}
```

**Response (Already Indexed):**
```json
{
  "status": "skipped",
  "stats": {
    "chunks_created": 0,
    "chunks_uploaded": 0,
    "time_taken_seconds": 0.0
  },
  "message": "Index already contains 250 vectors. Use force_reindex=true to re-ingest."
}
```

**Examples:**
```bash
# Basic ingestion
curl -X POST http://localhost:8000/ingest

# Force re-indexing
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"force_reindex": true}'
```

---

### 4. Get Ingestion Status

**Endpoint:** `GET /ingest/status`

**Response:**
```json
{
  "status": "ok",
  "vector_store": {
    "total_vectors": 250,
    "dimension": 384,
    "index_fullness": 0.0001
  }
}
```

**Example:**
```bash
curl http://localhost:8000/ingest/status
```

---

### 5. Get Session Info

**Endpoint:** `GET /session/{session_id}`

**Response:**
```json
{
  "session_id": "vendor-session-123",
  "exists": true,
  "total_turns": 10,
  "has_summary": false,
  "created_at": "2026-01-26T12:30:45.123456",
  "last_accessed": "2026-01-26T12:35:20.456789"
}
```

**Example:**
```bash
curl http://localhost:8000/session/vendor-session-123
```

---

### 6. Clear Session

**Endpoint:** `DELETE /session/{session_id}`

**Response (Success):**
```json
{
  "status": "success",
  "message": "Session vendor-session-123 cleared"
}
```

**Response (Not Found):**
```json
{
  "status": "not_found",
  "message": "Session vendor-session-123 not found"
}
```

**Example:**
```bash
curl -X DELETE http://localhost:8000/session/vendor-session-123
```

---

## Error Responses

### Validation Error (422)
```json
{
  "error": "Validation Error",
  "message": "Invalid request data",
  "details": [...]
}
```

### Bad Request (400)
```json
{
  "detail": "Validation error message"
}
```

### Not Found (404)
```json
{
  "detail": "Documentation file not found: documentation.txt"
}
```

### Internal Server Error (500)
```json
{
  "detail": "Error processing request: ..."
}
```

---

## Interactive Documentation

Access interactive API documentation:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## Example Workflow

### 1. Check Health
```bash
curl http://localhost:8000/health
```

### 2. Ingest Documentation (First Time Only)
```bash
curl -X POST http://localhost:8000/ingest
```

### 3. Check Ingestion Status
```bash
curl http://localhost:8000/ingest/status
```

### 4. Start Chatting
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "my-session-1",
    "user_query": "How do I integrate the booking API?"
  }'
```

### 5. Continue Conversation (Same Session)
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "my-session-1",
    "user_query": "What are the required parameters?"
  }'
```

### 6. Check Session Info
```bash
curl http://localhost:8000/session/my-session-1
```

### 7. Clear Session
```bash
curl -X DELETE http://localhost:8000/session/my-session-1
```

---

## Notes

- **Session Management:** Use the same `session_id` for related questions to maintain conversation context
- **Conversation Memory:** The system automatically manages history and summarizes long conversations
- **Similarity Threshold:** Responses with low similarity scores may indicate out-of-scope questions
- **Vector Store:** Must be populated via `/ingest` before the chat endpoint can provide meaningful answers

---

## Authentication

Currently, the API does not require authentication. For production use, implement appropriate authentication mechanisms (API keys, OAuth, etc.).

## Rate Limiting

No rate limits are currently implemented. Consider adding rate limiting in production environments.

---

## Support

For issues or questions, refer to the main README.md or contact the development team.
