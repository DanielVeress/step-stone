from datetime import datetime, timezone, timedelta
import pytest
from task import Task, Status, Priority

@pytest.fixture
def sample_task():
    """A pytest fixture to provide a basic Task instance."""
    return Task(title="Buy Groceries")

@pytest.fixture
def full_task():
    """A pytest fixture to provide a Task instance with all options set."""
    return Task(
        title="Write Report",
        body="Draft the Q3 financial summary.",
        status=Status.IN_PROGRESS,
        priority=Priority.HIGH,
        due_date=datetime(2025, 12, 31, 17, 0, 0, tzinfo=timezone.utc),
        estimated_time=120,
    )

def test_task_initialization(sample_task):
    """Test that a task is created with the required title and correct defaults."""
    assert sample_task.title == "Buy Groceries"
    assert sample_task.body == ""
    assert sample_task.status == Status.TODO
    assert sample_task.priority == Priority.MEDIUM
    assert sample_task.estimated_time == 0
    assert sample_task.parent_id is None
    assert sample_task.due_date is None

def test_task_full_initialization(full_task):
    """Test that a task is created correctly when all fields are provided."""
    assert full_task.title == "Write Report"
    assert full_task.body == "Draft the Q3 financial summary."
    assert full_task.status == Status.IN_PROGRESS
    assert full_task.priority == Priority.HIGH
    assert full_task.estimated_time == 120
    assert full_task.due_date.year == 2025 # Check a specific field of the datetime
    assert full_task.due_date.tzinfo == timezone.utc # Check that it is timezone aware

def test_id_generation():
    """Test that the ID is a unique string (UUID)."""
    task1 = Task(title="Test 1")
    task2 = Task(title="Test 2")
    
    # Check type and format
    assert isinstance(task1._id, str)
    assert len(task1._id) == 36 # Standard UUID length (including hyphens)
    
    # Check uniqueness
    assert task1._id != task2._id

def test_audit_timestamps(sample_task):
    """Test that created_at and updated_at are set to the same UTC time."""
    now_utc = datetime.now(timezone.utc)
    
    # Check that timestamps are datetimes and are timezone-aware (UTC)
    assert isinstance(sample_task._created_at, datetime)
    assert sample_task._created_at.tzinfo == timezone.utc
    assert sample_task._updated_at.tzinfo == timezone.utc
    
    # Check that created_at and updated_at are the same at creation
    assert sample_task._created_at == sample_task._updated_at
    
    # Check that the time is very recent (within a small delta)
    time_difference = now_utc - sample_task._created_at
    # Allow for a small difference (e.g., 1 second) for test execution time
    assert abs(time_difference) < timedelta(seconds=1)

def test_mark_updated(sample_task):
    """Test that the mark_updated method updates the updated_at timestamp."""
    initial_updated_at = sample_task._updated_at
    
    # Simulate a time passing
    import time
    time.sleep(0.01) # Wait a small amount of time
    
    sample_task.mark_updated()
    
    # The new updated_at should be greater than the initial one
    assert sample_task._updated_at > initial_updated_at
    
    # The created_at should remain unchanged
    assert sample_task._created_at == initial_updated_at 

def test_enum_assignment():
    """Test setting different enum values explicitly."""
    task = Task(title="Review PR", status=Status.COMPLETED, priority=Priority.TOP)
    assert task.status is Status.COMPLETED
    assert task.priority is Priority.TOP

def test_str_representation(sample_task):
    """Test the custom __str__ method."""
    str_output = str(sample_task)
    assert sample_task._id[:8] in str_output # Check for truncated ID
    assert sample_task.title in str_output
    assert sample_task.status.name in str_output
    assert "Task(" in str_output