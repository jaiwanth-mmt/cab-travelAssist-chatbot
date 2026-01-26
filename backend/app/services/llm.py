"""Azure OpenAI LLM service"""

from typing import List, Dict, Tuple, Optional
from openai import AzureOpenAI
import asyncio

from backend.app.core.config import settings
from backend.app.core.prompts import SYSTEM_PROMPT, SUMMARIZATION_PROMPT
from backend.app.utils.logger import setup_logger

logger = setup_logger(__name__)


class LLMService:
    """Azure OpenAI service wrapper"""
    
    def __init__(self):
        logger.info("Initializing Azure OpenAI client")
        self.client = AzureOpenAI(
            api_key=settings.azure_openai_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint
        )
        self.deployment = settings.azure_openai_deployment
    
    async def generate_answer(
        self,
        query: str,
        context: List[Dict],
        memory: str
    ) -> Tuple[str, List[str]]:
        """Generate answer using Azure OpenAI"""
        context_text = self._format_context(context)
        
        system_message = SYSTEM_PROMPT.format(
            context=context_text,
            memory=memory,
            query=query
        )
        
        messages = [
            {"role": "system", "content": system_message}
        ]
        
        try:
            logger.info(f"Generating answer for query: {query[:100]}...")
            
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.deployment,
                messages=messages,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                top_p=0.95,
                frequency_penalty=0,
                presence_penalty=0
            )
            
            answer = response.choices[0].message.content
            
            sources = list(set([
                chunk['metadata']['section_title']
                for chunk in context
                if chunk['metadata'].get('section_title')
            ]))
            
            logger.info("Answer generated successfully")
            return answer, sources
            
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            raise
    
    async def summarize_conversation(self, conversation: str) -> str:
        """Summarize a conversation"""
        prompt = SUMMARIZATION_PROMPT.format(conversation=conversation)
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that summarizes conversations concisely."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            logger.info("Generating conversation summary")
            
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.deployment,
                messages=messages,
                temperature=0.3,
                max_tokens=300
            )
            
            summary = response.choices[0].message.content
            logger.info("Summary generated successfully")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return "Summary generation failed. Continuing with recent conversation history."
    
    def _format_context(self, context: List[Dict]) -> str:
        """Format retrieved chunks into context string"""
        if not context:
            return "No relevant documentation found."
        
        formatted_chunks = []
        for i, chunk in enumerate(context, 1):
            section = chunk['metadata'].get('section_title', 'Unknown Section')
            api_endpoint = chunk['metadata'].get('api_endpoint', '')
            text = chunk.get('text', '')
            
            source_label = f"[Source {i}: {section}"
            if api_endpoint:
                source_label += f" | Endpoint: {api_endpoint}"
            source_label += "]"
            
            formatted_chunk = f"{source_label}\n{text}\n{'=' * 80}\n"
            formatted_chunks.append(formatted_chunk)
        
        return "\n".join(formatted_chunks)
    
    def _deduplicate_chunks(self, chunks: List[Dict]) -> List[Dict]:
        if not chunks:
            return []
        
        seen_texts = set()
        unique_chunks = []
        
        for chunk in chunks:
            text = chunk.get('text', '')
            fingerprint = text[:200].strip()
            
            if fingerprint not in seen_texts:
                seen_texts.add(fingerprint)
                unique_chunks.append(chunk)
        
        return unique_chunks


_llm_service = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
