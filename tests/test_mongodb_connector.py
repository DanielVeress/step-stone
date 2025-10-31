import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Import classes from your modules
from task import Task, Status, Priority
from db_connector import MongoDBConnector, _prepare_updates

# --- Fixtures ---

@pytest.fixture
def mock_mongo():
    """
    Fixture to patch 'pymongo.MongoClient' where it's used in 'mongodb_connector'.
    Yields the constructor mock, the client instance mock, and the collection mock.
    """
    with patch('pymongo.MongoClient', autospec=True) as mock_MongoClient_constructor:
        # 1. Mock the client instance that the constructor returns
        mock_client_instance = mock_MongoClient_constructor.return_value
        
        # 2. Mock the database selection (e.g., client['db_name'])
        mock_db = MagicMock()
        mock_client_instance.__getitem__.return_value = mock_db
        
        # 3. Mock the collection selection (e.g., db['coll_name'])
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        
        yield mock_MongoClient_constructor, mock_client_instance, mock_collection

@pytest.fixture
def connector(mock_mongo):
    """
    Provides a MongoDBConnector instance that is already 'connected'
    using the mocked MongoClient.
    
    Yields the connector instance and the mock_collection for assertions.
    """
    # Unpack the mocks from the 'mock_mongo' fixture
    _constructor, _client_instance, mock_collection = mock_mongo
    
    # Create the connector
    conn = MongoDBConnector(
        connection_uri="mongodb://mock_host:27017",
        database_name="mock_db",
        collection_name="mock_tasks"
    )
    
    # Call the connect method, which will use the patched MongoClient
    conn.connect()
    
    # Yield the connector and the mock collection for tests to use
    yield conn, mock_collection

@pytest.fixture
def sample_task():
    """Provides a sample Task object for testing."""
    task = Task(
        title="Test Task",
        body="This is a body",
        priority=Priority.HIGH,
        due_date=datetime(2025, 12, 25, 12, 0, 0, tzinfo=timezone.utc)
    )
    # Manually fix timestamps for predictable testing
    task._created_at = datetime(2025, 10, 31, 10, 0, 0, tzinfo=timezone.utc)
    task._updated_at = datetime(2025, 10, 31, 10, 0, 0, tzinfo=timezone.utc)
    return task


# --- Tests for _prepare_updates ---

def test_prepare_updates_enums_and_datetime():
    """Tests conversion of Enum and datetime objects."""
    dt = datetime.now(timezone.utc)
    updates = {
        "status": Status.COMPLETED,
        "priority": Priority.LOW,
        "due_date": dt
    }
    prepared = _prepare_updates(updates)
    assert prepared == {
        "status": "COMPLETED",
        "priority": "LOW",
        "due_date": dt  # Datetime object is passed through (astimezone is called)
    }
    assert prepared["due_date"].tzinfo == timezone.utc

def test_prepare_updates_filters_ids():
    """Tests that _id and created_at are filtered out."""
    updates = {
        "_id": "should_be_removed",
        "created_at": "should_also_be_removed",
        "title": "New Title"
    }

    prepared = _prepare_updates(updates)
    assert prepared == {"title": "New Title"}

def test_prepare_updates_handles_other_types():
    """Tests that standard types are passed through."""
    updates = {
        "title": "New Title",
        "estimated_time": 120,
        "parent_id": "parent_uuid"
    }
    prepared = _prepare_updates(updates)
    assert prepared == {
        "title": "New Title",
        "estimated_time": 120,
        "parent_id": "parent_uuid"
    }

# --- Tests for MongoDBConnector ---

def test_connect_success(connector, mock_mongo):
    """Tests if connect() correctly calls MongoClient and sets up attributes."""
    conn, mock_collection = connector
    mock_MongoClient_constructor, _client_inst, _coll = mock_mongo

    # 1. Assert MongoClient was called with the correct URI
    mock_MongoClient_constructor.assert_called_once_with("mongodb://mock_host:27017")
    
    # 2. Assert the internal attributes are set
    assert conn._client is not None
    assert conn._db is not None
    assert conn._task_collection is not None
    
    # 3. Assert the correct database and collection were accessed
    conn._client.__getitem__.assert_called_with("mock_db")
    conn._db.__getitem__.assert_called_with("mock_tasks")

def test_connect_import_error():
    """Tests if RuntimeError is raised if pymongo is not installed."""
    # Simulate an ImportError when 'mongodb_connector.MongoClient' is accessed
    with patch('pymongo.MongoClient', side_effect=ImportError("No module named 'pymongo'")):
        conn = MongoDBConnector("uri", "db", "coll")
        
        with pytest.raises(RuntimeError, match="pymongo is not installed"):
            conn.connect()

def test_close(connector, mock_mongo):
    """Tests if close() calls the client's close method."""
    conn, _collection = connector
    _constructor, mock_client_instance, _collection = mock_mongo
    
    conn.close()
    
    mock_client_instance.close.assert_called_once()

