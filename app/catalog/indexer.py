# app/catalog/indexer.py
import json
import hashlib
from typing import List, Dict, Optional, Tuple, Callable
import numpy as np
from pathlib import Path

from ..config import config
from ..logger import get_logger
from ..exceptions import IndexError

logger = get_logger(__name__)


class CatalogIndexer:
    """Build and manage FAISS vector index for catalog"""
    
    def __init__(self):
        self._model = None
        self._index = None
        self._items: List[Dict] = []
        self._embeddings: Optional[np.ndarray] = None
        self._dimension = 384
        self._use_fallback = False
    
    def _get_model(self):
        """Lazy load sentence transformer model with fallback"""
        if self._model is None and not self._use_fallback:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
                self._dimension = self._model.get_sentence_embedding_dimension()
                logger.info("Sentence transformer model loaded successfully")
            except ImportError as e:
                logger.warning(f"sentence-transformers not installed: {e}")
                self._use_fallback = True
            except Exception as e:
                logger.warning(f"Failed to load sentence transformer: {e}")
                self._use_fallback = True
        
        return self._model
    
    def _get_fallback_embedding(self, text: str) -> np.ndarray:
        """Generate a simple fallback embedding using hash-based approach"""
        # Create a deterministic embedding from text
        hash_obj = hashlib.md5(text.encode('utf-8'))
        hash_bytes = hash_obj.digest()
        
        # Convert to numpy array
        embedding = np.frombuffer(hash_bytes, dtype=np.uint8).astype(np.float32)
        
        # Pad or truncate to match dimension
        if len(embedding) < self._dimension:
            embedding = np.pad(embedding, (0, self._dimension - len(embedding)))
        else:
            embedding = embedding[:self._dimension]
        
        # Normalize
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
        return embedding
    
    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """Get embeddings with fallback mechanism"""
        if self._use_fallback or self._model is None:
            logger.info("Using fallback embedding method")
            embeddings = []
            for text in texts:
                emb = self._get_fallback_embedding(text)
                embeddings.append(emb)
            return np.array(embeddings).astype('float32')
        
        try:
            embeddings = self._model.encode(texts, show_progress_bar=False)
            return np.array(embeddings).astype('float32')
        except Exception as e:
            logger.error(f"Model encoding failed: {e}, using fallback")
            self._use_fallback = True
            return self._get_embeddings(texts)
    
    def build_index(self, catalog_data: List[Dict]) -> None:
        """Build FAISS index from catalog data"""
        if not catalog_data:
            logger.warning("No catalog data to index")
            return
        
        logger.info(f"Building index for {len(catalog_data)} items")
        
        # Prepare texts
        texts = []
        self._items = []
        
        for item in catalog_data:
            text_parts = [
                item.get('name', ''),
                item.get('description', ''),
                ' '.join(item.get('keys', [])),
                ' '.join(item.get('job_levels', [])),
            ]
            text = ' '.join([p for p in text_parts if p])
            texts.append(text)
            self._items.append(item)
        
        # Get embeddings
        embeddings = self._get_embeddings(texts)
        self._embeddings = embeddings
        
        # Build FAISS index
        try:
            import faiss
            self._index = faiss.IndexFlatL2(self._dimension)
            self._index.add(embeddings)
            logger.info(f"Index built with {self._index.ntotal} vectors")
        except ImportError as e:
            logger.warning(f"FAISS not installed: {e}, using simple search")
            self._index = None
    
    def save_index(self) -> None:
        """Save index and metadata to disk"""
        if self._index is None and self._embeddings is None:
            logger.warning("No index to save")
            return
        
        try:
            # Ensure directory exists
            index_path = Path(config.index_path)
            index_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save items metadata
            with open(f"{config.index_path}.json", 'w', encoding='utf-8') as f:
                json.dump(self._items, f, indent=2, ensure_ascii=False)
            
            # Save embeddings as numpy array
            if self._embeddings is not None:
                np.save(f"{config.index_path}.npy", self._embeddings)
            
            # Save FAISS index if available
            if self._index is not None:
                try:
                    import faiss
                    faiss.write_index(self._index, f"{config.index_path}.faiss")
                except ImportError:
                    pass
            
            logger.info(f"Index saved to {config.index_path}")
            
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
            raise IndexError(f"Index save failed: {e}")
    
    def load_index(self) -> bool:
        """Load index from disk"""
        try:
            items_file = f"{config.index_path}.json"
            embeddings_file = f"{config.index_path}.npy"
            index_file = f"{config.index_path}.faiss"
            
            if not Path(items_file).exists():
                logger.warning("Index files not found")
                return False
            
            # Load items
            with open(items_file, 'r', encoding='utf-8') as f:
                self._items = json.load(f)
            
            # Load embeddings
            if Path(embeddings_file).exists():
                self._embeddings = np.load(embeddings_file)
            
            # Try loading FAISS index
            if Path(index_file).exists():
                try:
                    import faiss
                    self._index = faiss.read_index(index_file)
                    logger.info(f"Loaded FAISS index with {self._index.ntotal} items")
                except ImportError:
                    self._index = None
            
            logger.info(f"Loaded {len(self._items)} items from cache")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to load index: {e}")
            return False
    
    def search(
        self, 
        query: str, 
        top_k: int = 10, 
        filter_func: Optional[Callable[[Dict], bool]] = None
    ) -> List[Tuple[Dict, float]]:
        """Search index by query string with optional filter"""
        if not self._items:
            logger.warning("No items loaded")
            return []
        
        # Get query embedding
        query_embedding = self._get_embeddings([query])[0]
        
        results = []
        
        # Use FAISS if available
        if self._index is not None:
            try:
                search_k = min(top_k * 5, len(self._items))
                distances, indices = self._index.search(
                    query_embedding.reshape(1, -1), search_k
                )
                
                for idx, dist in zip(indices[0], distances[0]):
                    if idx < len(self._items):
                        item = self._items[idx]
                        if filter_func and not filter_func(item):
                            continue
                        score = float(1 / (1 + dist))
                        results.append((item, score))
                        if len(results) >= top_k:
                            break
                # If no results with filter, try without filter
                if not results and filter_func:
                    logger.info("No results with filter, trying without filter")
                    return self.search(query, top_k, filter_func=None)
                
                return results
            except Exception as e:
                logger.warning(f"FAISS search failed: {e}, using fallback")
        
        # Fallback: use stored embeddings
        if self._embeddings is not None:
            for i, item in enumerate(self._items):
                if filter_func and not filter_func(item):
                    continue
                
                emb = self._embeddings[i]
                # Cosine similarity
                dot = np.dot(query_embedding, emb)
                norm_q = np.linalg.norm(query_embedding)
                norm_e = np.linalg.norm(emb)
                sim = dot / (norm_q * norm_e + 1e-8)
                results.append((item, float(sim)))
            
            # Sort by similarity
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
        
        # Last resort: simple text matching
        query_lower = query.lower()
        for item in self._items:
            if filter_func and not filter_func(item):
                continue
            
            text = f"{item.get('name', '')} {item.get('description', '')}".lower()
            score = sum(1 for word in query_lower.split() if word in text) / max(len(query_lower.split()), 1)
            results.append((item, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def get_item_by_index(self, idx: int) -> Optional[Dict]:
        """Get item by index"""
        if 0 <= idx < len(self._items):
            return self._items[idx]
        return None
    
    @property
    def is_loaded(self) -> bool:
        return len(self._items) > 0
    
    @property
    def size(self) -> int:
        return len(self._items)