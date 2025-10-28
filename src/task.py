from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid

def _generate_id() -> str:
    """Generates a unique UUID as a string."""
    return str(uuid.uuid4())

class Status(Enum):
    """Represents the completion status of a task."""
    TODO = 1
    IN_PROGRESS = 2
    COMPLETED = 3
    
class Priority(Enum):
    """Represents the urgency of a task."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    TOP = 4

@dataclass
class Task:
    """A task object that stores all the data for the task."""
    
    # Core data
    title: str
    body: str = ""
    parent_id: Optional[str] = None 
    status: Status = Status.TODO
    priority: Priority = Priority.MEDIUM
    due_date: Optional[datetime] = None
    estimated_time: int = 0
    
    # Audit data (auto-generated)
    id: str = field(default_factory=_generate_id, init=False, repr=False) 
    created_at: datetime = field(init=False)
    updated_at: datetime = field(init=False)

    def __post_init__(self):
        """Initializes audit data fields (created_at and updated_at)."""
        # Store all audit timestamps in UTC
        now_utc = datetime.now(timezone.utc)
        self.created_at = now_utc
        self.updated_at = now_utc

    def mark_updated(self):
        """Manually updates the updated_at timestamp when a modification occurs."""
        self.updated_at = datetime.now(timezone.utc)

    def __str__(self):
        return f"Task(ID: {self.id[:8]}..., Title: '{self.title}', Status: {self.status.name}, Updated: {self.updated_at.isoformat()})"