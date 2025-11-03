import gradio as gr
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List
import os
from dotenv import load_dotenv
from task import Task, Status, Priority
from db_connector import MongoDBConnector
from llm_api import GeminiAPI
import pandas as pd

# Load environment variables
load_dotenv()

# Initialize database connection
db = MongoDBConnector(
    connection_uri="mongodb://127.0.0.1:27017",
    database_name="task_db",
    collection_name="tasks"
)
db.connect()

# Initialize Gemini API
gemini_api = GeminiAPI(
    api_key=os.getenv("GEMINI_API_KEY"),
    model_name="gemini-2.5-flash"
)

def create_or_update_task(
    title: str,
    body: str,
    parent_id: str,
    status_val: str,
    priority_val: str,
    due_date_str: str,
    estimated_time: float,
    current_task_state: Optional[Task],
    task_id_display: str,
    created_at_display: str
) -> Tuple[Task, str, str, str, str]:
    """
    Creates a new Task object or updates the existing one from the UI inputs.
    Returns the updated task object, a Markdown summary, and the new audit data.
    """
    
    # 1. Prepare Data for Task object
    data = {
        'title': title,
        'body': body,
        # Gradio Datetime returns a string (or None if not set)
        'due_date': due_date_str, 
        'estimated_time': int(estimated_time), # gr.Number returns float, cast to int
        'status': status_val,
        'priority': priority_val,
        'parent_id': parent_id if parent_id else None
    }
    
    # 2. Update/Create Task
    try:
        if current_task_state is None:
            # Create a brand new task
            new_task = Task.from_dict(data)
            # Save to database
            if db.add_task(new_task):
                gr.Info("New Task Created and Saved to Database!")
            else:
                gr.Warning("Task created but failed to save to database!")
            
        else:
            # Modify the existing task object
            new_task = current_task_state
            
            # Apply changes
            new_task.title = title
            new_task.body = body
            new_task.parent_id = parent_id if parent_id else None
            new_task.status = Status(status_val)
            new_task.priority = Priority(priority_val)
            new_task.estimated_time = int(estimated_time)

            # Handle due_date update
            if due_date_str:
                new_task.due_date = datetime.fromisoformat(due_date_str).astimezone(timezone.utc)
            else:
                new_task.due_date = None

            # Manually update the timestamp
            new_task.mark_updated()
            
            # Update in database
            if db.update_task(new_task._id, new_task.to_dict()):
                gr.Info(f"Task '{new_task.title}' Updated in Database!")
            else:
                gr.Warning("Failed to update task in database!")
            
    except Exception as e:
        gr.Warning(f"Error processing task: {e}")
        return current_task_state, "# Error", task_id_display, created_at_display, created_at_display

    # 3. Prepare Outputs
    task_summary = f"**Task Summary:**\n\n```\n{str(new_task)}\n```"
    updated_at_str = new_task._updated_at.isoformat().split('+')[0] + 'Z'

    # Return the updated Task object (for the State component), the summary, and the updated audit fields
    return new_task, task_summary, new_task._id, new_task._created_at.isoformat().split('+')[0] + 'Z', updated_at_str


def load_task_data(task_state: Optional[Task]) -> Dict[gr.components.Component, Any]:
    """
    Takes a Task object (from gr.State) and prepares the values for the UI components.
    """
    if task_state is None:
        return {
            title_tb: "",
            body_tb: "",
            parent_id_tb: "",
            status_dd: Status.TODO.value,
            priority_dd: Priority.MEDIUM.value,
            due_date_dt: None,
            estimated_time_num: 0,
            task_id_display_tb: "N/A (New Task)",
            created_at_display_tb: "N/A",
            updated_at_display_tb: "N/A",
            task_summary_md: "# Create a New Task"
        }

    # Gradio Datetime component expects a datetime object or None for its value
    due_date_val = task_state.due_date.astimezone(timezone.utc).replace(tzinfo=None) if task_state.due_date else None

    return {
        title_tb: task_state.title,
        body_tb: task_state.body,
        parent_id_tb: task_state.parent_id if task_state.parent_id else "",
        status_dd: task_state.status.value,
        priority_dd: task_state.priority.value,
        due_date_dt: due_date_val,
        estimated_time_num: task_state.estimated_time,
        task_id_display_tb: task_state._id,
        created_at_display_tb: task_state._created_at.isoformat().split('+')[0] + 'Z',
        updated_at_display_tb: task_state._updated_at.isoformat().split('+')[0] + 'Z',
        task_summary_md: f"# Task: {task_state.title}\n\n```\n{str(task_state)}\n```"
    }

