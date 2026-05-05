"""Reworked module for toolkit.core.py"""
from abc import ABC, abstractmethod
from typing import Any, Dict

class ToolKernel(ABC):
    name: str = 'base_tool'
    description: str = 'Base tool interface'

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

    def validate_inputs(self, required_keys: list, kwargs: dict):
        missing = [key for key in required_keys if key not in kwargs]
        if missing:
            raise ValueError(f'[{self.name}] Missing required inputs: {missing}')
