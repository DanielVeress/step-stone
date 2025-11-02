from abc import ABC, abstractmethod
import yaml
import json
from typing import List
import pydantic
from google import genai
from google.genai import types
from task import Task, TaskInput

"""
The responsibility of the LLM API class is to handle requests and responses.
It should convert the response into a usable and generic format or class.
"""

def load_prompts(file_path="config/prompts.yml"):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

PROMPTS = load_prompts()

class AbstractLLMAPI(ABC):   
    """Abstract class for handling API requests from LLM providers."""
    @abstractmethod
    def _convert_response(self, response) -> Task:
        pass
    
    @abstractmethod
    def _convert_task(self, task: Task) -> str:
        pass
    
    @abstractmethod
    def request_subtask(parent_task: Task) -> str:
        """Requests a subtask from the LLM model."""
        pass
    
class GeminiAPI(AbstractLLMAPI):
    """Handles the API requests from Gemini API."""
    
    def __init__(self, api_key: str, model_name: str):
        super().__init__()
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name # "gemini-2.5-flash"
        self.system_prompt = PROMPTS["system_prompt"]
        self.content_config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            thinking_config=types.ThinkingConfig(thinking_budget=0), # to disable thinking
            response_mime_type="application/json",
            response_schema=list[TaskInput]
        )

    def _convert_task(self, task: Task) -> str:
        # TODO: think about the need to include parent tasks
        return str(task)
    
    def _convert_response(self, response) -> List[Task]:
        # Validate the JSON array against the List[TaskInput] structure
        validated_list: List[TaskInput] = pydantic.TypeAdapter(List[TaskInput]).validate_json(response.text)
        
        # Convert the list of TaskInput Pydantic models to a list of Task objects
        subtasks = []
        for task_input_model in validated_list:
            task_data_dict = task_input_model.model_dump() # converts to dict
            subtasks.append(Task.from_dict(task_data_dict))
        
        return subtasks

    def request_subtask(self, parent_task: Task) -> Task:
        # Set-up
        prompt = self._convert_task(parent_task)
        
        # Get response
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=self.content_config
        )
        
        # Convert response to subtasks
        subtasks = self._convert_response(response) 
        
        return subtasks
    
if __name__ == "__main__":
    task = Task(
        title="Make a project that breaks down tasks.",
        body="Make a python project that breaks down tasks into subtasks for the user.\n\
              The main technologies:\n\
              - python, gemini API, gradio for UI and MongoDB for database\n\
              Features:\n\
              - user can create root tasks\n\
              - user can ask for a breakdown for the task" 
    )
    
    import os
    from dotenv import load_dotenv
    load_dotenv()
    API_KEY = os.getenv("GEMINI_API_KEY")
    
    gemini_api_con = GeminiAPI(api_key=API_KEY, model_name="gemini-2.5-flash")
    subtasks = gemini_api_con.request_subtask(task)
    print(subtasks)
