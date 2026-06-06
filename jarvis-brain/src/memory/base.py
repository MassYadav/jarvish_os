from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseMemoryProvider(ABC):
    @abstractmethod
    def get_user_context(self, user_id: str) -> Dict[str, Any]:
        pass