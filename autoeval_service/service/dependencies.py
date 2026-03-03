from typing import Optional

from .autoeval_database import AutoEvalDatabase, init_autoeval_database_instance

# Global state
_autoeval_database_instance: Optional[AutoEvalDatabase] = None


def get_autoeval_database() -> AutoEvalDatabase:
    """Get PLM database instance"""
    global _autoeval_database_instance
    if not _autoeval_database_instance:
        _autoeval_database_instance = init_autoeval_database_instance()
    return _autoeval_database_instance
