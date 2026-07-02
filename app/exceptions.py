# app/exceptions.py
"""Custom exceptions for SHL Assessment Agent"""


class SHLAgentError(Exception):
    """Base exception for SHL agent"""
    pass


class CatalogError(SHLAgentError):
    """Catalog-related errors"""
    pass


class RetrievalError(SHLAgentError):
    """Retrieval-related errors"""
    pass


class LLMError(SHLAgentError):
    """LLM-related errors"""
    pass


class ValidationError(SHLAgentError):
    """Validation errors"""
    pass


class ConfigError(SHLAgentError):
    """Configuration errors"""
    pass


class IndexError(SHLAgentError):
    """Index-related errors"""
    pass