def test_add_task(connector, sample_task):
    """Tests if add_task() serializes the task and calls insert_one."""
    conn, mock_collection = connector
    
    # Configure the mock return value for insert_one
    mock_collection.insert_one.return_value = MagicMock(acknowledged=True)
    
    result = conn.add_task(sample_task)
    
    assert result is True
    
    # Check that insert_one was called with the correct, serialized data
    expected_dict = sample_task.to_dict()
    mock_collection.insert_one.assert_called_once_with(expected_dict)

def test_delete_task_success(connector):
    """Tests if delete_task() calls delete_one and returns True on success."""
    conn, mock_collection = connector
    
    # Configure mock return value
    mock_collection.delete_one.return_value = MagicMock(deleted_count=1)
    
    task_id = "test_task_id_123"
    result = conn.delete_task(task_id)
    
    assert result is True
    mock_collection.delete_one.assert_called_once_with({"_id": task_id})

def test_delete_task_not_found(connector):
    """Tests if delete_task() returns False when no document is deleted."""
    conn, mock_collection = connector
    
    # Configure mock return value
    mock_collection.delete_one.return_value = MagicMock(deleted_count=0)
    
    task_id = "non_existent_id"
    result = conn.delete_task(task_id)
    
    assert result is False
    mock_collection.delete_one.assert_called_once_with({"_id": task_id})

def test_get_task_success(connector, sample_task):
    """Tests if get_task() calls find_one and deserializes the data into a Task."""
    conn, mock_collection = connector
    
    # Prepare the data as it would come from Mongo
    task_dict = sample_task.to_dict()
    mock_collection.find_one.return_value = task_dict
    
    retrieved_task = conn.get_task(sample_task._id)
    
    # Check that find_one was called correctly
    mock_collection.find_one.assert_called_once_with({"_id": sample_task._id})
    
    # Check that the data was correctly deserialized
    assert isinstance(retrieved_task, Task)
    assert retrieved_task._id == sample_task._id
    assert retrieved_task.title == sample_task.title
    assert retrieved_task.priority == Priority.HIGH
    assert retrieved_task._created_at == sample_task._created_at

def test_get_task_not_found(connector, capsys):
    """
    Tests if get_task() returns None and prints an error when find_one
    returns None (which causes Task.from_dict to fail in the try...except block).
    """
    conn, mock_collection = connector
    
    # Simulate find_one returning nothing
    mock_collection.find_one.return_value = None
    
    task_id = "not_found_id"
    retrieved_task = conn.get_task(task_id)
    
    # Assert it returns None as per the except block
    assert retrieved_task is None
    
    # Assert the correct query was made
    mock_collection.find_one.assert_called_once_with({"_id": task_id})
    
    # Assert that an error was printed (as per the except block)
    captured = capsys.readouterr()
    assert "Error retrieving task" in captured.out

def test_update_task_success(connector):
    """Tests if update_task() prepares data and calls update_one successfully."""
    conn, mock_collection = connector
    
    # Configure mock return value
    mock_collection.update_one.return_value = MagicMock(modified_count=1)
    
    task_id = "task_to_update_123"
    updates = {
        "title": "A New Title",
        "status": Status.IN_PROGRESS,
        "due_date": datetime(2026, 1, 1, tzinfo=timezone.utc)
    }
    
    result = conn.update_task(task_id, updates)
    
    assert result is True
    
    # Check that the updates were correctly prepared for MongoDB
    expected_mongo_update = {
        "$set": {
            "title": "A New Title",
            "status": "IN_PROGRESS",
            "due_date": datetime(2026, 1, 1, tzinfo=timezone.utc)
        }
    }
    
    mock_collection.update_one.assert_called_once_with(
        filter={"_id": task_id},
        update=expected_mongo_update
    )

def test_update_task_no_modification(connector):
    """Tests if update_task() returns False if modified_count is 0."""
    conn, mock_collection = connector
    
    # Configure mock return value
    mock_collection.update_one.return_value = MagicMock(modified_count=0)
    
    task_id = "task_123"
    updates = {"title": "Same Old Title"}
    
    result = conn.update_task(task_id, updates)
    
    assert result is False

def test_update_task_filters_ids_and_returns_false(connector):
    """
    Tests if update_task() returns False and does not call update_one
    if all updates are filtered out by _prepare_updates.
    """
    conn, mock_collection = connector
    
    task_id = "task_123"
    # These fields are filtered out by _prepare_updates
    updates = {
        "_id": "new_id_attempt",
        "created_at": "new_date_attempt"
    }
    
    result = conn.update_task(task_id, updates)
    
    # Result should be False because prepared_updates was empty
    assert result is False
    
    # Database should not have been called
    mock_collection.update_one.assert_not_called()