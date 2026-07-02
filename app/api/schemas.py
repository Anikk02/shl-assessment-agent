# app/api/schemas.py
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime


class Message(BaseModel):
    """Single conversation message"""
    role: str = Field(..., description="Role of the message sender (user or assistant)")
    content: str = Field(..., description="Message content")
    
    @validator('role')
    def validate_role(cls, v: str) -> str:
        """Validate role is either user or assistant"""
        if v not in ['user', 'assistant']:
            raise ValueError(f"Role must be 'user' or 'assistant', got {v}")
        return v


class ChatRequest(BaseModel):
    """Chat endpoint request body"""
    messages: List[Message] = Field(
        ..., 
        min_items=1, 
        max_items=8,
        description="Conversation history (max 8 turns)"
    )
    
    @validator('messages')
    def validate_messages(cls, v: List[Message]) -> List[Message]:
        """Ensure messages alternate correctly"""
        if len(v) > 0:
            # First message must be from user
            if v[0].role != 'user':
                raise ValueError("First message must be from user")
            
            # Check alternation
            for i in range(1, len(v)):
                if v[i].role == v[i-1].role:
                    raise ValueError(f"Messages must alternate roles, found {v[i].role} after {v[i-1].role}")
        return v


class Recommendation(BaseModel):
    """Single recommendation item"""
    name: str = Field(..., description="Assessment name from catalog")
    url: str = Field(..., description="SHL catalog URL")
    test_type: str = Field(..., description="Test type code: K, P, A, B, S, C, D, O")
    
    @validator('url')
    def validate_url(cls, v: str) -> str:
        """Validate URL is from SHL domain"""
        if not v.startswith('https://www.shl.com/'):
            raise ValueError("URL must be from SHL domain")
        return v


class ChatResponse(BaseModel):
    """Chat endpoint response body"""
    reply: str = Field(..., description="Agent's reply text", min_length=1)
    recommendations: List[Recommendation] = Field(
        default_factory=list,
        description="Recommended assessments (empty when gathering context or refusing)"
    )
    end_of_conversation: bool = Field(
        default=False,
        description="True only when the agent considers the task complete"
    )
    
    @validator('recommendations')
    def validate_recommendations(cls, v: List[Recommendation]) -> List[Recommendation]:
        """Ensure recommendations are between 0 and 10"""
        if len(v) > 10:
            raise ValueError(f"Too many recommendations: {len(v)} (max 10)")
        return v


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(default="ok", description="Service status")
    timestamp: datetime = Field(default_factory=datetime.now, description="Current timestamp")