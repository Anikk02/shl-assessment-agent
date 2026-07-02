# app/api/routes.py
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any

from .schemas import ChatRequest, ChatResponse, HealthResponse
from ..agent.orchestrator import AgentOrchestrator
from ..catalog.loader import CatalogLoader
from ..catalog.indexer import CatalogIndexer
from ..catalog.retriever import CatalogRetriever
from ..llm.client import LLMClient
from ..logger import get_logger
from ..exceptions import SHLAgentError, CatalogError

logger = get_logger(__name__)

router = APIRouter()

# Global components (lazy initialized)
_indexer = None
_retriever = None
_llm_client = None
_orchestrator = None
_catalog_loader = None


def initialize_components():
    """Initialize all components on first request"""
    global _indexer, _retriever, _llm_client, _orchestrator, _catalog_loader
    
    if _orchestrator is not None:
        return
    
    try:
        logger.info("Initializing components...")
        
        # Load catalog
        _catalog_loader = CatalogLoader()
        catalog_data = _catalog_loader.load()
        logger.info(f"Loaded {len(catalog_data)} catalog items")
        
        # Build or load index
        _indexer = CatalogIndexer()
        if not _indexer.load_index():
            logger.info("Building index from catalog...")
            _indexer.build_index(catalog_data)
            _indexer.save_index()
        logger.info(f"Index loaded with {_indexer.size} items")
        
        # Initialize retriever, LLM, and orchestrator
        _retriever = CatalogRetriever(_indexer)
        _llm_client = LLMClient()
        _orchestrator = AgentOrchestrator(_retriever, _llm_client)
        
        logger.info("All components initialized successfully")
        
    except CatalogError as e:
        logger.error(f"Catalog initialization failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Component initialization failed: {e}", exc_info=True)
        raise


def get_orchestrator() -> AgentOrchestrator:
    """Dependency injection for agent orchestrator"""
    initialize_components()
    return _orchestrator


@router.get("/health", response_model=HealthResponse)
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for service readiness"""
    try:
        # Try to initialize components
        initialize_components()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "degraded"}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
) -> ChatResponse:
    """
    Process a chat turn and return agent response.
    
    The agent will:
    - Clarify vague queries before recommending
    - Recommend 1-10 assessments when sufficient context is available
    - Support refinement when constraints change
    - Compare assessments when asked
    - Refuse out-of-scope requests
    """
    try:
        logger.info(f"Processing chat with {len(request.messages)} messages")
        
        # Convert to dict format for agent
        messages = [msg.dict() for msg in request.messages]
        
        # Process through agent
        result = orchestrator.process(messages)
        
        # Build response
        response = ChatResponse(
            reply=result['reply'],
            recommendations=result.get('recommendations', []),
            end_of_conversation=result.get('end_of_conversation', False)
        )
        
        logger.info(
            f"Response: end={response.end_of_conversation}, "
            f"recommendations={len(response.recommendations)}"
        )
        
        return response
        
    except SHLAgentError as e:
        logger.error(f"Agent error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")