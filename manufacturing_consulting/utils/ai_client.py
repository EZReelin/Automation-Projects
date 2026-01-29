"""
AI Client wrapper for Claude and OpenAI integrations.

Provides a unified interface for AI operations across all services.
"""

import json
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings


class AIClient:
    """
    Unified AI client for Claude and OpenAI APIs.
    
    Provides methods for:
    - Text generation
    - Embeddings
    - Structured output generation
    """
    
    def __init__(self):
        self.anthropic_key = settings.ai.anthropic_api_key
        self.openai_key = settings.ai.openai_api_key
        self.default_model = settings.ai.default_model
        self.max_tokens = settings.ai.max_tokens
        self.temperature = settings.ai.temperature
        self.embedding_model = settings.ai.embedding_model
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        json_output: bool = False,
    ) -> str:
        """
        Generate text using Claude API.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            model: Model to use (defaults to config)
            max_tokens: Max output tokens
            temperature: Sampling temperature
            json_output: Whether to expect JSON response
            
        Returns:
            Generated text response
        """
        model = model or self.default_model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature
        
        messages = [{"role": "user", "content": prompt}]
        
        request_body = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        
        if system_prompt:
            request_body["system"] = system_prompt
        
        if temperature is not None:
            request_body["temperature"] = temperature
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_key.get_secret_value() if self.anthropic_key else "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=request_body,
                timeout=120.0,
            )
            response.raise_for_status()
            result = response.json()
            
        return result["content"][0]["text"]
    
    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate structured output conforming to a schema.
        
        Args:
            prompt: User prompt
            schema: JSON schema for expected output
            system_prompt: Optional system instructions
            
        Returns:
            Parsed JSON response
        """
        schema_instruction = f"""
You must respond with valid JSON that conforms to this schema:
{json.dumps(schema, indent=2)}

Respond ONLY with the JSON, no additional text or markdown.
"""
        
        full_system = (system_prompt or "") + "\n\n" + schema_instruction
        
        response = await self.generate_text(
            prompt=prompt,
            system_prompt=full_system,
            json_output=True,
        )
        
        # Parse and validate JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError(f"Failed to parse JSON from response: {response[:200]}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def generate_embeddings(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for text using OpenAI API.
        
        Args:
            texts: List of texts to embed
            model: Embedding model to use
            
        Returns:
            List of embedding vectors
        """
        model = model or self.embedding_model
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.openai_key.get_secret_value() if self.openai_key else ''}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "input": texts,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()
        
        # Sort by index to maintain order
        sorted_data = sorted(result["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]
    
    async def generate_single_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.generate_embeddings([text])
        return embeddings[0]


class AIPromptBuilder:
    """
    Helper class for building structured prompts.
    
    Provides templates and utilities for common AI operations.
    """
    
    @staticmethod
    def quote_generation_prompt(
        customer_name: str,
        parts: list[dict],
        context: dict | None = None,
    ) -> str:
        """Build prompt for quote generation."""
        parts_text = "\n".join([
            f"- {p.get('part_number', 'N/A')}: {p.get('description', '')} "
            f"(Qty: {p.get('quantity', 1)})"
            for p in parts
        ])
        
        return f"""
Generate a professional manufacturing quote for {customer_name}.

Parts Requested:
{parts_text}

Please provide:
1. Unit pricing recommendations based on manufacturing costs
2. Lead time estimates
3. Any relevant notes or conditions
4. Suggested discounts for quantity breaks

Context: {json.dumps(context or {})}
"""
    
    @staticmethod
    def sop_generation_prompt(
        interview_transcript: str,
        domain_name: str,
        template_sections: list[dict],
    ) -> str:
        """Build prompt for SOP generation from interview."""
        sections_text = "\n".join([
            f"- {s.get('title', 'Section')}: {s.get('placeholder', '')}"
            for s in template_sections
        ])
        
        return f"""
Convert the following interview transcript into a structured Standard Operating Procedure (SOP) 
for the knowledge domain: {domain_name}

Interview Transcript:
{interview_transcript}

The SOP should include these sections:
{sections_text}

Guidelines:
1. Extract specific step-by-step procedures
2. Identify safety considerations and cautions
3. Note any equipment or materials needed
4. Include quality checkpoints
5. Add troubleshooting tips mentioned
6. Maintain technical accuracy

Format the response as a structured JSON document.
"""
    
    @staticmethod
    def erp_query_prompt(
        query: str,
        erp_system: str,
        context_chunks: list[str],
        custom_terminology: dict | None = None,
    ) -> str:
        """Build prompt for ERP query answering."""
        context_text = "\n\n---\n\n".join(context_chunks)
        terminology_text = ""
        if custom_terminology:
            terminology_text = "\n".join([
                f"- '{k}' means '{v}'"
                for k, v in custom_terminology.items()
            ])
        
        return f"""
You are an expert assistant for {erp_system} ERP system.

User Question: {query}

{"Custom Terminology:" + terminology_text if terminology_text else ""}

Relevant Documentation:
{context_text}

Instructions:
1. Answer the question based ONLY on the provided documentation
2. Include specific menu paths or navigation steps when available
3. Reference transaction codes if applicable
4. If the documentation doesn't contain the answer, clearly state that
5. Suggest related topics the user might find helpful

Provide a clear, concise answer.
"""


# Global AI client instance
ai_client = AIClient()
prompt_builder = AIPromptBuilder()
