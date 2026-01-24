"""Query preprocessing and enhancement service"""

import re
from typing import List, Dict, Tuple, Optional

from backend.app.utils.logger import setup_logger

logger = setup_logger(__name__)


class QueryPreprocessor:
    """
    Enhance user queries for better retrieval
    - Expand queries with synonyms and related terms
    - Detect query intent
    - Rewrite follow-up questions with context
    """
    
    def __init__(self):
        # API-related keywords and their variations
        self.api_synonyms = {
            "search": ["search", "find", "lookup", "query", "get fare", "check availability"],
            "block": ["block", "hold", "reserve", "lock"],
            "booking": ["booking", "book", "reserve", "make reservation"],
            "cancel": ["cancel", "cancellation", "remove", "delete booking"],
            "payment": ["payment", "pay", "paid", "transaction", "charge"],
            "assign": ["assign", "allocate", "attach", "map"],
            "chauffeur": ["chauffeur", "driver", "cab driver", "vehicle driver"],
            "tracking": ["tracking", "track", "location", "gps", "position"],
            "start": ["start", "begin", "initiate", "commence"],
            "pickup": ["pickup", "boarded", "passenger on board", "customer pickup"],
            "drop": ["drop", "alight", "dropoff", "destination reached"],
            "flow": ["flow", "workflow", "process", "sequence", "steps"],
            "authentication": ["authentication", "auth", "api key", "credentials"],
            "request": ["request", "payload", "input", "body"],
            "response": ["response", "output", "result", "return"],
            "endpoint": ["endpoint", "api", "url", "path"],
            "parameter": ["parameter", "param", "field", "attribute"],
        }
        
        # Common entities in documentation
        self.entity_patterns = {
            "api_endpoint": r"/\w+(?:/\w+)*",
            "api_name": r"(?:Search|Block|Paid|Cancel|Assign|Reassign|Start|Arrived|Pickup|Alight|Detach|Update)",
            "http_method": r"\b(?:GET|POST|PUT|DELETE|PATCH)\b",
            "status_code": r"\b(?:200|201|400|401|403|404|500)\b",
        }
        
        # Query intent categories
        self.intent_keywords = {
            "api_usage": ["how to", "how do i", "how can i", "steps to", "way to"],
            "api_details": ["what is", "explain", "describe", "tell me about", "details of"],
            "flow": ["flow", "workflow", "process", "sequence", "lifecycle", "journey"],
            "example": ["example", "sample", "format", "structure", "template"],
            "troubleshooting": ["error", "issue", "problem", "not working", "fail"],
            "parameters": ["parameters", "fields", "attributes", "what to send"],
        }
    
    def detect_intent(self, query: str) -> str:
        """
        Detect the intent of the query
        Returns: api_usage, api_details, flow, example, troubleshooting, parameters, or general
        """
        query_lower = query.lower()
        
        for intent, keywords in self.intent_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                return intent
        
        return "general"
    
    def extract_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract structured entities from query"""
        entities = {}
        
        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, query, re.IGNORECASE)
            if matches:
                entities[entity_type] = list(set(matches))
        
        return entities
    
    def expand_query(self, query: str, intent: str) -> str:
        """
        Expand query with related terms for better semantic matching
        """
        query_lower = query.lower()
        expanded_terms = []
        
        # Find matching synonyms
        for term, synonyms in self.api_synonyms.items():
            if any(syn in query_lower for syn in synonyms):
                # Add a few related terms
                expanded_terms.extend(synonyms[:2])
        
        # Add intent-specific context
        if intent == "flow":
            expanded_terms.extend(["steps", "sequence", "process"])
        elif intent == "example":
            expanded_terms.extend(["request format", "response format", "sample"])
        elif intent == "api_usage":
            expanded_terms.extend(["implementation", "integration"])
        elif intent == "parameters":
            expanded_terms.extend(["fields", "required", "optional"])
        
        # Create expanded query
        if expanded_terms:
            # Limit expansion to avoid noise
            unique_terms = list(set(expanded_terms))[:4]
            expanded = f"{query} {' '.join(unique_terms)}"
            return expanded
        
        return query
    
    def rewrite_followup_query(
        self, 
        current_query: str, 
        conversation_history: List[Dict]
    ) -> str:
        """
        Rewrite follow-up questions to be self-contained using conversation context
        
        Args:
            current_query: The current user query
            conversation_history: List of previous turns
            
        Returns:
            Rewritten query with context
        """
        query_lower = current_query.lower()
        
        # Check if this looks like a follow-up question
        followup_indicators = [
            "what about", "how about", "and", "also", "that", "it", "this",
            "can you explain", "tell me more", "more details", "elaborate",
            "example", "show me"
        ]
        
        is_followup = any(indicator in query_lower for indicator in followup_indicators)
        
        # Check for pronouns
        has_pronoun = bool(re.search(r'\b(it|this|that|they|them|its)\b', query_lower))
        
        # Very short queries are likely follow-ups
        is_short = len(current_query.split()) < 5
        
        if not (is_followup or has_pronoun or is_short) or not conversation_history:
            return current_query
        
        # Extract context from recent conversation
        context_terms = []
        
        # Look at last 2-3 turns
        recent_turns = conversation_history[-3:] if len(conversation_history) >= 3 else conversation_history
        
        for turn in recent_turns:
            if turn["role"] == "user":
                # Extract key terms from user questions
                user_text = turn["content"]
                
                # Extract API names
                api_matches = re.findall(
                    r'\b(?:Search|Block|Paid|Cancel|Assign|Reassign|Start|Arrived|Pickup|Alight|Detach|Update|Booking)\b',
                    user_text,
                    re.IGNORECASE
                )
                context_terms.extend(api_matches)
                
                # Extract endpoints
                endpoint_matches = re.findall(r'/\w+', user_text)
                context_terms.extend(endpoint_matches)
        
        # Create rewritten query
        if context_terms:
            # Get unique context terms
            unique_context = list(set(context_terms))[:3]
            
            # Rewrite query with context
            rewritten = f"{current_query} (context: {' '.join(unique_context)})"
            logger.info(f"Rewrote follow-up query: '{current_query}' -> '{rewritten}'")
            return rewritten
        
        return current_query
    
    def preprocess(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, any]:
        """
        Main preprocessing function
        
        Returns:
            Dictionary with:
            - original_query: The original query
            - processed_query: Enhanced query for retrieval
            - intent: Detected intent
            - entities: Extracted entities
        """
        # Detect intent
        intent = self.detect_intent(query)
        
        # Extract entities
        entities = self.extract_entities(query)
        
        # Rewrite if it's a follow-up
        if conversation_history:
            query = self.rewrite_followup_query(query, conversation_history)
        
        # Expand query
        expanded_query = self.expand_query(query, intent)
        
        logger.info(f"Query preprocessing: intent={intent}, entities={entities}")
        
        return {
            "original_query": query,
            "processed_query": expanded_query,
            "intent": intent,
            "entities": entities
        }


# Global instance
_query_preprocessor = None


def get_query_preprocessor() -> QueryPreprocessor:
    """Get or create the global query preprocessor instance"""
    global _query_preprocessor
    if _query_preprocessor is None:
        _query_preprocessor = QueryPreprocessor()
    return _query_preprocessor
