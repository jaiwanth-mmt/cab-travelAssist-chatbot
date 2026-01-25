# Memory and Follow-up Query Improvements

## Problem Statement

The chatbot was failing to answer follow-up meta-queries like "summarize it" or "explain more" even when using the same session ID. The issue occurred because:

1. The RAG (Retrieval-Augmented Generation) system always performed new vector searches for every query
2. Meta-queries like "summarize it" are too vague for semantic search, resulting in zero relevant documents
3. Without retrieved documents, the system couldn't generate an answer, even though conversation history was available
4. Query rewriting only captured API names/endpoints, missing broader contextual phrases like "tracking flow"

## Solution Implemented

### 1. **Document Caching in Session Memory** (`memory.py`)

Added caching mechanism to store retrieved documents from the previous turn:

```python
# New fields in SessionMemory
self.last_retrieved_chunks: List[Dict] = []  # Cache for retrieved documents
self.last_query: Optional[str] = None         # Last processed query
```

**New methods:**
- `cache_retrieved_chunks()`: Store documents after successful retrieval
- `get_cached_chunks()`: Retrieve cached documents
- `has_cached_chunks()`: Check if cache is available

### 2. **Enhanced Query Rewriting** (`query_processor.py`)

Improved the follow-up query rewriter to capture broader semantic context:

**Before:** Only extracted specific API names and endpoints
```python
# Old: Only looked for "Search", "Block", "Cancel", etc.
api_matches = re.findall(r'\b(?:Search|Block|Paid|...)\b', ...)
```

**After:** Now captures topic phrases and noun phrases
```python
# New: Extracts broader phrases like "tracking flow", "booking process", etc.
topic_patterns = [
    r'\b(tracking\s+flow)\b',
    r'\b(booking\s+process)\b',
    r'\b(payment\s+flow)\b',
    ...
]
```

### 3. **Meta-Query Detection** (`query_processor.py`)

Added intelligent detection for meta-queries that should reuse context:

```python
def is_meta_query(self, query: str) -> bool:
    """Detect if query is asking about previous answer"""
    
    meta_patterns = [
        r'^(summarize|summarise)\s*(it|that|this)?',
        r'^(explain|elaborate)\s*(more|further|it)?',
        r'^(tell me more|more details)',
        r'^(give|show|provide)\s*.*\s*(example|sample)',
        ...
    ]
```

**Detected meta-queries:**
- "Summarize it"
- "Explain more"
- "Tell me more"
- "Give me an example"
- "Elaborate on that"
- "In other words"
- etc.

### 4. **Smart Document Reuse** (`chat.py`)

Modified the chat endpoint to use cached documents for meta-queries:

```python
# Check if this is a meta-query and we have cached chunks
if is_meta_query and memory_manager.has_cached_chunks(request.session_id):
    # Reuse cached documents instead of searching
    retrieved_chunks = memory_manager.get_cached_chunks(request.session_id)
    used_cache = True
else:
    # Perform normal hybrid search
    retrieved_chunks = hybrid_search.search(...)
```

## Benefits

### ✅ **Follow-up Queries Now Work**
- "What is tracking flow?" → Answer with details
- "Summarize it" → ✅ Works! Uses cached documents
- "Tell me more" → ✅ Works! Reuses context

### ✅ **Better Context Capture**
- Query rewriting now captures semantic phrases, not just keywords
- "tracking flow", "booking process", "payment flow" are preserved
- More accurate follow-up query rewriting

### ✅ **Reduced API Calls**
- Meta-queries don't trigger unnecessary vector searches
- Faster response times for follow-ups
- Lower costs (fewer embedding API calls)

### ✅ **Improved User Experience**
- Natural conversation flow
- Users can ask for summaries, elaborations, examples without repeating context
- More intuitive chatbot behavior

## Testing Results

Test scenario with session ID `test-meta-query-session`:

1. **Q1:** "What is the tracking flow?"
   - Retrieved: 5 chunks
   - Confidence: low
   - Status: ✅ Answered successfully

2. **Q2:** "Summarize it"
   - Retrieved: 5 chunks (from cache)
   - Confidence: low
   - Status: ✅ **SUCCESS - Used cached chunks!**

3. **Q3:** "Tell me more about it"
   - Retrieved: 5 chunks (from cache)
   - Confidence: low
   - Status: ✅ Answered successfully

## Log Evidence

```
Query intent: general, is_meta: True, processed: Summarize it (context: tracking flow)
Meta-query detected - reusing cached chunks from previous turn
Retrieved 5 chunks, avg hybrid score: 0.514
```

## Implementation Details

### Files Modified

1. **`backend/app/services/memory.py`**
   - Added document caching to `SessionMemory` class
   - Added cache management methods to `MemoryManager`

2. **`backend/app/services/query_processor.py`**
   - Enhanced `rewrite_followup_query()` with broader context extraction
   - Added `is_meta_query()` method for meta-query detection
   - Updated `preprocess()` to return `is_meta_query` flag

3. **`backend/app/api/chat.py`**
   - Modified chat endpoint to check for meta-queries
   - Added cache reuse logic
   - Added cache population after successful retrieval

### Backward Compatibility

✅ All changes are backward compatible:
- Existing queries work exactly as before
- New functionality is additive
- No breaking changes to API responses

## Usage in FastAPI Swagger UI

Now when testing in `localhost:8001/docs`:

1. First request with session ID `vendor-session-123`:
```json
{
  "session_id": "vendor-session-123",
  "user_query": "What is the tracking flow?"
}
```

2. Follow-up with SAME session ID:
```json
{
  "session_id": "vendor-session-123",
  "user_query": "Summarize it"
}
```

✅ **The bot will now successfully summarize using cached context!**

## Future Enhancements

Potential improvements for consideration:

1. **Cache expiration**: Expire cached documents after N turns
2. **Multi-turn cache**: Cache last N retrievals instead of just last one
3. **Smart cache invalidation**: Clear cache when topic changes significantly
4. **Cache persistence**: Store cache in Redis for multi-instance deployments
