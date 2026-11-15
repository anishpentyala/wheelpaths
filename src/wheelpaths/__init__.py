"""Offline lexical installation path plans. Never installs or imports a wheel."""
from .planner import audit, InvalidPlan, Limits

__all__ = ['audit', 'InvalidPlan', 'Limits']
