# enhanced_memory.py
# Enhanced memory system for context management between models

import os
import json
import uuid
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from pathlib import Path

try:
    from sentence_transformers import SentenceTransformer
    VECTOR_ENABLED = True
except ImportError:
    VECTOR_ENABLED = False
    print("Warning: sentence_transformers not installed. Falling back to keyword-based retrieval.")

class MemoryChunk:
    """Represents a chunk of information stored in memory."""
    
    def __init__(self, 
                text: str, 
                metadata: Dict[str, Any],
                embedding: Optional[List[float]] = None,
                expiry: Optional[datetime] = None):
        """Initialize a memory chunk.
        
        Args:
            text: Text content of the chunk
            metadata: Metadata about the chunk (source, timestamp, etc.)
            embedding: Vector embedding of the chunk (if available)
            expiry: Expiration time for this chunk (if applicable)
        """
        self.id = str(uuid.uuid4())
        self.text = text
        self.metadata = metadata
        self.embedding = embedding
        self.created_at = datetime.now()
        self.expiry = expiry or (self.created_at + timedelta(days=1))
        
        # Generate keywords for keyword-based retrieval fallback
        self.keywords = self._extract_keywords(text)
        
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text for non-vector retrieval.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of keywords
        """
        # Simple keyword extraction - split by space and remove common words
        common_words = {"the", "a", "an", "in", "on", "at", "to", "for", "with", "by", "from"}
        words = text.lower().split()
        return [word for word in words if word not in common_words and len(word) > 3]
        
    def is_expired(self) -> bool:
        """Check if this chunk has expired.
        
        Returns:
            True if chunk has expired, False otherwise
        """
        return datetime.now() > self.expiry
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.
        
        Returns:
            Dictionary representation of the chunk
        """
        return {
            "id": self.id,
            "text": self.text,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "expiry": self.expiry.isoformat(),
            "keywords": self.keywords
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryChunk':
        """Create from dictionary representation.
        
        Args:
            data: Dictionary representation of a chunk
            
        Returns:
            New MemoryChunk instance
        """
        chunk = cls(
            text=data["text"],
            metadata=data["metadata"]
        )
        chunk.id = data["id"]
        chunk.created_at = datetime.fromisoformat(data["created_at"])
        chunk.expiry = datetime.fromisoformat(data["expiry"])
        chunk.keywords = data["keywords"]
        return chunk


class ResultCache:
    """Cache for model outputs to avoid repeated API calls."""
    
    def __init__(self, ttl_seconds: int = 3600):
        """Initialize the result cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.cache = {}
        self.ttl_seconds = ttl_seconds
        
    def _generate_key(self, task: str, input_data: str) -> str:
        """Generate a unique key for the cache.
        
        Args:
            task: Task name
            input_data: Input data for the task
            
        Returns:
            Cache key
        """
        content = f"{task}:{input_data}"
        return hashlib.md5(content.encode()).hexdigest()
        
    def get(self, task: str, input_data: str) -> Optional[str]:
        """Get cached result if available and not expired.
        
        Args:
            task: Task name
            input_data: Input data for the task
            
        Returns:
            Cached result or None if not found/expired
        """
        key = self._generate_key(task, input_data)
        if key in self.cache:
            entry = self.cache[key]
            if datetime.now() < entry["expiry"]:
                return entry["result"]
            else:
                # Clean up expired entry
                del self.cache[key]
        return None
        
    def set(self, task: str, input_data: str, result: str) -> None:
        """Set a result in the cache.
        
        Args:
            task: Task name
            input_data: Input data for the task
            result: Result to cache
        """
        key = self._generate_key(task, input_data)
        expiry = datetime.now() + timedelta(seconds=self.ttl_seconds)
        self.cache[key] = {
            "result": result,
            "expiry": expiry
        }
        
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache = {}


class EnhancedMemorySystem:
    """Enhanced memory system with vector storage and smart retrieval."""
    
    def __init__(self, 
                config: Dict[str, Any],
                workspace_dir: str = "./workspace"):
        """Initialize the enhanced memory system.
        
        Args:
            config: Memory system configuration
            workspace_dir: Directory for storing memory files
        """
        self.config = config
        self.workspace_dir = workspace_dir
        self.chunk_size = config.get("chunk_size", 1000)
        self.overlap = config.get("overlap", 100)
        self.vector_config = config.get("vector_db", {})
        
        # Initialize cache
        cache_config = config.get("cache", {})
        self.cache = ResultCache(ttl_seconds=cache_config.get("ttl_seconds", 3600))
        
        # Initialize chunks storage
        self.chunks = []
        
        # Initialize vector model if available
        self.embedding_model = None
        if VECTOR_ENABLED and self.vector_config.get("embedding_model"):
            try:
                model_name = self.vector_config.get("embedding_model")
                self.embedding_model = SentenceTransformer(model_name)
                print(f"Initialized embedding model: {model_name}")
            except Exception as e:
                print(f"Error initializing embedding model: {str(e)}")
                self.embedding_model = None
                
        # Create workspace directory if it doesn't exist
        os.makedirs(workspace_dir, exist_ok=True)
        
        # Model-specific context sizes for optimizing retrieval
        self.model_context_sizes = {
            "deepseek/deepseek-chat-v3-0324:free": 128000,
            "google/gemma-3-27b-it-128k:free": 128000,
            "google/gemini-2.5-pro-exp-03-25:free": 1000000,
            "google/gemma-3-27b-chat:free": 12000,
            "meta-llama/llama-guard-3-8b": 8000
        }
                
    def _split_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks.
        
        Args:
            text: Text to split
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
            
        words = text.split()
        if len(words) <= self.chunk_size:
            return [text]
            
        chunks = []
        for i in range(0, len(words), self.chunk_size - self.overlap):
            chunk = " ".join(words[i:i + self.chunk_size])
            chunks.append(chunk)
            
        return chunks
        
    def _create_embedding(self, text: str) -> Optional[List[float]]:
        """Create embedding for text if model is available.
        
        Args:
            text: Text to create embedding for
            
        Returns:
            Embedding vector or None if not available
        """
        if not self.embedding_model:
            return None
            
        try:
            embedding = self.embedding_model.encode(text)
            return embedding.tolist()
        except Exception as e:
            print(f"Error creating embedding: {str(e)}")
            return None
            
    def add_document(self, 
                    document: str, 
                    metadata: Dict[str, Any]) -> None:
        """Add a document to memory, splitting into chunks.
        
        Args:
            document: Document text
            metadata: Document metadata
        """
        chunks = self._split_text(document)
        
        for chunk in chunks:
            embedding = self._create_embedding(chunk)
            memory_chunk = MemoryChunk(
                text=chunk,
                metadata=metadata,
                embedding=embedding
            )
            self.chunks.append(memory_chunk)
            
        # Remove expired chunks
        self.chunks = [chunk for chunk in self.chunks if not chunk.is_expired()]
        
        # Save memory to disk
        self._save_memory()
            
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity (0-1)
        """
        if not vec1 or not vec2:
            return 0.0
            
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return dot_product / (norm1 * norm2)
            
    def _keyword_similarity(self, query: str, chunk: MemoryChunk) -> float:
        """Calculate keyword-based similarity as fallback.
        
        Args:
            query: Query text
            chunk: Memory chunk
            
        Returns:
            Similarity score (0-1)
        """
        query_keywords = set(self._extract_keywords(query))
        chunk_keywords = set(chunk.keywords)
        
        if not query_keywords or not chunk_keywords:
            return 0.0
            
        intersection = query_keywords.intersection(chunk_keywords)
        return len(intersection) / max(len(query_keywords), len(chunk_keywords))
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of keywords
        """
        common_words = {"the", "a", "an", "in", "on", "at", "to", "for", "with", "by", "from"}
        words = text.lower().split()
        return [word for word in words if word not in common_words and len(word) > 3]
            
    def get_relevant_context(self, 
                           query: str, 
                           max_chunks: int = 3,
                           task: Optional[str] = None,
                           model: Optional[str] = None) -> str:
        """Get the most relevant context for a query.
        
        Args:
            query: Query text
            max_chunks: Maximum number of chunks to include
            task: Task name for context filtering
            model: Model name for context window optimization
            
        Returns:
            Relevant context text
        """
        if not self.chunks:
            return ""
        
        # Adjust max_chunks based on model's context window if provided
        if model and model in self.model_context_sizes:
            context_size = self.model_context_sizes[model]
            # For very large context models like Phi-3, allow more chunks
            if context_size > 32000:  # For extremely large context windows
                max_chunks = max(max_chunks, 12)
            elif context_size > 8000:  # For large context windows
                max_chunks = max(max_chunks, 6)
            
        query_embedding = self._create_embedding(query)
        
        # Calculate similarities
        similarities = []
        for chunk in self.chunks:
            # Filter by task if specified
            if task and chunk.metadata.get("task") != task:
                continue
                
            # Use vector similarity if available
            if query_embedding and chunk.embedding:
                similarity = self._cosine_similarity(query_embedding, chunk.embedding)
            else:
                # Fall back to keyword similarity
                similarity = self._keyword_similarity(query, chunk)
                
            similarities.append((chunk, similarity))
            
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Take top chunks
        top_chunks = [chunk for chunk, sim in similarities[:max_chunks] if sim > self.vector_config.get("similarity_threshold", 0.5)]
        
        # Combine chunks into context
        if not top_chunks:
            return ""
            
        context = "\n\n".join([chunk.text for chunk in top_chunks])
        return context
    
    def _save_memory(self) -> None:
        """Save memory to disk."""
        memory_file = os.path.join(self.workspace_dir, "memory.json")
        
        # Convert chunks to serializable form
        serialized_chunks = [chunk.to_dict() for chunk in self.chunks]
        
        with open(memory_file, 'w') as f:
            json.dump(serialized_chunks, f, indent=2)
            
    def _load_memory(self) -> None:
        """Load memory from disk if available."""
        memory_file = os.path.join(self.workspace_dir, "memory.json")
        
        if not os.path.exists(memory_file):
            return
            
        try:
            with open(memory_file, 'r') as f:
                serialized_chunks = json.load(f)
                
            self.chunks = [MemoryChunk.from_dict(data) for data in serialized_chunks]
            
            # Re-compute embeddings if model is available
            if self.embedding_model:
                for chunk in self.chunks:
                    if not chunk.embedding:
                        chunk.embedding = self._create_embedding(chunk.text)
        except Exception as e:
            print(f"Error loading memory: {str(e)}")
