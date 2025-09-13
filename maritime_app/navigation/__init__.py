"""
Maritime Navigation Module
=========================

Professional maritime navigation calculations for course planning and tracking.
"""

from .maritime_navigation import (
    MaritimeNavigation,
    Position,
    CourseResult,
    CrossTrackError
)

__all__ = [
    'MaritimeNavigation',
    'Position', 
    'CourseResult',
    'CrossTrackError'
]
