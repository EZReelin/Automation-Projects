"""
Parts catalog management service.

Handles CRUD operations and search for manufacturing parts.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.quote_intelligence import Part, PartSimilarity, PartCategory
from utils.logging import ServiceLogger
from utils.ai_client import ai_client
from utils.vector_search import tenant_vector_store


class PartsService:
    """
    Service for managing manufacturing parts catalog.
    
    Provides:
    - CRUD operations for parts
    - Full-text and semantic search
    - Part categorization and tagging
    - Embedding generation for similarity matching
    """
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("parts")
    
    async def create_part(
        self,
        part_number: str,
        name: str,
        description: str | None = None,
        category: PartCategory = PartCategory.COMPONENT,
        **kwargs: Any,
    ) -> Part:
        """
        Create a new part in the catalog.
        
        Args:
            part_number: Unique part identifier
            name: Part name/title
            description: Detailed description
            category: Part category
            **kwargs: Additional part attributes
            
        Returns:
            Created Part instance
        """
        self.logger.log_operation_start(
            "create_part",
            tenant_id=self.tenant_id,
            part_number=part_number,
        )
        
        part = Part(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            part_number=part_number,
            name=name,
            description=description,
            category=category,
            **kwargs,
        )
        
        self.session.add(part)
        await self.session.flush()
        
        # Generate embedding for similarity search
        if description:
            await self._generate_part_embedding(part)
        
        self.logger.log_operation_complete(
            "create_part",
            tenant_id=self.tenant_id,
            part_id=part.id,
        )
        
        return part
    
    async def get_part(self, part_id: str) -> Part | None:
        """Get a part by ID."""
        result = await self.session.execute(
            select(Part).where(
                and_(
                    Part.id == part_id,
                    Part.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_part_by_number(
        self,
        part_number: str,
        revision: str = "A",
    ) -> Part | None:
        """Get a part by part number and revision."""
        result = await self.session.execute(
            select(Part).where(
                and_(
                    Part.part_number == part_number,
                    Part.revision == revision,
                    Part.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def update_part(
        self,
        part_id: str,
        **updates: Any,
    ) -> Part | None:
        """
        Update a part's attributes.
        
        Args:
            part_id: Part ID to update
            **updates: Attributes to update
            
        Returns:
            Updated Part or None if not found
        """
        part = await self.get_part(part_id)
        if not part:
            return None
        
        for key, value in updates.items():
            if hasattr(part, key):
                setattr(part, key, value)
        
        part.updated_at = datetime.utcnow()
        
        # Regenerate embedding if description changed
        if "description" in updates:
            await self._generate_part_embedding(part)
        
        await self.session.flush()
        return part
    
    async def delete_part(self, part_id: str) -> bool:
        """
        Delete a part (soft delete by marking inactive).
        
        Args:
            part_id: Part ID to delete
            
        Returns:
            True if deleted successfully
        """
        part = await self.get_part(part_id)
        if not part:
            return False
        
        part.is_active = False
        part.updated_at = datetime.utcnow()
        
        await self.session.flush()
        return True
    
    async def search_parts(
        self,
        query: str | None = None,
        category: PartCategory | None = None,
        tags: list[str] | None = None,
        is_active: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Part], int]:
        """
        Search parts with filters.
        
        Args:
            query: Text search query
            category: Filter by category
            tags: Filter by tags
            is_active: Filter by active status
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            Tuple of (parts list, total count)
        """
        conditions = [
            Part.tenant_id == self.tenant_id,
            Part.is_active == is_active,
        ]
        
        if category:
            conditions.append(Part.category == category)
        
        if tags:
            conditions.append(Part.tags.overlap(tags))
        
        if query:
            # Full-text search on multiple fields
            search_pattern = f"%{query}%"
            conditions.append(
                or_(
                    Part.part_number.ilike(search_pattern),
                    Part.name.ilike(search_pattern),
                    Part.description.ilike(search_pattern),
                    Part.alternate_part_numbers.any(query),
                )
            )
        
        # Get total count
        count_query = select(func.count(Part.id)).where(and_(*conditions))
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()
        
        # Get parts
        parts_query = (
            select(Part)
            .where(and_(*conditions))
            .order_by(Part.part_number)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(parts_query)
        parts = result.scalars().all()
        
        return list(parts), total
    
    async def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.7,
    ) -> list[tuple[Part, float]]:
        """
        Search parts using semantic similarity.
        
        Args:
            query: Natural language search query
            top_k: Number of results
            threshold: Minimum similarity threshold
            
        Returns:
            List of (Part, similarity_score) tuples
        """
        self.logger.log_operation_start(
            "semantic_search",
            tenant_id=self.tenant_id,
            query=query[:100],
        )
        
        # Generate query embedding
        query_embedding = await ai_client.generate_single_embedding(query)
        
        # Search vector store
        vector_store = tenant_vector_store.get_store(self.tenant_id, "parts")
        results = vector_store.search(query_embedding, top_k=top_k, threshold=threshold)
        
        # Fetch full part objects
        parts_with_scores = []
        for result in results:
            part = await self.get_part(result.id)
            if part and part.is_active:
                parts_with_scores.append((part, result.score))
        
        self.logger.log_operation_complete(
            "semantic_search",
            tenant_id=self.tenant_id,
            results_count=len(parts_with_scores),
        )
        
        return parts_with_scores
    
    async def bulk_import(
        self,
        parts_data: list[dict],
        update_existing: bool = False,
    ) -> dict[str, int]:
        """
        Bulk import parts from external data.
        
        Args:
            parts_data: List of part dictionaries
            update_existing: Whether to update existing parts
            
        Returns:
            Summary dict with created/updated/skipped counts
        """
        self.logger.log_operation_start(
            "bulk_import",
            tenant_id=self.tenant_id,
            count=len(parts_data),
        )
        
        created = 0
        updated = 0
        skipped = 0
        
        for data in parts_data:
            part_number = data.get("part_number")
            if not part_number:
                skipped += 1
                continue
            
            existing = await self.get_part_by_number(
                part_number,
                data.get("revision", "A"),
            )
            
            if existing:
                if update_existing:
                    await self.update_part(existing.id, **data)
                    updated += 1
                else:
                    skipped += 1
            else:
                await self.create_part(**data)
                created += 1
        
        self.logger.log_operation_complete(
            "bulk_import",
            tenant_id=self.tenant_id,
            created=created,
            updated=updated,
            skipped=skipped,
        )
        
        return {"created": created, "updated": updated, "skipped": skipped}
    
    async def _generate_part_embedding(self, part: Part) -> None:
        """Generate and store embedding for a part."""
        # Create text for embedding
        text_parts = [part.name]
        if part.description:
            text_parts.append(part.description)
        if part.tags:
            text_parts.extend(part.tags)
        
        text = " ".join(text_parts)
        
        try:
            embedding = await ai_client.generate_single_embedding(text)
            
            # Store in vector store
            vector_store = tenant_vector_store.get_store(self.tenant_id, "parts")
            vector_store.add_documents(
                ids=[part.id],
                embeddings=[embedding],
                documents=[{
                    "content": text,
                    "part_number": part.part_number,
                    "name": part.name,
                    "category": part.category.value if part.category else None,
                }],
            )
        except Exception as e:
            self.logger.log_operation_failed(
                "generate_embedding",
                e,
                tenant_id=self.tenant_id,
                part_id=part.id,
            )
    
    async def get_categories_summary(self) -> dict[str, int]:
        """Get count of parts by category."""
        result = await self.session.execute(
            select(Part.category, func.count(Part.id))
            .where(
                and_(
                    Part.tenant_id == self.tenant_id,
                    Part.is_active == True,
                )
            )
            .group_by(Part.category)
        )
        return {row[0].value: row[1] for row in result.all()}
