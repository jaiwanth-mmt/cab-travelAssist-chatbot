# Travel Assist Chatbot - API Documentation

## Base URL
```
http://localhost:8000
```

## Table of Contents
1. [Health Check](#1-health-check)
2. [Chat Endpoint](#2-chat-endpoint)
3. [Ingest Documentation](#3-ingest-documentation)
4. [Get Ingestion Status](#4-get-ingestion-status)
5. [Get Session Info](#5-get-session-info)
6. [Clear Session](#6-clear-session)

---

## 1. Health Check

Check the health status of the API and its services.

### Endpoint
```
GET /health
```

### Request
No request body required.

### Response

**Status Code:** `200 OK`

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "embedding_model": "loaded",
    "vector_store": "connected",
    "llm": "configured"
  }
}
```

### cURL Example
```bash
curl -X GET http://localhost:8000/health
```

---

## 2. Chat Endpoint

Send a query to the chatbot and receive an AI-generated answer based on the documentation.

### Endpoint
```
POST /chat
```

### Request

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "session_id": "string",
  "user_query": "string"
}
```

**Field Descriptions:**
| Field | Type | Required | Description | Constraints |
|-------|------|----------|-------------|-------------|
| `session_id` | string | Yes | Unique session identifier for conversation tracking | 1-100 characters |
| `user_query` | string | Yes | User's question or query | 1-2000 characters |

**Example Request:**
```json
{
  "session_id": "vendor-session-123",
  "user_query": "How do I call the search API?"
}
```

### Response

**Status Code:** `200 OK`

```json
{
  "session_id": "string",
  "answer": "string",
  "sources": ["string"],
  "confidence": "high|medium|low|none",
  "metadata": {
    "retrieved_chunks": 0,
    "avg_similarity": 0.0,
    "latency_ms": 0.0
  }
}
```

**Field Descriptions:**
| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session identifier |
| `answer` | string | Generated answer to the user's query |
| `sources` | array | List of documentation sections used to generate the answer |
| `confidence` | string | Confidence level: `high`, `medium`, `low`, or `none` |
| `metadata.retrieved_chunks` | integer | Number of chunks retrieved from vector store |
| `metadata.avg_similarity` | float | Average similarity score of retrieved chunks (0.0-1.0) |
| `metadata.latency_ms` | float | Total processing time in milliseconds |

**Example Response:**
```json
{
  "session_id": "vendor-session-123",
  "answer": "The Search API is called by sending a POST request to your partner search endpoint. The request should include parameters like origin, destination, travel dates, and passenger details. The API will return available travel options with pricing and availability information.",
  "sources": [
    "Normal Booking Flow - Search",
    "API Flowchart",
    "Search API Documentation"
  ],
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
- `low`: avg_similarity >= similarity_threshold (default 0.65)
- `none`: No relevant context found

### Error Responses

**Status Code:** `400 Bad Request`
```json
{
  "detail": "Validation error message"
}
```

**Status Code:** `500 Internal Server Error`
```json
{
  "detail": "Error processing request: [error details]"
}
```

### cURL Example
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "vendor-session-123",
    "user_query": "How do I call the search API?"
  }'
```

---

## 3. Ingest Documentation

Process and ingest the documentation file into the Pinecone vector store. This is a one-time operation that should be run before using the chatbot.

### Endpoint
```
POST /ingest
```

### Request

**Headers:**
```
Content-Type: application/json
```

**Body (Optional):**
```json
{
  "force_reindex": false
}
```

**Field Descriptions:**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `force_reindex` | boolean | No | `false` | Force re-indexing even if index already exists |

**Example Request:**
```json
{
  "force_reindex": false
}
```

### Response

**Status Code:** `200 OK`

**Success Response:**
```json
{
  "status": "success",
  "stats": {
    "chunks_created": 50,
    "chunks_uploaded": 50,
    "time_taken_seconds": 45.2
  },
  "message": "Documentation ingested successfully"
}
```

**Already Indexed Response:**
```json
{
  "status": "skipped",
  "stats": {
    "chunks_created": 0,
    "chunks_uploaded": 0,
    "time_taken_seconds": 0.0
  },
  "message": "Index already contains 50 vectors. Use force_reindex=true to re-ingest."
}
```

**Field Descriptions:**
| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Status of the ingestion: `success` or `skipped` |
| `stats.chunks_created` | integer | Number of chunks created from the document |
| `stats.chunks_uploaded` | integer | Number of chunks successfully uploaded to vector store |
| `stats.time_taken_seconds` | float | Total time taken for ingestion in seconds |
| `message` | string | Additional message or notes |

### Error Responses

**Status Code:** `404 Not Found`
```json
{
  "detail": "Documentation file not found: documentation.txt"
}
```

**Status Code:** `500 Internal Server Error`
```json
{
  "detail": "Error during ingestion: [error details]"
}
```

### cURL Examples

**Basic Ingestion:**
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json"
```

**Force Re-indexing:**
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"force_reindex": true}'
```

---

## 4. Get Ingestion Status

Get the current status of the vector store.

### Endpoint
```
GET /ingest/status
```

### Request
No request body required.

### Response

**Status Code:** `200 OK`

```json
{
  "status": "ok",
  "vector_store": {
    "total_vectors": 50,
    "dimension": 384,
    "index_fullness": 0.0001
  }
}
```

**Field Descriptions:**
| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Overall status |
| `vector_store.total_vectors` | integer | Total number of vectors in the index |
| `vector_store.dimension` | integer | Dimension of the embedding vectors |
| `vector_store.index_fullness` | float | Index fullness percentage (0.0-1.0) |

### Error Responses

**Status Code:** `500 Internal Server Error`
```json
{
  "detail": "Error getting status: [error details]"
}
```

### cURL Example
```bash
curl -X GET http://localhost:8000/ingest/status
```

---

## 5. Get Session Info

Retrieve information about a conversation session.

### Endpoint
```
GET /session/{session_id}
```

### Request

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Unique session identifier |

### Response

**Status Code:** `200 OK`

```json
{
  "session_id": "vendor-session-123",
  "message_count": 10,
  "has_summary": false,
  "last_activity": "2026-01-23T12:30:45.123456"
}
```

**Field Descriptions:**
| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session identifier |
| `message_count` | integer | Total number of messages in the session |
| `has_summary` | boolean | Whether the session has a summary |
| `last_activity` | string | Timestamp of last activity (ISO 8601 format) |

### Error Responses

**Status Code:** `500 Internal Server Error`
```json
{
  "detail": "Error getting session info: [error details]"
}
```

### cURL Example
```bash
curl -X GET http://localhost:8000/session/vendor-session-123
```

---

## 6. Clear Session

Clear conversation history for a session.

### Endpoint
```
DELETE /session/{session_id}
```

### Request

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Unique session identifier |

### Response

**Status Code:** `200 OK`

**Success Response:**
```json
{
  "status": "success",
  "message": "Session vendor-session-123 cleared"
}
```

**Not Found Response:**
```json
{
  "status": "not_found",
  "message": "Session vendor-session-123 not found"
}
```

### Error Responses

**Status Code:** `500 Internal Server Error`
```json
{
  "detail": "Error clearing session: [error details]"
}
```

### cURL Example
```bash
curl -X DELETE http://localhost:8000/session/vendor-session-123
```

---

## Common HTTP Status Codes

| Status Code | Description |
|-------------|-------------|
| `200 OK` | Request successful |
| `400 Bad Request` | Invalid request parameters or body |
| `404 Not Found` | Resource not found |
| `500 Internal Server Error` | Server-side error occurred |

---

## Rate Limiting

Currently, there are no rate limits implemented. However, it's recommended to implement rate limiting in production environments.

---

## Authentication

Currently, the API does not require authentication. For production use, implement appropriate authentication mechanisms (API keys, OAuth, etc.).

---

## Interactive API Documentation

The API also provides interactive documentation powered by Swagger UI and ReDoc:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

These interfaces allow you to:
- View all available endpoints
- See request/response schemas
- Test API calls directly from the browser
- Download OpenAPI specification

---

## Example Workflow

### 1. Check Health
```bash
curl -X GET http://localhost:8000/health
```

### 2. Ingest Documentation (First Time Only)
```bash
curl -X POST http://localhost:8000/ingest
```

### 3. Check Ingestion Status
```bash
curl -X GET http://localhost:8000/ingest/status
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
curl -X GET http://localhost:8000/session/my-session-1
```

### 7. Clear Session (When Done)
```bash
curl -X DELETE http://localhost:8000/session/my-session-1
```

---

## Notes

- **Session Management:** The `session_id` is used to maintain conversation context across multiple queries. Use the same `session_id` for related questions.
- **Conversation Memory:** The system automatically manages conversation history and summarizes long conversations.
- **Similarity Threshold:** Responses with low similarity scores may indicate the question is outside the scope of the documentation.
- **Vector Store:** The Pinecone vector store must be populated (via `/ingest`) before the chat endpoint can provide meaningful answers.

---

## Support

For issues or questions, please refer to the main README.md file or contact the development team.
