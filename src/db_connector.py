from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone
from task import Task, Priority, Status

def _prepare_updates(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Converts Task-specific types in the updates dictionary for MongoDB."""
    prepared = {}
    
    for key, value in updates.items():
        # Ignore ID fields
        if key in ('_id', 'created_at'):
            continue
            
        # Handle Enum types
        if isinstance(value, (Status, Priority)):
            prepared[key] = value.name
        # Handle Datetime objects
        elif isinstance(value, datetime):
            prepared[key] = value.astimezone(timezone.utc)
        else:
            prepared[key] = value
            
    return prepared

class AbstractDBConnector(ABC):
    """An abstract class that defines the required interface for any database connector."""

    @abstractmethod
    def connect(self) -> None:
        """Establishes the database connection."""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""
        pass

    @abstractmethod
    def add_task(self, task_data: Dict[str, Any]) -> None:
        """Adds a new task to the database."""
        pass

    @abstractmethod
    def delete_task(self, task_id: str) -> bool:
        """Deletes a task from the database by its ID."""
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Task:
        """Retrieves a task from the database by its ID."""
        pass

    @abstractmethod
    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """Updates an existing task in the database."""
        pass
    
class MongoDBConnector(AbstractDBConnector):
    """A concrete implementation for connecting to a MongoDB database."""

    def __init__(self, connection_uri: str, database_name: str, collection_name: str):
        self.connection_uri = connection_uri
        self.database_name = database_name
        self.collection_name = collection_name
        self._client = None
        self._db = None
        self._task_collection = None

    def connect(self) -> None:
        try:
            from pymongo import MongoClient # Import inside the method or class to avoid hard dependency until used
            self._client = MongoClient(self.connection_uri)
            self._db = self._client[self.database_name]
            self._task_collection = self._db[self.collection_name]
        except ImportError:
            raise RuntimeError("pymongo is not installed. Install it to use MongoDBConnector.")
        except Exception as e:
            print(f"Connection failed: {e}")

    def close(self) -> None:
        self._client.close()

    def add_task(self, task: Task) -> bool:
        task_data = task.to_dict()
        results = self._task_collection.insert_one(task_data)
        return results.acknowledged
    
    def delete_task(self, task_id: str) -> bool:
        result = self._task_collection.delete_one({"_id": task_id})
        return result.deleted_count == 1

    def get_task(self, task_id: str) -> Task:        
        try:
            task_data = self._task_collection.find_one({"_id": task_id})
            return Task.from_dict(task_data)
        except Exception as e:
            print(f"Error retrieving task: {e}")
            return None
    
    def get_all_tasks(self) -> List[Task]:
        """Retrieves all tasks from the database."""
        tasks: List[Task] = []
        try:
            # Use find({}) to get all documents in the collection
            cursor = self._task_collection.find({})
            
            # Iterate through the cursor and convert each document to a Task object
            for task_data in cursor:
                tasks.append(Task.from_dict(task_data))
                
        except Exception as e:
            print(f"Error retrieving all tasks: {e}")
            
        return tasks
    
    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        # Prepare and clean the updates dictionary
        prepared_updates = _prepare_updates(updates)

        if not prepared_updates:
            # Nothing to update after filtering ID/audit fields
            return False 
        
        result = self._task_collection.update_one(
            # Use _id for filtering
            filter={"_id": task_id},
            # Use the $set operator with the cleaned updates
            update={"$set": prepared_updates}
        )
        
        return result.modified_count == 1
    
if __name__ == "__main__":
    connection_uri = "mongodb://127.0.0.1:27017"
    database_name = "task_db"
    collection_name = "tasks"
    connector = MongoDBConnector(connection_uri, database_name, collection_name)
    
    connector.connect()
    
    ## Do stuff...
    task = Task(
        title="Do Laundry",
        body="You have to do the laundry today."
    )
    task_id = task._id
    connector.add_task(task)
    
    print(connector.get_all_tasks())
    
    connector.close()