def clear_form():
    """Resets all fields to create a new task."""
    return [
        gr.update(value=""),
        gr.update(value=""),
        gr.update(value=""),
        gr.update(value=Status.TODO.value),
        gr.update(value=Priority.MEDIUM.value),
        gr.update(value=None),
        gr.update(value=0),
        gr.update(value=None),
        gr.update(value="N/A (New Task)"),
        gr.update(value="N/A"),
        gr.update(value="N/A"),
        gr.update(value="# Create a New Task")
    ]

def load_task_list() -> List[List[str]]: # <-- Note the changed type hint
    """Loads all tasks from the database and formats them for the UI."""
    tasks = db.get_all_tasks()
    formatted_tasks_rows = []
    
    # This order MUST match your gr.Dataframe headers:
    # ["Task ID", "Title", "Status", "Priority", "Due Date", "Parent ID"]
    for task in tasks:
        row = [
            str(task._id),
            str(task.title),
            str(task.status.value),
            str(task.priority.value),
            task.due_date.isoformat().split('+')[0] + 'Z' if task.due_date else "Not Set",
            str(task.parent_id) if task.parent_id else "None"
        ]
        formatted_tasks_rows.append(row)
    
    return formatted_tasks_rows

def load_task_by_id(task_id: str) -> Optional[Task]:
    """Load a task from the database by its ID."""
    return db.get_task(task_id)

def generate_subtasks(task_id: str) -> str:
    """Generate subtasks for the given task using the LLM API."""
    try:
        # Get the parent task
        parent_task = db.get_task(task_id)
        if not parent_task:
            return "Error: Parent task not found!"
                
        # Generate subtasks using LLM
        subtasks = gemini_api.request_subtask(parent_task)
        if not subtasks:
            return "No subtasks were generated."
            
        # Save subtasks to database
        saved_count = 0
        for subtask in subtasks:
            if db.add_task(subtask):
                saved_count += 1
                gr.Info(f"Created subtask: {subtask.title}")
            else:
                gr.Warning(f"Failed to save subtask: {subtask.title}")
        
        return f"Successfully generated and saved {saved_count} subtasks!"
        
    except Exception as e:
        return f"Error generating subtasks: {str(e)}"

# --- Gradio UI Definition (Blocks) ---

