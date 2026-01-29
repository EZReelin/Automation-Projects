"""
ERP Query service.

Provides natural language interface for ERP system queries.
"""

import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.erp_copilot import (
    ERPConfiguration, ERPQuery, ERPQueryTemplate, DocumentationGap,
    QueryCategory
)
from services.erp_copilot.document_service import ERPDocumentService
from utils.logging import ServiceLogger
from utils.ai_client import ai_client, prompt_builder
from config.settings import settings


class ERPQueryService:
    """
    Service for handling ERP queries.
    
    Provides:
    - Natural language query processing
    - Context-aware responses
    - Query templates for common questions
    - Fallback handling for unanswerable queries
    """
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("erp_query")
        self.doc_service = ERPDocumentService(session, tenant_id)
    
    async def process_query(
        self,
        query_text: str,
        user_id: str,
        conversation_id: str | None = None,
        parent_query_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Process a natural language ERP query.
        
        Args:
            query_text: User's question
            user_id: User asking the question
            conversation_id: Conversation thread ID
            parent_query_id: Previous query in thread
            
        Returns:
            Dictionary with response and metadata
        """
        start_time = time.time()
        
        self.logger.log_operation_start(
            "process_query",
            tenant_id=self.tenant_id,
            query=query_text[:100],
        )
        
        # Get ERP configuration
        config = await self._get_erp_config()
        if not config:
            return {
                "response": "ERP system is not configured. Please contact your administrator.",
                "success": False,
                "error": "no_configuration",
            }
        
        # Classify query
        classification = await self._classify_query(query_text, config)
        
        # Check for template match
        template_response = await self._check_templates(query_text, config)
        if template_response:
            return await self._save_and_return_query(
                config_id=config.id,
                user_id=user_id,
                query_text=query_text,
                response=template_response,
                classification=classification,
                was_template=True,
                start_time=start_time,
                conversation_id=conversation_id,
                parent_query_id=parent_query_id,
            )
        
        # Search relevant documentation
        relevant_chunks = await self.doc_service.search_documents(
            query_text,
            module=classification.get("module"),
            limit=settings.erp_copilot.max_context_chunks,
        )
        
        if not relevant_chunks:
            # No relevant documentation found
            return await self._handle_no_documentation(
                config=config,
                user_id=user_id,
                query_text=query_text,
                classification=classification,
                start_time=start_time,
                conversation_id=conversation_id,
                parent_query_id=parent_query_id,
            )
        
        # Generate response from documentation
        context_chunks = [chunk.content for chunk, _ in relevant_chunks]
        confidence = sum(score for _, score in relevant_chunks) / len(relevant_chunks)
        
        response = await self._generate_response(
            query_text,
            context_chunks,
            config,
            classification,
        )
        
        # Build source references
        sources = []
        for chunk, score in relevant_chunks:
            doc = await self.doc_service.get_document(chunk.document_id)
            if doc:
                sources.append({
                    "document_id": doc.id,
                    "document_title": doc.title,
                    "chunk_id": chunk.id,
                    "relevance_score": score,
                    "section": chunk.parent_headers[0] if chunk.parent_headers else None,
                })
        
        return await self._save_and_return_query(
            config_id=config.id,
            user_id=user_id,
            query_text=query_text,
            response=response,
            classification=classification,
            confidence=confidence,
            sources=sources,
            start_time=start_time,
            conversation_id=conversation_id,
            parent_query_id=parent_query_id,
        )
    
    async def submit_feedback(
        self,
        query_id: str,
        rating: int | None = None,
        was_helpful: bool | None = None,
        feedback_text: str | None = None,
    ) -> ERPQuery | None:
        """
        Submit feedback for a query response.
        
        Args:
            query_id: Query to provide feedback for
            rating: 1-5 star rating
            was_helpful: Boolean helpfulness indicator
            feedback_text: Optional text feedback
            
        Returns:
            Updated ERPQuery or None
        """
        result = await self.session.execute(
            select(ERPQuery).where(
                and_(
                    ERPQuery.id == query_id,
                    ERPQuery.tenant_id == self.tenant_id,
                )
            )
        )
        query = result.scalar_one_or_none()
        if not query:
            return None
        
        if rating is not None:
            query.user_rating = rating
        if was_helpful is not None:
            query.was_helpful = was_helpful
        if feedback_text:
            query.user_feedback = feedback_text
        
        await self.session.flush()
        
        # If negative feedback, consider for documentation gap
        if rating and rating <= 2:
            await self._record_potential_gap(query)
        
        return query
    
    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> list[ERPQuery]:
        """Get conversation history."""
        result = await self.session.execute(
            select(ERPQuery)
            .where(
                and_(
                    ERPQuery.conversation_id == conversation_id,
                    ERPQuery.tenant_id == self.tenant_id,
                )
            )
            .order_by(ERPQuery.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_common_queries(
        self,
        module: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Get most common query patterns."""
        from sqlalchemy import func
        
        conditions = [ERPQuery.tenant_id == self.tenant_id]
        
        if module:
            conditions.append(ERPQuery.detected_entities["module"].astext == module)
        
        result = await self.session.execute(
            select(
                ERPQuery.query_category,
                func.count(ERPQuery.id).label("count"),
            )
            .where(and_(*conditions))
            .group_by(ERPQuery.query_category)
            .order_by(func.count(ERPQuery.id).desc())
            .limit(limit)
        )
        
        return [
            {"category": row.query_category.value if row.query_category else "other", "count": row.count}
            for row in result.all()
        ]
    
    # Query Templates
    
    async def create_query_template(
        self,
        name: str,
        query_patterns: list[str],
        response_template: str,
        category: QueryCategory | None = None,
        module: str | None = None,
        keywords: list[str] | None = None,
    ) -> ERPQueryTemplate:
        """Create a query template for common questions."""
        template = ERPQueryTemplate(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            name=name,
            query_patterns=query_patterns,
            response_template=response_template,
            category=category,
            module=module,
            keywords=keywords or [],
        )
        
        self.session.add(template)
        await self.session.flush()
        
        return template
    
    async def list_templates(
        self,
        category: QueryCategory | None = None,
        module: str | None = None,
    ) -> list[ERPQueryTemplate]:
        """List query templates."""
        conditions = [
            ERPQueryTemplate.tenant_id == self.tenant_id,
            ERPQueryTemplate.is_active == True,
        ]
        
        if category:
            conditions.append(ERPQueryTemplate.category == category)
        if module:
            conditions.append(ERPQueryTemplate.module == module)
        
        result = await self.session.execute(
            select(ERPQueryTemplate)
            .where(and_(*conditions))
            .order_by(ERPQueryTemplate.usage_count.desc())
        )
        
        return list(result.scalars().all())
    
    # Private methods
    
    async def _get_erp_config(self) -> ERPConfiguration | None:
        """Get ERP configuration."""
        result = await self.session.execute(
            select(ERPConfiguration).where(
                and_(
                    ERPConfiguration.tenant_id == self.tenant_id,
                    ERPConfiguration.is_active == True,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _classify_query(
        self,
        query_text: str,
        config: ERPConfiguration,
    ) -> dict[str, Any]:
        """Classify query intent and extract entities."""
        prompt = f"""
Classify this ERP query and extract relevant information.

ERP System: {config.erp_system.value}
Query: {query_text}

Provide:
1. category: One of [how_to, where_to_find, troubleshooting, configuration, reporting, data_entry, workflow, integration, permissions, other]
2. intent: Brief description of what user wants
3. module: ERP module this relates to (if identifiable)
4. entities: Any specific entities mentioned (screens, reports, fields, etc.)
"""
        
        schema = {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "intent": {"type": "string"},
                "module": {"type": "string"},
                "entities": {"type": "object"},
            },
        }
        
        return await ai_client.generate_structured(prompt, schema)
    
    async def _check_templates(
        self,
        query_text: str,
        config: ERPConfiguration,
    ) -> str | None:
        """Check if query matches any templates."""
        templates = await self.list_templates()
        
        query_lower = query_text.lower()
        
        for template in templates:
            # Check pattern matches
            for pattern in template.query_patterns:
                if pattern.lower() in query_lower:
                    # Update usage
                    template.usage_count += 1
                    template.last_used_at = datetime.utcnow()
                    
                    # Fill in variables
                    response = template.response_template
                    
                    # Replace common variables
                    if config.navigation_map:
                        for var, path in config.navigation_map.items():
                            response = response.replace(f"{{{var}}}", str(path))
                    
                    return response
        
        return None
    
    async def _generate_response(
        self,
        query_text: str,
        context_chunks: list[str],
        config: ERPConfiguration,
        classification: dict,
    ) -> str:
        """Generate response from documentation context."""
        prompt = prompt_builder.erp_query_prompt(
            query=query_text,
            erp_system=config.erp_system.value,
            context_chunks=context_chunks,
            custom_terminology=config.custom_terminology,
        )
        
        system_prompt = f"""You are an expert {config.erp_system.value} assistant.
Answer questions based on the provided documentation.
Be specific and actionable.
If the documentation doesn't cover the question, say so clearly.
Include menu paths and step numbers when available."""
        
        return await ai_client.generate_text(
            prompt,
            system_prompt=system_prompt,
            max_tokens=1000,
        )
    
    async def _handle_no_documentation(
        self,
        config: ERPConfiguration,
        user_id: str,
        query_text: str,
        classification: dict,
        start_time: float,
        conversation_id: str | None,
        parent_query_id: str | None,
    ) -> dict[str, Any]:
        """Handle queries with no matching documentation."""
        # Generate generic response
        response = f"""I couldn't find specific documentation for your question about "{query_text[:50]}..."

This might be because:
1. The topic isn't covered in the uploaded documentation
2. Different terminology might help find relevant information

You might want to:
- Try rephrasing your question
- Check the ERP system's built-in help
- Contact your system administrator

I've flagged this as a documentation gap for review."""
        
        # Record documentation gap
        await self._record_gap(
            topic=classification.get("intent", query_text[:100]),
            query=query_text,
            module=classification.get("module"),
            category=classification.get("category"),
        )
        
        return await self._save_and_return_query(
            config_id=config.id,
            user_id=user_id,
            query_text=query_text,
            response=response,
            classification=classification,
            was_fallback=True,
            fallback_reason="no_matching_documentation",
            start_time=start_time,
            conversation_id=conversation_id,
            parent_query_id=parent_query_id,
        )
    
    async def _save_and_return_query(
        self,
        config_id: str,
        user_id: str,
        query_text: str,
        response: str,
        classification: dict,
        start_time: float,
        confidence: float = 0.0,
        sources: list | None = None,
        was_template: bool = False,
        was_fallback: bool = False,
        fallback_reason: str | None = None,
        conversation_id: str | None = None,
        parent_query_id: str | None = None,
    ) -> dict[str, Any]:
        """Save query record and return response."""
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        query_category = None
        if classification.get("category"):
            try:
                query_category = QueryCategory(classification["category"])
            except ValueError:
                query_category = QueryCategory.OTHER
        
        query = ERPQuery(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            erp_config_id=config_id,
            user_id=user_id,
            query_text=query_text,
            query_category=query_category,
            detected_intent=classification.get("intent"),
            detected_entities=classification.get("entities", {}),
            response_text=response,
            response_sources=sources or [],
            confidence_score=confidence,
            was_fallback_used=was_fallback,
            fallback_reason=fallback_reason,
            response_time_ms=response_time_ms,
            is_follow_up=parent_query_id is not None,
            parent_query_id=parent_query_id,
            conversation_id=conversation_id or str(uuid4()),
        )
        
        self.session.add(query)
        await self.session.flush()
        
        self.logger.log_operation_complete(
            "process_query",
            tenant_id=self.tenant_id,
            query_id=query.id,
            response_time_ms=response_time_ms,
            was_fallback=was_fallback,
        )
        
        return {
            "query_id": query.id,
            "response": response,
            "confidence": confidence,
            "sources": sources or [],
            "conversation_id": query.conversation_id,
            "category": query_category.value if query_category else None,
            "was_fallback": was_fallback,
            "response_time_ms": response_time_ms,
            "success": True,
        }
    
    async def _record_gap(
        self,
        topic: str,
        query: str,
        module: str | None = None,
        category: str | None = None,
    ) -> None:
        """Record a documentation gap."""
        # Check for existing gap
        result = await self.session.execute(
            select(DocumentationGap).where(
                and_(
                    DocumentationGap.tenant_id == self.tenant_id,
                    DocumentationGap.topic == topic,
                    DocumentationGap.is_resolved == False,
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.query_count += 1
            existing.sample_queries = (existing.sample_queries or [])[:9] + [query]
            existing.last_reported_at = datetime.utcnow()
        else:
            gap = DocumentationGap(
                id=str(uuid4()),
                tenant_id=self.tenant_id,
                topic=topic,
                sample_queries=[query],
                module=module,
                severity="medium",
            )
            
            if category:
                try:
                    gap.category = QueryCategory(category)
                except ValueError:
                    pass
            
            self.session.add(gap)
        
        await self.session.flush()
    
    async def _record_potential_gap(self, query: ERPQuery) -> None:
        """Record potential gap from negative feedback."""
        await self._record_gap(
            topic=query.detected_intent or query.query_text[:100],
            query=query.query_text,
            module=query.detected_entities.get("module"),
            category=query.query_category.value if query.query_category else None,
        )
