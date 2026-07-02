# app/catalog/retriever.py
from typing import List, Dict, Optional, Tuple, Callable
from .indexer import CatalogIndexer
from ..logger import get_logger

logger = get_logger(__name__)


class CatalogRetriever:
    """Retrieve catalog items with filtering and ranking"""
    
    def __init__(self, indexer: CatalogIndexer):
        self.indexer = indexer
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search catalog - uses keyword search as primary method
        """
        if not self.indexer.is_loaded:
            logger.warning("Index not loaded, returning empty results")
            return []
        
        logger.info(f"Searching with query: '{query}', filters: {filters}")
        
        # Use keyword search
        results = self.search_by_keywords(query, top_k=top_k)
        
        # Apply filters if needed
        if filters and results:
            filter_func = self._build_filter_func(filters)
            filtered_results = []
            for result in results:
                if filter_func(result['item']):
                    filtered_results.append(result)
                    if len(filtered_results) >= top_k:
                        break
            results = filtered_results
        
        logger.info(f"Found {len(results)} results for query: '{query}'")
        return results
    
    def search_by_keywords(self, query: str, top_k: int = 10) -> List[Dict]:
        """Keyword-based search with scoring"""
        if not self.indexer.is_loaded:
            return []
        
        # Extract keywords from query
        query_lower = query.lower()
        keywords = query_lower.split()
        
        # Remove common stopwords
        stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'for', 'on', 'at', 'to', 'by', 'in', 'of', 'with', 'without', 'i', 'need', 'hire', 'please', 'recommend', 'specific', 'assessments', 'names', 'urls'}
        keywords = [k for k in keywords if k not in stopwords and len(k) > 2]
        
        # If no keywords, add default
        if not keywords:
            keywords = ['assessment']
        
        logger.info(f"Keywords: {keywords}")
        
        results = []
        for item in self.indexer._items:
            name = item.get('name', '').lower()
            desc = item.get('description', '').lower()
            keys = ' '.join(item.get('keys', [])).lower()
            job_levels = ' '.join(item.get('job_levels', [])).lower()
            
            combined_text = f"{name} {desc} {keys} {job_levels}"
            
            # Calculate match score
            score = 0.0
            matched_keywords = []
            
            for keyword in keywords:
                # Exact match in name - highest weight
                if keyword in name:
                    score += 3.0
                    matched_keywords.append(keyword)
                    # Boost for full word match
                    if f' {keyword} ' in f' {name} ' or name.startswith(keyword):
                        score += 1.0
                
                # Match in description
                elif keyword in desc:
                    score += 1.0
                    matched_keywords.append(keyword)
                
                # Match in keys
                elif keyword in keys:
                    score += 0.5
                    matched_keywords.append(keyword)
                
                # Match in job levels
                elif keyword in job_levels:
                    score += 0.3
                    matched_keywords.append(keyword)
                
                # Check if keyword is part of a longer word
                else:
                    for word in combined_text.split():
                        if keyword in word and word != keyword:
                            score += 0.2
                            matched_keywords.append(keyword)
                            break
            
            if score > 0:
                # Boost for having multiple matches
                score *= (1 + len(matched_keywords) * 0.1)
                results.append((item, score))
        
        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Log top results
        logger.info(f"Found {len(results)} keyword matches")
        
        # Return top_k
        return [{"item": item, "score": score} for item, score in results[:top_k]]
    
    def search_by_keyword(self, keyword: str, top_k: int = 10) -> List[Dict]:
        """Simple single keyword search"""
        return self.search_by_keywords(keyword, top_k)
    
    def get_by_name(self, name: str, fuzzy: bool = True) -> Optional[Dict]:
        """Get catalog item by name"""
        if not self.indexer.is_loaded:
            return None
        
        name_lower = name.lower()
        
        # Try exact match first
        for item in self.indexer._items:
            if item['name'].lower() == name_lower:
                return item
        
        # Try partial match
        if fuzzy:
            for item in self.indexer._items:
                if name_lower in item['name'].lower() or item['name'].lower() in name_lower:
                    return item
        
        return None
    
    def get_by_names(self, names: List[str]) -> List[Dict]:
        """Get multiple items by names"""
        results = []
        for name in names:
            item = self.get_by_name(name)
            if item:
                results.append(item)
        return results
    
    def get_by_id(self, entity_id: str) -> Optional[Dict]:
        """Get catalog item by entity_id"""
        if not self.indexer.is_loaded:
            return None
        
        for item in self.indexer._items:
            if item.get('id') == entity_id:
                return item
        return None
    
    def get_all(self) -> List[Dict]:
        """Get all catalog items"""
        return self.indexer._items if self.indexer.is_loaded else []
    
    def _build_filter_func(self, filters: Dict) -> Callable:
        """Build a filter function from filter dict"""
        def filter_func(item: Dict) -> bool:
            for key, value in filters.items():
                if key == 'test_type':
                    if isinstance(value, list):
                        if item.get('test_type', '').upper() not in [v.upper() for v in value]:
                            return False
                    else:
                        if item.get('test_type', '').upper() != value.upper():
                            return False
                elif key == 'duration_max':
                    duration = item.get('duration_minutes')
                    if duration and duration > value:
                        return False
                elif key == 'duration_min':
                    duration = item.get('duration_minutes')
                    if duration and duration < value:
                        return False
                elif key == 'language':
                    if value not in item.get('languages', []):
                        return False
                elif key == 'job_level':
                    if value not in item.get('job_levels', []):
                        return False
                elif key == 'remote':
                    if item.get('remote') != value:
                        return False
                elif key == 'adaptive':
                    if item.get('adaptive') != value:
                        return False
            return True
        
        return filter_func