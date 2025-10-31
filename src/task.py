from dataclasses import dataclass, field, asdict
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
    _id: str = field(default_factory=_generate_id, init=False, repr=False) 
    _created_at: datetime = field(init=False)
    _updated_at: datetime = field(init=False)

    def __post_init__(self):
        """Initializes audit data fields (_created_at and _updated_at)."""
        # Store all audit timestamps in UTC
        now_utc = datetime.now(timezone.utc)
        self._created_at = now_utc
        self._updated_at = now_utc
        
    def __str__(self):
        return f"Task(ID: {self._id[:8]}..., Title: '{self.title}', Status: {self.status.name}, Updated: {self._updated_at.isoformat()})"

    def mark_updated(self):
        """Manually updates the _updated_at timestamp when a modification occurs."""
        self._updated_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> dict:
        """Converts the Task object to a dictionary, handling custom types."""
        data = asdict(self)
        
        # Handle Enum types
        data['status'] = self.status.name
        data['priority'] = self.priority.name
        
        # Handle datetime objects
        if self.due_date:
            data['due_date'] = self.due_date.isoformat()
        data['_created_at'] = self._created_at.isoformat()
        data['_updated_at'] = self._updated_at.isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Creates a Task object from a dictionary, handling custom types and audit data."""
        
        # Prepare data for Task's __init__ (core data)
        init_fields = {
            f.name 
            for f in cls.__dataclass_fields__.values() 
            if f.init
        }
        
        # Filter the loaded data to only include core data
        init_data = {}
        for key in init_fields:
            if key in data:
                value = data[key]
                
                # Type Conversion for Core Data (Handles Enums and Datetime)
                if key == 'status':
                    init_data[key] = Status[value]
                elif key == 'priority':
                    init_data[key] = Priority[value]
                elif key == 'due_date' and value:
                    init_data[key] = datetime.fromisoformat(value)

        # Create the Task object
        new_task = cls(**init_data)
        
        # Override audit fields with loaded data
        audit_fields = {
            f.name 
            for f in cls.__dataclass_fields__.values() 
            if not f.init 
        }
        
        for key in audit_fields:
            if key in data:
                value = data[key]
                
                # Type Conversion for Audit Data
                if key in ('_created_at', '_updated_at'):
                    setattr(new_task, key, datetime.fromisoformat(value))
                elif key == '_id':
                    setattr(new_task, key, value)
                
        return new_task