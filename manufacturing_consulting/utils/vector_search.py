"""
Vector search utilities for semantic search across documents and parts.

Provides RAG (Retrieval Augmented Generation) capabilities.
"""

from typing import Any
import numpy as np
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Result from vector similarity search."""
    id: str
    content: str
    score: float
    metadata: dict[str, Any]


class VectorStore:
    """
    Simple in-memory vector store for semantic search.
    
    For production, integrate with ChromaDB, Pinecone, or pgvector.
    This implementation provides the interface and basic functionality.
    """
    
    def __init__(self, dimension: int = 1536):
        """
        Initialize vector store.
        
        Args:
            dimension: Embedding dimension (1536 for OpenAI embeddings)
        """
        self.dimension = dimension
        self.vectors: list[np.ndarray] = []
        self.documents: list[dict] = []
        self.ids: list[str] = []
    
    def add_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[dict],
    ) -> None:
        """
        Add documents with embeddings to the store.
        
        Args:
            ids: Unique identifiers for each document
            embeddings: Embedding vectors
            documents: Document metadata
        """
        for id_, embedding, doc in zip(ids, embeddings, documents):
            self.ids.append(id_)
            self.vectors.append(np.array(embedding))
            self.documents.append(doc)
    
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> list[SearchResult]:
        """
        Search for similar documents.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            threshold: Minimum similarity threshold
            
        Returns:
            List of search results sorted by relevance
        """
        if not self.vectors:
            return []
        
        query_vec = np.array(query_embedding)
        
        # Compute cosine similarities
        scores = []
        for vec in self.vectors:
            similarity = np.dot(query_vec, vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(vec)
            )
            scores.append(similarity)
        
        # Get top-k results
        indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in indices:
            score = scores[idx]
            if score >= threshold:
                results.append(SearchResult(
                    id=self.ids[idx],
                    content=self.documents[idx].get("content", ""),
                    score=float(score),
                    metadata=self.documents[idx],
                ))
        
        return results
    
    def delete(self, ids: list[str]) -> None:
        """Remove documents by ID."""
        indices_to_remove = [i for i, id_ in enumerate(self.ids) if id_ in ids]
        for idx in sorted(indices_to_remove, reverse=True):
            del self.vectors[idx]
            del self.documents[idx]
            del self.ids[idx]
    
    def clear(self) -> None:
        """Clear all documents from the store."""
        self.vectors = []
        self.documents = []
        self.ids = []


class TenantVectorStore:
    """
    Multi-tenant vector store manager.
    
    Maintains separate vector stores per tenant for data isolation.
    """
    
    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        self._stores: dict[str, dict[str, VectorStore]] = {}
    
    def get_store(self, tenant_id: str, collection: str) -> VectorStore:
        """
        Get or create a vector store for a tenant and collection.
        
        Args:
            tenant_id: Tenant identifier
            collection: Collection name (e.g., 'parts', 'erp_docs')
            
        Returns:
            VectorStore instance
        """
        if tenant_id not in self._stores:
            self._stores[tenant_id] = {}
        
        if collection not in self._stores[tenant_id]:
            self._stores[tenant_id][collection] = VectorStore(self.dimension)
        
        return self._stores[tenant_id][collection]
    
    def delete_tenant(self, tenant_id: str) -> None:
        """Remove all stores for a tenant."""
        if tenant_id in self._stores:
            del self._stores[tenant_id]


class TextChunker:
    """
    Utility for chunking documents for embedding.
    
    Supports various chunking strategies for optimal retrieval.
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separator: str = "\n\n",
    ):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
            separator: Primary separator for splitting
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator
    
    def chunk_text(self, text: str) -> list[dict]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of chunk dictionaries with content and position info
        """
        # Split by separator first
        paragraphs = text.split(self.separator)
        
        chunks = []
        current_chunk = ""
        current_start = 0
        
        for para in paragraphs:
            if len(current_chunk) + len(para) <= self.chunk_size:
                current_chunk += para + self.separator
            else:
                if current_chunk:
                    chunks.append({
                        "content": current_chunk.strip(),
                        "start_position": current_start,
                        "end_position": current_start + len(current_chunk),
                    })
                    # Start new chunk with overlap
                    overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                    current_start = current_start + len(current_chunk) - len(overlap_text)
                    current_chunk = overlap_text + para + self.separator
                else:
                    current_chunk = para + self.separator
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "start_position": current_start,
                "end_position": current_start + len(current_chunk),
            })
        
        # Add chunk indices
        for i, chunk in enumerate(chunks):
            chunk["chunk_index"] = i
        
        return chunks
    
    def chunk_with_headers(
        self,
        text: str,
        header_pattern: str = r"^#+\s+.+$",
    ) -> list[dict]:
        """
        Chunk text while preserving header context.
        
        Args:
            text: Text to chunk
            header_pattern: Regex pattern for headers
            
        Returns:
            List of chunks with parent header information
        """
        import re
        
        lines = text.split("\n")
        chunks = []
        current_headers: list[str] = []
        current_content = ""
        current_start = 0
        
        for line in lines:
            if re.match(header_pattern, line):
                # Save current chunk if exists
                if current_content.strip():
                    chunks.append({
                        "content": current_content.strip(),
                        "parent_headers": current_headers.copy(),
                        "start_position": current_start,
                    })
                
                # Update headers
                header_level = len(line) - len(line.lstrip("#"))
                # Trim headers to current level
                current_headers = current_headers[:header_level - 1]
                current_headers.append(line.strip("# ").strip())
                
                current_content = ""
                current_start = 0
            else:
                current_content += line + "\n"
        
        # Don't forget final chunk
        if current_content.strip():
            chunks.append({
                "content": current_content.strip(),
                "parent_headers": current_headers.copy(),
                "start_position": current_start,
            })
        
        # Add indices
        for i, chunk in enumerate(chunks):
            chunk["chunk_index"] = i
        
        return chunks


# Global instances
tenant_vector_store = TenantVectorStore()
text_chunker = TextChunker()
