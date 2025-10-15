# app/plm_leaderboard/dependencies.py
from pathlib import Path
from typing import Optional
from fastapi import Depends

from .plm_leaderboard_database import PLMLeaderboardDatabase, init_leaderboard_database_instance
from .service import PLMLeaderboardService

# Global state
_plm_database_instance: Optional[PLMLeaderboardDatabase] = None


def get_plm_leaderboard_database() -> PLMLeaderboardDatabase:
    """Get PLM database instance"""
    global _plm_database_instance
    if not _plm_database_instance:
        raise RuntimeError("PLM database not initialized")
    return _plm_database_instance


def get_plm_leaderboard_service(
        database: PLMLeaderboardDatabase = Depends(get_plm_leaderboard_database)
) -> PLMLeaderboardService:
    """Get PLM service with injected database"""
    return PLMLeaderboardService(database)


def init_plm_leaderboard_dependencies(backup_data: Optional[Path] = None):
    """Initialize PLM module dependencies"""
    global _plm_database_instance
    _plm_database_instance = init_leaderboard_database_instance(backup_data=backup_data)
