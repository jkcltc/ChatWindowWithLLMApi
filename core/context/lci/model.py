from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set

@dataclass(frozen=True)
class LCIValidationReport:
    is_empty: bool = True
    is_copy: bool = False
    anchor_found: bool = False
    ids_valid: bool = False
    
    anchor_id: str = ""
    related_ids: Tuple[str, ...] = field(default_factory=tuple)
    missing_id: Optional[str] = None

    summary_ratio: float = 0.0
    
    error_msg: str = ""
    
    @property
    def is_valid(self) -> bool:
        return not bool(self.error_msg)


