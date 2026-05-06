from __future__ import annotations
from dataclasses import dataclass

@dataclass
class User:
    username: str
    role: str
    is_active: bool = True


__all__ = ["User"]