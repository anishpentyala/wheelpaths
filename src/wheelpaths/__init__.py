"""Offline lexical installation path plans. Never installs or imports a wheel."""
from .planner import audit, InvalidPlan

__all__ = ['audit', 'InvalidPlan']