with gr.Blocks(title="Task Management UI") as demo:
    gr.Markdown("# 📋 Task Management Editor")

    # State Components
    task_state = gr.State(None)  # Initialize with None to start with a new task
    
    with gr.Row():
        gr.Markdown("## Task List")
    
    with gr.Row():
        # Task List Table
        task_list = gr.Dataframe(
            headers=["Task ID", "Title", "Status", "Priority", "Due Date", "Parent ID"],
            datatype=["str", "str", "str", "str", "str", "str"],
            interactive=False,
            wrap=True,
            elem_id="task_list"  # Add an ID for potential CSS styling
        )
        
        # Refresh button for task list
        refresh_btn = gr.Button("🔄 Refresh Tasks", scale=1)

    with gr.Row():
        # --- Left Column: Input Fields (Core Data) ---
        with gr.Column(scale=2):
            gr.Markdown("## Core Task Data")
            
            # Title (String)
            title_tb = gr.Textbox(label="Title", info="A concise, descriptive title.", interactive=True)
            
            # Body (String - Multi-line)
            body_tb = gr.Textbox(label="Body/Description", lines=5, interactive=True)
            
            # Parent ID (Optional[str])
            parent_id_tb = gr.Textbox(label="Parent Task ID (Optional)", interactive=True, placeholder="Enter a UUID if this is a sub-task")

            with gr.Row():
                # Status (Enum)
                status_dd = gr.Dropdown(
                    label="Status",
                    choices=[e.value for e in Status],
                    value=Status.TODO.value,
                    interactive=True,
                    scale=1
                )
                
                # Priority (Enum)
                priority_dd = gr.Dropdown(
                    label="Priority",
                    choices=[e.value for e in Priority],
                    value=Priority.MEDIUM.value,
                    interactive=True,
                    scale=1
                )

            with gr.Row():
                # Due Date (Optional[datetime])
                due_date_dt = gr.DateTime(
                    label="Due Date (Optional)",
                    type="text", # ensures the output is a string for the handler
                    interactive=True,
                    scale=1
                )
                
                # Estimated Time (int)
                estimated_time_num = gr.Number(
                    label="Estimated Time (minutes)",
                    value=0,
                    minimum=0,
                    precision=0, # Forces integer input
                    interactive=True,
                    scale=1
                )
            
            # --- Action Buttons ---
            with gr.Row():
                submit_btn = gr.Button("💾 Save/Update Task", variant="primary")
                clear_btn = gr.Button("➕ Clear Form (New Task)", variant="secondary")
                generate_subtasks_btn = gr.Button("🔄 Generate Subtasks", variant="secondary", interactive=False)

        # --- Right Column: Output & Audit Data ---
        with gr.Column(scale=1):
            gr.Markdown("## Task Summary & Audit")
            
            # Summary Display (Markdown/str)
            task_summary_md = gr.Markdown(
                label="Task Summary",
                value="# Task Summary will appear here after Save"
            )

            with gr.Accordion("Audit Data (Read-Only)", open=False):
                # _id (str)
                task_id_display_tb = gr.Textbox(label="Task ID", interactive=False)
                
                # _created_at (datetime)
                created_at_display_tb = gr.Textbox(label="Created At (UTC)", interactive=False)
                
                # _updated_at (datetime)
                updated_at_display_tb = gr.Textbox(label="Last Updated At (UTC)", interactive=False)


    # --- Event Handling ---
    
    # 1. Initial Load: Load the initial state
    demo.load(
        load_task_data,
        inputs=[task_state],
        outputs=[
            title_tb, body_tb, parent_id_tb, status_dd, priority_dd, 
            due_date_dt, estimated_time_num, task_id_display_tb, 
            created_at_display_tb, updated_at_display_tb, task_summary_md
        ],
        show_progress="hidden"
    )
    
    # Load initial task list
    demo.load(
        load_task_list,
        outputs=[task_list]
    )

    # 2. Save/Update Button: Call the handler function
    submit_btn.click(
        create_or_update_task,
        inputs=[
            title_tb, body_tb, parent_id_tb, status_dd, priority_dd, 
            due_date_dt, estimated_time_num, task_state, 
            task_id_display_tb, created_at_display_tb # Pass audit fields to persist on error
        ],
        outputs=[
            task_state, task_summary_md, task_id_display_tb, 
            created_at_display_tb, updated_at_display_tb
        ]
    ).success(  # Refresh task list after successful save/update
        load_task_list,
        outputs=[task_list]
    )
    
    # 3. Clear Button: Reset the form and clear the state
    clear_btn.click(
        clear_form,
        outputs=[
            title_tb, body_tb, parent_id_tb, status_dd, priority_dd, 
            due_date_dt, estimated_time_num, task_state, 
            task_id_display_tb, created_at_display_tb, updated_at_display_tb, task_summary_md
        ]
    )


    # 4. Task List Event Handlers
    refresh_btn.click(
        load_task_list,
        outputs=[task_list]
    )
    
    # Load task when clicked in the list
    def handle_task_selection(evt: gr.SelectData, task_data: pd.DataFrame):
        """Handle task selection from the table."""
        
        # FIX 1: Use 'task_data.empty' to check if the DataFrame is empty
        if evt is None or task_data.empty:
            return None
            
        try:
            # evt.index is a tuple: (row_index, col_index)
            row_index = evt.index[0] 
            
            # FIX 2: Use .iloc[row, col] to access data in the DataFrame
            # We want the 0th column ("Task ID") of the selected row
            task_id = task_data.iloc[row_index, 0] 
            
            if task_id and task_id != "N/A (New Task)":
                return load_task_by_id(task_id)
        except Exception as e:
            gr.Warning(f"Error selecting task: {e}")
        return None

    task_list.select(
        handle_task_selection,
        inputs=[task_list],
        outputs=[task_state],
        show_progress="hidden"
    ).then(  # Chain with load_task_data to update the form
        load_task_data,
        inputs=[task_state],
        outputs=[
            title_tb, body_tb, parent_id_tb, status_dd, priority_dd,
            due_date_dt, estimated_time_num, task_id_display_tb,
            created_at_display_tb, updated_at_display_tb, task_summary_md
        ]
    ).then(  # Enable/disable generate subtasks button based on task selection
        lambda x: gr.update(interactive=x is not None),
        inputs=[task_state],
        outputs=[generate_subtasks_btn]
    )
    
    # 5. Generate Subtasks Handler
    generate_subtasks_btn.click(
        generate_subtasks,
        inputs=[task_id_display_tb],
        outputs=[task_summary_md]
    ).success(  # Refresh task list after generating subtasks
        load_task_list,
        outputs=[task_list]
    )

if __name__ == "__main__":
    try:
        demo.launch()
    finally:
        # Clean up database connection when the app closes
        db.close()