# app/agent/context.py
import re
import json
from typing import List, Dict, Optional, Any

from ..llm.client import LLMClient
from ..logger import get_logger

logger = get_logger(__name__)


class ContextExtractor:
    """Extract structured context from conversation"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def extract(self, messages: List[Dict]) -> Dict[str, Any]:
        """Extract constraints from conversation history"""
        constraints = {
            "role": None,
            "seniority": None,
            "competencies": [],
            "test_types": [],
            "duration_limit": None,
            "language": None,
            "job_level": None
        }
        
        # Extract using rules first
        for msg in messages:
            content = msg.get('content', '')
            self._extract_from_text(content, constraints)
        
        # Try LLM enhancement for better extraction
        if len(messages) > 1:
            try:
                llm_constraints = self._extract_with_llm(messages)
                if llm_constraints:
                    for key, value in llm_constraints.items():
                        if value:
                            constraints[key] = value
            except Exception as e:
                logger.debug(f"LLM extraction failed: {e}")
        
        logger.debug(f"Extracted constraints: {constraints}")
        return constraints
    
    def _extract_from_text(self, text: str, constraints: Dict) -> None:
        """Extract constraints from text using rules"""
        text_lower = text.lower()
        
        # Role
        role_patterns = [
            r'(?:hiring|need|looking for|position|role)[:\s]+([a-z\s]+)',
            r'([a-z\s]+)\s+(?:developer|engineer|analyst|manager|lead|specialist|consultant)'
        ]
        for pattern in role_patterns:
            match = re.search(pattern, text_lower)
            if match and not constraints['role']:
                constraints['role'] = match.group(1).strip()
                break
        
        # Seniority
        seniority_map = {
            'senior': 'senior',
            'sr': 'senior',
            'lead': 'lead',
            'mid': 'mid',
            'junior': 'entry',
            'entry': 'entry',
            'graduate': 'entry',
            'executive': 'executive',
            'director': 'executive',
            'manager': 'manager'
        }
        for word, level in seniority_map.items():
            if word in text_lower:
                constraints['seniority'] = level
                constraints['job_level'] = level
                break
        
        # Competencies - look for skill keywords
        skill_keywords = [
            'java', 'python', 'sql', 'aws', 'docker', 'kubernetes', 
            'spring', 'angular', 'react', 'leadership', 'communication',
            'problem solving', 'analytical', 'teamwork', 'strategic'
        ]
        for skill in skill_keywords:
            if skill in text_lower:
                if skill not in constraints['competencies']:
                    constraints['competencies'].append(skill)
        
        # Test types
        test_map = {
            'personality': 'P',
            'behaviour': 'P',
            'behavior': 'P',
            'ability': 'A',
            'aptitude': 'A',
            'cognitive': 'A',
            'reasoning': 'A',
            'knowledge': 'K',
            'skills': 'K',
            'technical': 'K',
            'simulation': 'S',
            'situational': 'B',
            'scenarios': 'B',
            'competency': 'C'
        }
        for word, code in test_map.items():
            if word in text_lower:
                if code not in constraints['test_types']:
                    constraints['test_types'].append(code)
        
        # Duration
        duration_match = re.search(r'(\d+)\s*(?:minutes?|mins?)', text_lower)
        if duration_match:
            constraints['duration_limit'] = int(duration_match.group(1))
        
        # Language
        languages = ['english', 'spanish', 'french', 'german', 'chinese', 
                     'portuguese', 'dutch', 'italian', 'korean', 'japanese']
        for lang in languages:
            if lang in text_lower:
                constraints['language'] = lang.capitalize()
                break
    
    def _extract_with_llm(self, messages: List[Dict]) -> Optional[Dict]:
        """Use LLM to extract constraints"""
        prompt = f"""Extract hiring requirements from this conversation.

Conversation: {json.dumps(messages, indent=2)}

Return JSON with these fields:
- role: job role (string or null)
- seniority: entry/mid/senior/lead/executive or null  
- competencies: list of required skills
- test_types: list of assessment types (K, P, A, B, S, C)
- duration_limit: max duration in minutes (number or null)
- language: required language or null

JSON:"""
        
        response = self.llm.generate(prompt)
        if response:
            return self.llm.extract_json(response)
        return None
    
    def is_sufficient(self, constraints: Dict) -> bool:
        """Check if enough info to recommend"""
        has_role = constraints.get('role') is not None
        has_competencies = len(constraints.get('competencies', [])) > 0
        
        return has_role or has_competencies
    
    def get_missing_fields(self, constraints: Dict) -> List[str]:
        """Get missing fields that need clarification"""
        missing = []
        required = ['role', 'seniority']
        
        for field in required:
            if not constraints.get(field):
                missing.append(field)
        
        if not constraints.get('competencies'):
            missing.append('competencies')
        
        return missing