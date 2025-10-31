from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from task import Task

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
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
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
    
    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        pass
    
if __name__ == "__main__":
    connection_uri = "mongodb://127.0.0.1:27017"
    database_name = "task_db"
    collection_name = "tasks"
    connector = MongoDBConnector(connection_uri, database_name, collection_name)
    
    connector.connect()
    
    ## Do stuff...
    connector.add_task(Task("Test_Title"))
    
    
    connector.close()