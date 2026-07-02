# app/agent/policy.py
from enum import Enum
from typing import Dict, List, Optional, Any

from .context import ContextExtractor
from ..logger import get_logger

logger = get_logger(__name__)


class Intent(Enum):
    """Agent intent types"""
    CLARIFY = "clarify"
    RECOMMEND = "recommend"
    REFINE = "refine"
    COMPARE = "compare"
    REFUSE = "refuse"
    COMPLETE = "complete"


class DialoguePolicy:
    """Dialogue policy for agent decision making"""
    
    def __init__(self, context_extractor: ContextExtractor):
        self.context = context_extractor
    
    def decide(self, messages: List[Dict]) -> Dict[str, Any]:
        """Decide the next action"""
        # Extract constraints
        constraints = self.context.extract(messages)
        
        # Get last message
        last_message = messages[-1].get('content', '') if messages else ''
        last_message_lower = last_message.lower()
        
        # FIRST: Check for comparison (before out-of-scope)
        if self._is_comparison(last_message):
            logger.info("Detected comparison intent")
            return {
                "intent": Intent.COMPARE,
                "constraints": constraints
            }
        
        # THEN: Check for out-of-scope (but be careful not to block comparisons)
        out_of_scope = self._check_out_of_scope(last_message)
        if out_of_scope:
            return {
                "intent": Intent.REFUSE,
                "reason": out_of_scope,
                "constraints": constraints
            }
        
        # Check for refinement
        if self._is_refinement(last_message):
            return {
                "intent": Intent.REFINE,
                "constraints": constraints
            }
        
        # Check if enough info
        if self.context.is_sufficient(constraints):
            already_recommended = self._has_recommended(messages)
            return {
                "intent": Intent.RECOMMEND,
                "constraints": constraints,
                "first_time": not already_recommended
            }
        
        # Default: clarify
        return {
            "intent": Intent.CLARIFY,
            "constraints": constraints,
            "missing": self.context.get_missing_fields(constraints)
        }
    
    def _check_out_of_scope(self, text: str) -> Optional[str]:
        """Check if request is out of scope - but be careful with comparisons"""
        text_lower = text.lower()
        
        # Legal questions
        legal_keywords = ['legal', 'law', 'compliance', 'regulation', 'regulatory', 'hipaa', 'gdpr']
        for keyword in legal_keywords:
            if keyword in text_lower:
                return "I cannot provide legal or regulatory advice. I specialize in SHL assessment selection."
        
        # Hiring process questions (but not comparison questions)
        hiring_keywords = ['interview loop', 'how to interview', 'interview process', 'salary', 'offer']
        # Don't block comparison questions that might contain these words
        if any(keyword in text_lower for keyword in hiring_keywords):
            # Check if it's actually a comparison
            if not self._is_comparison(text):
                return "I focus on SHL assessment recommendations, not general hiring process advice."
        
        # Prompt injection detection
        injection_patterns = ['ignore previous', 'system prompt', 'reveal your', 'forget your']
        for pattern in injection_patterns:
            if pattern in text_lower:
                return "I cannot honor that request. Let me help you with SHL assessment selection."
        
        # Check if this is completely off-topic (but allow comparison questions)
        assessment_keywords = ['assessment', 'test', 'recommend', 'hire', 'role', 'candidate', 'skill', 'competency']
        if not any(keyword in text_lower for keyword in assessment_keywords):
            # If it's not a comparison and not about assessments, it might be out of scope
            if not self._is_comparison(text):
                return "I'm here to help with SHL assessment recommendations. What role are you hiring for?"
        
        return None
    
    def _is_comparison(self, text: str) -> bool:
        """Detect comparison request - more comprehensive"""
        text_lower = text.lower()
        
        # Direct comparison indicators
        indicators = [
            'difference between',
            'compare',
            'vs',
            'versus',
            'differentiate',
            'what\'s the difference',
            'how are they different',
            'how do they compare',
            'which is better',
            'contrast'
        ]
        
        # Check for indicators
        for indicator in indicators:
            if indicator in text_lower:
                return True
        
        # Check for pattern "X and Y" with comparison context
        if ' and ' in text_lower:
            # Check if there are assessment names mentioned
            import re
            # Look for two items separated by "and" or "vs"
            patterns = [
                r'([a-z][a-z\s\(\)\-]+)\s+and\s+([a-z][a-z\s\(\)\-]+)',
                r'([a-z][a-z\s\(\)\-]+)\s+vs\.?\s+([a-z][a-z\s\(\)\-]+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    name1 = match.group(1).strip()
                    name2 = match.group(2).strip()
                    # Check if they look like assessment names (contain Java, OPQ, GSA, etc.)
                    assessment_keywords = ['java', 'opq', 'gsa', 'dsi', 'verify', 'angular', 'python', 'sql']
                    if any(kw in name1 for kw in assessment_keywords) or any(kw in name2 for kw in assessment_keywords):
                        return True
        
        return False
    
    def _is_refinement(self, text: str) -> bool:
        """Detect refinement request"""
        indicators = ['actually', 'add', 'remove', 'change', 'instead', 'drop', 'update', 'also']
        return any(ind in text.lower() for ind in indicators)
    
    def _has_recommended(self, messages: List[Dict]) -> bool:
        """Check if recommendations have been given before"""
        for msg in messages:
            if msg.get('role') == 'assistant':
                content = msg.get('content', '').lower()
                indicators = ['recommend', 'shortlist', 'here are', 'solutions', 'assessments']
                if any(ind in content for ind in indicators):
                    return True
        return False