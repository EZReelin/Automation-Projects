"""
Parts matching service with manufacturing nomenclature support.

Handles fuzzy matching, synonym detection, and similar parts identification.
"""

import re
from typing import Any
from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.quote_intelligence import Part, PartSimilarity
from utils.logging import ServiceLogger
from utils.ai_client import ai_client
from utils.vector_search import tenant_vector_store
from config.settings import settings


@dataclass
class MatchResult:
    """Result of a part matching operation."""
    part: Part
    score: float
    match_type: str  # exact, fuzzy, semantic, alternate
    match_reasons: list[str]


class PartMatchingService:
    """
    Service for matching and finding similar parts.
    
    Handles:
    - Exact matching by part number
    - Fuzzy matching for nomenclature variations
    - Semantic matching using embeddings
    - Alternate part number lookup
    - Manufacturer cross-reference
    """
    
    # Common manufacturing abbreviations and variations
    MANUFACTURING_SYNONYMS = {
        "ss": ["stainless steel", "stainless", "304", "316"],
        "al": ["aluminum", "aluminium", "alu"],
        "brz": ["bronze"],
        "brs": ["brass"],
        "cs": ["carbon steel", "mild steel"],
        "hex": ["hexagonal", "hexagon"],
        "sq": ["square"],
        "rd": ["round"],
        "flg": ["flange", "flanged"],
        "thd": ["thread", "threaded"],
        "assy": ["assembly", "asm"],
        "mach": ["machined", "machining"],
        "plat": ["plated", "plating"],
        "hdw": ["hardware"],
        "brg": ["bearing"],
        "bsh": ["bushing", "bush"],
        "spc": ["spacer"],
        "wshr": ["washer"],
        "nut": ["nut"],
        "scr": ["screw"],
        "blt": ["bolt"],
        "pn": ["pin"],
        "shft": ["shaft"],
        "od": ["outside diameter", "outer diameter"],
        "id": ["inside diameter", "inner diameter"],
    }
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("part_matching")
        self.similarity_threshold = settings.quote_intelligence.similarity_threshold
        self.max_results = settings.quote_intelligence.max_similar_parts
    
    async def find_matches(
        self,
        query: str,
        limit: int | None = None,
    ) -> list[MatchResult]:
        """
        Find matching parts using multiple strategies.
        
        Args:
            query: Part number, description, or search term
            limit: Maximum number of results
            
        Returns:
            List of MatchResults sorted by relevance
        """
        limit = limit or self.max_results
        self.logger.log_operation_start(
            "find_matches",
            tenant_id=self.tenant_id,
            query=query[:100],
        )
        
        all_matches: list[MatchResult] = []
        seen_ids: set[str] = set()
        
        # Strategy 1: Exact match
        exact_matches = await self._exact_match(query)
        for match in exact_matches:
            if match.part.id not in seen_ids:
                all_matches.append(match)
                seen_ids.add(match.part.id)
        
        # Strategy 2: Alternate part number match
        alt_matches = await self._alternate_number_match(query)
        for match in alt_matches:
            if match.part.id not in seen_ids:
                all_matches.append(match)
                seen_ids.add(match.part.id)
        
        # Strategy 3: Fuzzy match
        fuzzy_matches = await self._fuzzy_match(query)
        for match in fuzzy_matches:
            if match.part.id not in seen_ids:
                all_matches.append(match)
                seen_ids.add(match.part.id)
        
        # Strategy 4: Semantic match
        semantic_matches = await self._semantic_match(query)
        for match in semantic_matches:
            if match.part.id not in seen_ids:
                all_matches.append(match)
                seen_ids.add(match.part.id)
        
        # Sort by score and limit
        all_matches.sort(key=lambda x: x.score, reverse=True)
        
        self.logger.log_operation_complete(
            "find_matches",
            tenant_id=self.tenant_id,
            total_matches=len(all_matches),
        )
        
        return all_matches[:limit]
    
    async def _exact_match(self, query: str) -> list[MatchResult]:
        """Find exact matches by part number."""
        # Normalize query
        normalized = self._normalize_part_number(query)
        
        result = await self.session.execute(
            select(Part).where(
                and_(
                    Part.tenant_id == self.tenant_id,
                    Part.is_active == True,
                    Part.part_number.ilike(normalized),
                )
            )
        )
        parts = result.scalars().all()
        
        return [
            MatchResult(
                part=part,
                score=1.0,
                match_type="exact",
                match_reasons=["Exact part number match"],
            )
            for part in parts
        ]
    
    async def _alternate_number_match(self, query: str) -> list[MatchResult]:
        """Find matches in alternate part numbers."""
        normalized = self._normalize_part_number(query)
        
        result = await self.session.execute(
            select(Part).where(
                and_(
                    Part.tenant_id == self.tenant_id,
                    Part.is_active == True,
                    Part.alternate_part_numbers.any(normalized),
                )
            )
        )
        parts = result.scalars().all()
        
        return [
            MatchResult(
                part=part,
                score=0.95,
                match_type="alternate",
                match_reasons=["Match found in alternate part numbers"],
            )
            for part in parts
        ]
    
    async def _fuzzy_match(self, query: str) -> list[MatchResult]:
        """Find fuzzy matches using string similarity."""
        normalized = self._normalize_part_number(query)
        expanded = self._expand_abbreviations(query)
        
        # Get candidate parts
        result = await self.session.execute(
            select(Part).where(
                and_(
                    Part.tenant_id == self.tenant_id,
                    Part.is_active == True,
                )
            ).limit(1000)  # Limit candidates for performance
        )
        parts = result.scalars().all()
        
        matches = []
        for part in parts:
            # Calculate similarity scores
            pn_similarity = self._calculate_similarity(
                normalized,
                self._normalize_part_number(part.part_number),
            )
            
            name_similarity = self._calculate_similarity(
                expanded.lower(),
                part.name.lower(),
            )
            
            desc_similarity = 0.0
            if part.description:
                desc_similarity = self._calculate_similarity(
                    expanded.lower(),
                    part.description.lower(),
                )
            
            # Combined score with weights
            score = max(
                pn_similarity * 0.9,  # Part number match weighted high
                name_similarity * 0.7,
                desc_similarity * 0.5,
            )
            
            if score >= self.similarity_threshold:
                reasons = []
                if pn_similarity >= self.similarity_threshold:
                    reasons.append(f"Part number similarity: {pn_similarity:.0%}")
                if name_similarity >= self.similarity_threshold:
                    reasons.append(f"Name similarity: {name_similarity:.0%}")
                if desc_similarity >= self.similarity_threshold:
                    reasons.append(f"Description similarity: {desc_similarity:.0%}")
                
                matches.append(MatchResult(
                    part=part,
                    score=score,
                    match_type="fuzzy",
                    match_reasons=reasons,
                ))
        
        return sorted(matches, key=lambda x: x.score, reverse=True)
    
    async def _semantic_match(self, query: str) -> list[MatchResult]:
        """Find matches using semantic similarity."""
        try:
            # Generate query embedding
            query_embedding = await ai_client.generate_single_embedding(query)
            
            # Search vector store
            vector_store = tenant_vector_store.get_store(self.tenant_id, "parts")
            results = vector_store.search(
                query_embedding,
                top_k=self.max_results,
                threshold=self.similarity_threshold,
            )
            
            matches = []
            for result in results:
                part_result = await self.session.execute(
                    select(Part).where(
                        and_(
                            Part.id == result.id,
                            Part.tenant_id == self.tenant_id,
                            Part.is_active == True,
                        )
                    )
                )
                part = part_result.scalar_one_or_none()
                
                if part:
                    matches.append(MatchResult(
                        part=part,
                        score=result.score * 0.85,  # Slightly lower weight for semantic
                        match_type="semantic",
                        match_reasons=[f"Semantic similarity: {result.score:.0%}"],
                    ))
            
            return matches
            
        except Exception as e:
            self.logger.log_operation_failed(
                "semantic_match",
                e,
                tenant_id=self.tenant_id,
            )
            return []
    
    def _normalize_part_number(self, part_number: str) -> str:
        """Normalize part number for comparison."""
        # Remove common separators and standardize
        normalized = part_number.upper()
        normalized = re.sub(r'[-_\s.]+', '', normalized)
        return normalized
    
    def _expand_abbreviations(self, text: str) -> str:
        """Expand manufacturing abbreviations."""
        expanded = text.lower()
        
        for abbr, expansions in self.MANUFACTURING_SYNONYMS.items():
            # Create pattern for whole word match
            pattern = rf'\b{re.escape(abbr)}\b'
            if re.search(pattern, expanded):
                # Add first expansion
                expanded = re.sub(pattern, expansions[0], expanded)
        
        return expanded
    
    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity ratio."""
        return SequenceMatcher(None, s1, s2).ratio()
    
    async def compute_part_similarities(
        self,
        part_id: str,
        threshold: float | None = None,
    ) -> list[PartSimilarity]:
        """
        Compute and store similarity relationships for a part.
        
        Args:
            part_id: Part to compute similarities for
            threshold: Minimum similarity threshold
            
        Returns:
            List of created PartSimilarity records
        """
        threshold = threshold or self.similarity_threshold
        
        # Get the source part
        part_result = await self.session.execute(
            select(Part).where(
                and_(
                    Part.id == part_id,
                    Part.tenant_id == self.tenant_id,
                )
            )
        )
        source_part = part_result.scalar_one_or_none()
        if not source_part:
            return []
        
        # Find similar parts
        search_text = f"{source_part.name} {source_part.description or ''}"
        matches = await self.find_matches(search_text, limit=20)
        
        similarities = []
        for match in matches:
            if match.part.id != part_id and match.score >= threshold:
                similarity = PartSimilarity(
                    tenant_id=self.tenant_id,
                    part_id=part_id,
                    similar_part_id=match.part.id,
                    similarity_score=match.score,
                    match_type=match.match_type,
                    match_reasons=match.match_reasons,
                )
                self.session.add(similarity)
                similarities.append(similarity)
        
        await self.session.flush()
        return similarities
    
    async def get_similar_parts(
        self,
        part_id: str,
        limit: int = 10,
    ) -> list[tuple[Part, float]]:
        """
        Get pre-computed similar parts for a given part.
        
        Args:
            part_id: Part ID to find similarities for
            limit: Maximum results
            
        Returns:
            List of (Part, similarity_score) tuples
        """
        result = await self.session.execute(
            select(PartSimilarity, Part)
            .join(Part, Part.id == PartSimilarity.similar_part_id)
            .where(
                and_(
                    PartSimilarity.part_id == part_id,
                    PartSimilarity.tenant_id == self.tenant_id,
                    Part.is_active == True,
                )
            )
            .order_by(PartSimilarity.similarity_score.desc())
            .limit(limit)
        )
        
        return [
            (row.Part, float(row.PartSimilarity.similarity_score))
            for row in result.all()
        ]
