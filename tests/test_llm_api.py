import pytest
from llm_api import GeminiAPI, Task
from unittest.mock import Mock, patch
import json

@pytest.fixture
def gemini_api():
    return GeminiAPI(api_key="fake_key", model_name="gemini-2.5-flash")

def test_convert_task(gemini_api):
    # Create a sample task
    task = Task(title="Test Task", body="Test task description")
    
    # Convert task to string
    result = gemini_api._convert_task(task)
    
    # Check if result is a string and contains task information
    assert isinstance(result, str)
    assert "Test Task" in result
    assert "Test task description" in result

@pytest.mark.asyncio
async def test_convert_response(gemini_api):
    # Create a mock response with valid JSON
    mock_response = Mock()
    mock_response.text = json.dumps([
        {
            "title": "Subtask 1",
            "body": "Description 1",
        },
        {
            "title": "Subtask 2",
            "body": "Description 2",
        }
    ])
    
    # Convert response to tasks
    tasks = gemini_api._convert_response(mock_response)
    
    # Verify the conversion
    assert isinstance(tasks, list)
    assert len(tasks) == 2
    assert all(isinstance(task, Task) for task in tasks)
    assert tasks[0].title == "Subtask 1"
    assert tasks[1].title == "Subtask 2"

@pytest.mark.asyncio
async def test_request_subtask(gemini_api):
    # Create a parent task
    parent_task = Task(title="Parent Task", body="Parent description")
    
    # Mock the Gemini API response
    mock_response = Mock()
    mock_response.text = json.dumps([
        {
            "title": "Child Task",
            "body": "Child description",
        }
    ])
    
    # Mock the generate_content method
    with patch.object(gemini_api.client.models, 'generate_content', return_value=mock_response):
        # Request subtasks
        subtasks = gemini_api.request_subtask(parent_task)
        
        # Verify the result
        assert isinstance(subtasks, list)
        assert len(subtasks) == 1
        assert subtasks[0].title == "Child Task"
        assert subtasks[0].body == "Child description"

def test_gemini_api_initialization():
    # Test initialization with valid parameters
    api = GeminiAPI(api_key="test_key", model_name="gemini-2.5-flash")
    assert api.model_name == "gemini-2.5-flash"
    assert isinstance(api.system_prompt, str)  # Check if system prompt is loaded