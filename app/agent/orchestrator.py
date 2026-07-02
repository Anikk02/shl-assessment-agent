# app/agent/orchestrator.py
import json
import re
from typing import List, Dict, Any, Optional

from .policy import DialoguePolicy, Intent
from .context import ContextExtractor
from .prompts import (
    SYSTEM_PROMPT,
    CLARIFY_PROMPT,
    RECOMMEND_PROMPT,
    COMPARE_PROMPT,
    REFUSE_PROMPT
)
from ..catalog.retriever import CatalogRetriever
from ..llm.client import LLMClient
from ..config import config
from ..logger import get_logger

logger = get_logger(__name__)


class AgentOrchestrator:
    """Main orchestrator for agent logic"""
    
    def __init__(self, retriever: CatalogRetriever, llm_client: LLMClient):
        self.retriever = retriever
        self.llm = llm_client
        self.context_extractor = ContextExtractor(llm_client)
        self.policy = DialoguePolicy(self.context_extractor)
        self._shortlist: List[Dict] = []
    
    def process(self, messages: List[Dict]) -> Dict[str, Any]:
        """Process conversation and return response"""
        try:
            # Check turn limit
            if len(messages) >= config.max_turns:
                logger.warning(f"Turn limit reached: {len(messages)}")
                return self._handle_turn_limit(messages)
            
            # Get policy decision
            decision = self.policy.decide(messages)
            intent = decision['intent']
            constraints = decision['constraints']
            
            logger.info(f"Intent: {intent.value}, constraints: {constraints}")
            
            # Handle by intent
            handlers = {
                Intent.REFUSE: self._handle_refuse,
                Intent.COMPARE: self._handle_compare,
                Intent.REFINE: self._handle_refine,
                Intent.RECOMMEND: self._handle_recommend,
                Intent.CLARIFY: self._handle_clarify,
            }
            
            handler = handlers.get(intent, self._handle_clarify)
            return handler(messages, constraints, decision)
            
        except Exception as e:
            logger.error(f"Error in process: {e}", exc_info=True)
            return {
                "reply": "I encountered an issue processing your request. Could you please rephrase or provide more details?",
                "recommendations": [],
                "end_of_conversation": False
            }
    
    def _handle_clarify(self, messages: List[Dict], constraints: Dict, decision: Dict) -> Dict:
        """Handle clarification"""
        reply = self._generate_clarification(messages, constraints)
        
        return {
            "reply": reply,
            "recommendations": [],
            "end_of_conversation": False
        }
    
    def _handle_recommend(self, messages: List[Dict], constraints: Dict, decision: Dict) -> Dict:
        """Handle recommendation - ALWAYS populate recommendations array"""
        try:
            # Build query and filters
            query = self._build_query(constraints)
            filters = self._build_filters(constraints)
            
            logger.info(f"Searching with query: '{query}', filters: {filters}")
            
            # If query is too short, expand it with relevant keywords
            if len(query.split()) < 3:
                expanded_query = self._expand_query(query)
                logger.info(f"Expanded query: '{expanded_query}'")
                query = expanded_query
            
            # Search catalog - try keyword search first
            results = self.retriever.search(query, top_k=config.max_recommendations, filters=filters)
            
            # If no results, try a broader search with individual keywords
            if not results:
                logger.info("No results from combined search, trying individual keywords")
                keywords = query.split()
                for keyword in keywords:
                    if len(keyword) > 2 and keyword not in ['for', 'with', 'the']:
                        keyword_results = self.retriever.search_by_keyword(keyword, top_k=5)
                        if keyword_results:
                            results = keyword_results
                            logger.info(f"Found {len(results)} results for keyword: '{keyword}'")
                            break
            
            # Build recommendations
            recommendations = []
            for result in results:
                item = result['item']
                recommendations.append({
                    "name": item.get('name', ''),
                    "url": item.get('url', ''),
                    "test_type": item.get('test_type', 'O')
                })
            
            self._shortlist = recommendations
            
            # Generate reply
            first_time = decision.get('first_time', True)
            reply = self._generate_recommendation_response(
                messages, constraints, recommendations, first_time
            )
            
            # End conversation if we have recommendations and it's the first time
            end = len(recommendations) > 0 and first_time
            
            logger.info(f"Returning {len(recommendations)} recommendations, end={end}")
            
            return {
                "reply": reply,
                "recommendations": recommendations,
                "end_of_conversation": end
            }
            
        except Exception as e:
            logger.error(f"Error in _handle_recommend: {e}", exc_info=True)
            return {
                "reply": "I encountered an issue while searching for assessments. Could you please rephrase your request or provide more specific details about the role?",
                "recommendations": [],
                "end_of_conversation": False
            }
    
    def _handle_refine(self, messages: List[Dict], constraints: Dict, decision: Dict) -> Dict:
        """Handle refinement - ALWAYS populate recommendations array"""
        try:
            query = self._build_query(constraints)
            filters = self._build_filters(constraints)
            
            logger.info(f"Refining with query: '{query}', filters: {filters}")
            
            # Search catalog
            results = self.retriever.search(query, top_k=config.max_recommendations, filters=filters)
            
            # If no results, try broader search
            if not results:
                keywords = query.split()
                for keyword in keywords:
                    if len(keyword) > 2:
                        keyword_results = self.retriever.search_by_keyword(keyword, top_k=5)
                        if keyword_results:
                            results = keyword_results
                            logger.info(f"Found {len(results)} results for keyword: '{keyword}'")
                            break
            
            recommendations = []
            for result in results:
                item = result['item']
                recommendations.append({
                    "name": item.get('name', ''),
                    "url": item.get('url', ''),
                    "test_type": item.get('test_type', 'O')
                })
            
            self._shortlist = recommendations
            
            reply = self._generate_refinement_response(messages, constraints, recommendations)
            
            return {
                "reply": reply,
                "recommendations": recommendations,
                "end_of_conversation": len(recommendations) > 0
            }
            
        except Exception as e:
            logger.error(f"Error in _handle_refine: {e}", exc_info=True)
            return {
                "reply": "I encountered an issue updating the recommendations. Could you please try again?",
                "recommendations": [],
                "end_of_conversation": False
            }
    
    def _handle_compare(self, messages: List[Dict], constraints: Dict, decision: Dict) -> Dict:
        """Handle comparison with improved name extraction"""
        try:
            last_message = messages[-1].get('content', '')
            logger.info(f"Processing comparison request: {last_message}")
            
            # Try multiple methods to extract assessment names
            names = self._extract_names_advanced(last_message)
            
            logger.info(f"Extracted names: {names}")
            
            if len(names) < 2:
                return {
                    "reply": "I need at least two assessment names to compare. Could you specify which assessments you'd like to compare? For example:\n- 'Compare Core Java (Advanced Level) and Core Java (Entry Level)'\n- 'What's the difference between OPQ and GSA?'",
                    "recommendations": [],
                    "end_of_conversation": False
                }
            
            # Get items from catalog
            items = []
            for name in names:
                item = self.retriever.get_by_name(name, fuzzy=True)
                if item:
                    items.append(item)
                    logger.info(f"Found item: {item.get('name')}")
            
            if len(items) < 2:
                found_names = [item.get('name') for item in items]
                not_found = [n for n in names if n not in found_names]
                # Suggest available assessments
                available = self._suggest_similar_assessments(names[0])
                return {
                    "reply": f"I couldn't find these assessments in the catalog: {', '.join(not_found)}.\n\nAvailable Java assessments include:\n{available}\n\nPlease try again with exact assessment names from the catalog.",
                    "recommendations": [],
                    "end_of_conversation": False
                }
            
            # Generate comparison
            reply = self._generate_comparison_response(items)
            
            recommendations = [{
                "name": item.get('name', ''),
                "url": item.get('url', ''),
                "test_type": item.get('test_type', 'O')
            } for item in items]
            
            return {
                "reply": reply,
                "recommendations": recommendations,
                "end_of_conversation": False
            }
            
        except Exception as e:
            logger.error(f"Error in _handle_compare: {e}", exc_info=True)
            return {
                "reply": "I encountered an issue comparing assessments. Could you please specify which assessments you'd like to compare? For example: 'Compare Core Java (Advanced Level) and Core Java (Entry Level)'",
                "recommendations": [],
                "end_of_conversation": False
            }
    
    def _extract_names_advanced(self, text: str) -> List[str]:
        """Advanced name extraction for Java assessments"""
        names = []
        
        # Method 1: Direct pattern matching for "difference between X and Y"
        pattern1 = r'difference\s+between\s+([^and]+)\s+and\s+([^?\.]+)'
        match1 = re.search(pattern1, text, re.IGNORECASE)
        if match1:
            name1 = match1.group(1).strip()
            name2 = match1.group(2).strip()
            if name1 and name2:
                names.extend([name1, name2])
                return names
        
        # Method 2: Pattern for "X vs Y" or "X versus Y"
        pattern2 = r'([A-Za-z0-9\s\(\)\-]+)\s+(?:vs\.?|versus)\s+([A-Za-z0-9\s\(\)\-]+)'
        match2 = re.search(pattern2, text, re.IGNORECASE)
        if match2:
            name1 = match2.group(1).strip()
            name2 = match2.group(2).strip()
            if name1 and name2:
                names.extend([name1, name2])
                return names
        
        # Method 3: Pattern for "compare X and Y"
        pattern3 = r'compare\s+([^and]+)\s+and\s+([^?\.]+)'
        match3 = re.search(pattern3, text, re.IGNORECASE)
        if match3:
            name1 = match3.group(1).strip()
            name2 = match3.group(2).strip()
            if name1 and name2:
                names.extend([name1, name2])
                return names
        
        # Method 4: Look for quoted names or parenthesized names
        quoted = re.findall(r'"([^"]+)"', text)
        if quoted:
            names.extend(quoted)
        
        # Method 5: Look for specific Java assessment patterns
        java_names = [
            'Core Java (Advanced Level)',
            'Core Java (Entry Level)',
            'Core Java (Advanced Level) (New)',
            'Core Java (Entry Level) (New)',
            'Java 8',
            'Java 8 (New)',
            'Enterprise Java Beans',
            'Enterprise Java Beans (New)',
            'Java Design Patterns',
            'Java Design Patterns (New)',
            'Java Frameworks',
            'Java Frameworks (New)',
            'Java Web Services',
            'Java Web Services (New)',
            'Java Platform Enterprise Edition 7',
            'Java Platform Enterprise Edition 7 (Java EE 7)',
            'JavaScript',
            'JavaScript (New)'
        ]
        
        for java_name in java_names:
            if java_name.lower() in text.lower():
                names.append(java_name)
        
        # Method 6: Try to find any "Java" mentions with parentheses
        java_pattern = r'(Java\s+[^,\.\?]+?)(?:\s+and\s+|\s+vs\.?\s+|\s+versus\s+)(Java\s+[^,\.\?]+)'
        match6 = re.search(java_pattern, text, re.IGNORECASE)
        if match6:
            name1 = match6.group(1).strip()
            name2 = match6.group(2).strip()
            if name1 and name2:
                names.extend([name1, name2])
        
        # Clean up and deduplicate
        names = [n.strip() for n in names if n.strip()]
        names = list(set(names))
        
        logger.info(f"Extracted names: {names}")
        return names
    
    def _suggest_similar_assessments(self, query: str) -> str:
        """Suggest available assessments similar to the query"""
        all_items = self.retriever.get_all()
        suggestions = []
        
        query_lower = query.lower()
        for item in all_items:
            name = item.get('name', '')
            if 'java' in name.lower() and len(suggestions) < 10:
                suggestions.append(f"  - {name}")
        
        if not suggestions:
            return "  - No Java assessments found in catalog"
        
        return "\n".join(suggestions)
    
    def _handle_refuse(self, messages: List[Dict], constraints: Dict, decision: Dict) -> Dict:
        """Handle refusal"""
        reason = decision.get('reason', '')
        reply = self._generate_refusal_response(reason)
        
        return {
            "reply": reply,
            "recommendations": [],
            "end_of_conversation": False
        }
    
    def _handle_turn_limit(self, messages: List[Dict]) -> Dict:
        """Handle max turn limit"""
        reply = "We're approaching the conversation limit. Based on what we've discussed, here's a final shortlist of relevant assessments."
        
        try:
            constraints = self.context_extractor.extract(messages)
            query = self._build_query(constraints)
            results = self.retriever.search(query, top_k=config.max_recommendations)
            
            recommendations = []
            for result in results:
                item = result['item']
                recommendations.append({
                    "name": item.get('name', ''),
                    "url": item.get('url', ''),
                    "test_type": item.get('test_type', 'O')
                })
            
            return {
                "reply": reply,
                "recommendations": recommendations,
                "end_of_conversation": True
            }
        except Exception as e:
            logger.error(f"Error in _handle_turn_limit: {e}")
            return {
                "reply": "We've reached the conversation limit. Please start a new conversation with more details about your hiring needs.",
                "recommendations": [],
                "end_of_conversation": True
            }
    
    def _generate_clarification(self, messages: List[Dict], constraints: Dict) -> str:
        """Generate clarification question"""
        missing = self.context_extractor.get_missing_fields(constraints)
        
        try:
            prompt = CLARIFY_PROMPT.format(
                constraints=json.dumps(constraints, indent=2),
                conversation=json.dumps(messages[-3:], indent=2)
            )
            response = self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)
            if response:
                return response
        except Exception as e:
            logger.debug(f"LLM clarification failed: {e}")
        
        if not missing:
            return "Could you tell me more about your hiring needs, such as the role, seniority level, and key competencies required?"
        
        questions = []
        field_questions = {
            'role': "What role are you hiring for?",
            'seniority': "What's the seniority level (entry, mid, senior, lead)?",
            'competencies': "What key competencies or skills are required?",
            'test_types': "What type of assessments are you looking for (personality, ability, knowledge, etc.)?"
        }
        
        for field in missing:
            if field in field_questions:
                questions.append(field_questions[field])
        
        return " ".join(questions) if questions else "To help me recommend the right assessments, could you tell me more about the role and requirements?"
    
    def _generate_recommendation_response(
        self,
        messages: List[Dict],
        constraints: Dict,
        recommendations: List[Dict],
        first_time: bool
    ) -> str:
        """Generate recommendation response with proper context"""
        if not recommendations:
            return "I couldn't find any specific assessments matching your requirements. Could you provide more details about the role and skills needed?"
        
        try:
            prompt = RECOMMEND_PROMPT.format(
                constraints=json.dumps(constraints, indent=2),
                recommendations=json.dumps(recommendations[:5], indent=2)
            )
            response = self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)
            if response:
                return response
        except Exception as e:
            logger.error(f"LLM recommendation generation failed: {e}")
        
        names = [r['name'] for r in recommendations[:5]]
        if first_time:
            return f"Based on your requirements, I recommend these {len(recommendations)} SHL assessments: {', '.join(names)}. Would you like more details about any of these?"
        else:
            return f"Here's an updated shortlist of {len(recommendations)} assessments: {', '.join(names)}."
    
    def _generate_refinement_response(
        self,
        messages: List[Dict],
        constraints: Dict,
        recommendations: List[Dict]
    ) -> str:
        """Generate refinement response"""
        if not recommendations:
            return "I couldn't find any assessments matching your updated requirements. Could you provide more details?"
        
        try:
            prompt = RECOMMEND_PROMPT.format(
                constraints=json.dumps(constraints, indent=2),
                recommendations=json.dumps(recommendations[:5], indent=2)
            )
            response = self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)
            if response:
                return response
        except Exception:
            pass
        
        names = [r['name'] for r in recommendations[:5]]
        return f"I've updated the shortlist based on your changes. Here are {len(recommendations)} assessments: {', '.join(names)}."
    
    def _generate_comparison_response(self, items: List[Dict]) -> str:
        """Generate comparison response"""
        try:
            comparison_data = []
            for item in items:
                comparison_data.append({
                    "name": item.get('name', ''),
                    "description": item.get('description', 'No description available'),
                    "test_type": item.get('test_type', ''),
                    "duration": item.get('duration_minutes', 'Not specified'),
                    "languages": item.get('languages', [])
                })
            
            prompt = COMPARE_PROMPT.format(
                comparison_data=json.dumps(comparison_data, indent=2)
            )
            response = self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)
            if response:
                return response
        except Exception as e:
            logger.error(f"LLM comparison generation failed: {e}")
        
        # Fallback comparison
        fallback = "Here's a comparison based on catalog data:\n\n"
        for item in items:
            fallback += f"**{item.get('name', 'Unknown')}**\n"
            fallback += f"- Type: {item.get('test_type', 'Not specified')}\n"
            fallback += f"- Duration: {item.get('duration_minutes', 'Not specified')} minutes\n"
            fallback += f"- Languages: {', '.join(item.get('languages', ['Not specified']))}\n"
            fallback += f"- Description: {item.get('description', 'No description available')[:150]}...\n\n"
        
        return fallback
    
    def _generate_refusal_response(self, reason: str) -> str:
        """Generate refusal response"""
        try:
            prompt = REFUSE_PROMPT.format(reason=reason)
            response = self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)
            if response:
                return response
        except Exception:
            pass
        
        return f"I understand your question, but {reason} I'm here to help with SHL assessment selection. Is there a specific role or hiring need I can assist with?"
    
    def _build_query(self, constraints: Dict) -> str:
        """Build search query from constraints"""
        parts = []
        
        if constraints.get('role'):
            parts.append(constraints['role'])
        
        if constraints.get('competencies'):
            parts.extend(constraints['competencies'][:3])
        
        if constraints.get('seniority'):
            parts.append(constraints['seniority'])
        
        query = " ".join(parts) if parts else ""
        if len(query.split()) < 3:
            query = f"{query} programming developer skills".strip()
        
        return query if query else "assessment"
    
    def _expand_query(self, query: str) -> str:
        """Expand short query with relevant keywords"""
        tech_keywords = {
            'java': 'java spring boot microservices developer',
            'python': 'python django flask developer',
            'javascript': 'javascript react node developer',
            'aws': 'aws cloud computing developer',
            'docker': 'docker containerization devops',
            'sql': 'sql database querying developer',
            'leadership': 'leadership management executive',
            'personality': 'personality behavior OPQ',
            'cognitive': 'cognitive ability reasoning aptitude',
            'technical': 'technical programming knowledge skills',
            'frontend': 'frontend react angular javascript',
            'backend': 'backend java python spring',
            'fullstack': 'fullstack frontend backend developer'
        }
        
        query_lower = query.lower()
        for key, expansion in tech_keywords.items():
            if key in query_lower:
                return f"{query} {expansion}"
        
        return query
    
    def _build_filters(self, constraints: Dict) -> Optional[Dict]:
        """Build filters from constraints - be less restrictive"""
        filters = {}
        
        if constraints.get('test_types') and len(constraints['test_types']) > 0:
            filters['test_type'] = constraints['test_types']
        
        if constraints.get('language'):
            filters['language'] = constraints['language']
        
        return filters if filters else None