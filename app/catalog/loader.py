# app/catalog/loader.py
import json
import requests
import re
from typing import List, Dict, Optional
from pathlib import Path

from ..config import config
from ..logger import get_logger
from ..exceptions import CatalogError

logger = get_logger(__name__)


class CatalogLoader:
    """Load catalog from URL or local file with robust JSON handling"""
    
    def __init__(self):
        self.catalog_url = config.catalog_url
        self.catalog_path = config.catalog_path
        self._cache: Optional[List[Dict]] = None
    
    def load(self, force_refresh: bool = False) -> List[Dict]:
        """Load catalog from URL or cache"""
        # Try to load from cache first
        if not force_refresh and self._load_from_cache():
            logger.info("Using cached catalog")
            return self._cache
        
        # Fetch from URL
        logger.info(f"Fetching catalog from {self.catalog_url}")
        try:
            response = requests.get(self.catalog_url, timeout=30)
            response.raise_for_status()
            
            # Get raw text and clean it
            raw_text = response.text
            
            # Clean the JSON text
            cleaned_text = self._clean_json(raw_text)
            
            # Parse JSON
            try:
                data = json.loads(cleaned_text)
            except json.JSONDecodeError as e:
                logger.warning(f"Initial JSON parse failed: {e}, trying with strict=False")
                # Try with more lenient parsing
                data = json.loads(cleaned_text, strict=False)
            
            if isinstance(data, list) and len(data) > 0:
                normalized = self._normalize_catalog(data)
                self._save_cache(normalized)
                logger.info(f"Loaded {len(normalized)} items from URL")
                return normalized
            else:
                raise CatalogError("Invalid catalog format: expected non-empty list")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch catalog: {e}")
            if self._load_from_cache():
                return self._cache
            raise CatalogError(f"Failed to fetch catalog: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse catalog JSON after cleaning: {e}")
            # Try one more time with a different approach
            try:
                # Try to load line by line for malformed JSON
                data = self._parse_line_by_line(raw_text)
                if data:
                    normalized = self._normalize_catalog(data)
                    self._save_cache(normalized)
                    logger.info(f"Loaded {len(normalized)} items using line-by-line parsing")
                    return normalized
            except Exception as line_error:
                logger.error(f"Line-by-line parsing also failed: {line_error}")
            
            if self._load_from_cache():
                return self._cache
            raise CatalogError(f"Failed to parse catalog JSON: {e}")
    
    def _clean_json(self, text: str) -> str:
        """Clean JSON text by removing control characters and fixing common issues"""
        # Remove invalid control characters (ASCII 0-31 except tab, newline, carriage return)
        # Keep \t (9), \n (10), \r (13)
        cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Fix trailing commas (common in JSON from APIs)
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        
        # Fix unescaped quotes within strings (common issue)
        # This is a simplified fix - for more complex cases, use json.loads with strict=False
        return cleaned
    
    def _parse_line_by_line(self, text: str) -> Optional[List[Dict]]:
        """Attempt to parse JSON by extracting individual objects"""
        try:
            # Find all complete JSON objects in the text
            objects = []
            depth = 0
            start = None
            in_string = False
            escape = False
            
            for i, char in enumerate(text):
                if escape:
                    escape = False
                    continue
                
                if char == '\\' and in_string:
                    escape = True
                    continue
                
                if char == '"' and not escape:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == '{':
                        if depth == 0:
                            start = i
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0 and start is not None:
                            # Found a complete object
                            obj_str = text[start:i+1]
                            try:
                                # Clean the object string
                                obj_str = self._clean_json(obj_str)
                                obj = json.loads(obj_str)
                                objects.append(obj)
                            except json.JSONDecodeError:
                                # If individual object fails, try with strict=False
                                try:
                                    obj = json.loads(obj_str, strict=False)
                                    objects.append(obj)
                                except:
                                    pass
                            start = None
            
            return objects if objects else None
            
        except Exception as e:
            logger.error(f"Line-by-line parsing error: {e}")
            return None
    
    def _normalize_catalog(self, raw_data: List[Dict]) -> List[Dict]:
        """Normalize catalog data to consistent format"""
        normalized = []
        
        for item in raw_data:
            # Skip invalid items
            if not item.get('name'):
                continue
            
            test_type = self._map_test_type(item.get('keys', []))
            duration = self._parse_duration(item.get('duration', ''))
            
            normalized.append({
                "id": item.get('entity_id', ''),
                "name": item.get('name', ''),
                "url": item.get('link', ''),
                "test_type": test_type,
                "description": item.get('description', ''),
                "duration_minutes": duration,
                "languages": item.get('languages', []),
                "job_levels": item.get('job_levels', []),
                "remote": item.get('remote', '') == 'yes',
                "adaptive": item.get('adaptive', '') == 'yes',
                "keys": item.get('keys', []),
                "status": item.get('status', ''),
            })
        
        logger.info(f"Normalized {len(normalized)} items from {len(raw_data)} raw items")
        return normalized
    
    def _map_test_type(self, keys: List[str]) -> str:
        """Map keys to test type code"""
        key_map = {
            'Knowledge & Skills': 'K',
            'Personality & Behavior': 'P',
            'Ability & Aptitude': 'A',
            'Biodata & Situational Judgment': 'B',
            'Simulations': 'S',
            'Competencies': 'C',
            'Development & 360': 'D',
            'Assessment Exercises': 'A'
        }
        
        for key in keys:
            if key in key_map:
                return key_map[key]
        return 'O'
    
    def _parse_duration(self, duration_str: str) -> Optional[int]:
        """Parse duration string to minutes"""
        if not duration_str:
            return None
        
        match = re.search(r'(\d+)', duration_str)
        if match:
            return int(match.group(1))
        return None
    
    def _load_from_cache(self) -> bool:
        """Load catalog from cache file"""
        try:
            cache_path = Path(self.catalog_path)
            if cache_path.exists():
                with open(cache_path, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                logger.info(f"Loaded {len(self._cache)} items from cache")
                return True
        except Exception as e:
            logger.warning(f"Cache load failed: {e}")
        return False
    
    def _save_cache(self, data: List[Dict]) -> None:
        """Save catalog to cache"""
        try:
            cache_path = Path(self.catalog_path)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(data)} items to cache at {self.catalog_path}")
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")
    
    def get_catalog_items(self) -> List[Dict]:
        """Get all catalog items (loads if not already loaded)"""
        if self._cache is None:
            self.load()
        return self._cache