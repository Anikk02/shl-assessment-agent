# app/logger.py
import logging
import sys
from pathlib import Path
from typing import Optional

from .config import config


class Logger:
    """Application logger with file and console handlers"""
    
    _instance: Optional[logging.Logger] = None
    
    @classmethod
    def get_logger(cls, name: str = "shl_agent") -> logging.Logger:
        """Get or create logger instance"""
        if cls._instance is None:
            cls._instance = cls._setup_logger(name)
        return cls._instance
    
    @classmethod
    def _setup_logger(cls, name: str) -> logging.Logger:
        """Setup logger with console and file handlers"""
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
        
        # Prevent duplicate handlers
        if logger.handlers:
            return logger
        
        # Console handler
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console.setFormatter(console_format)
        logger.addHandler(console)
        
        # File handler
        try:
            log_dir = Path("data/logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(config.log_file)
            file_handler.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
            file_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
        except Exception:
            pass  # File logging is optional
        
        return logger


# Convenience function
def get_logger(name: str = "shl_agent") -> logging.Logger:
    """Get logger instance"""
    return Logger.get_logger(name)