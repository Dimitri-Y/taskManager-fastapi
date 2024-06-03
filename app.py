import os
from typing import Optional, List
from enum import Enum
from fastapi import FastAPI, Body, HTTPException, status
from fastapi.responses import Response
from pydantic import ConfigDict, BaseModel, Field, EmailStr
from pydantic.functional_validators import BeforeValidator

from typing_extensions import Annotated

from bson import ObjectId
import motor.motor_asyncio
from pymongo import ReturnDocument

import uuid

app = FastAPI(
    title="Tasks API",
    summary="A sample application showing how to use FastAPI to add a ReST API to a MongoDB collection.",
)
client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URL"])
db = client.college
task_collection = db.get_collection("tasks")

# Represents an ObjectId field in the database.
# It will be represented as a `str` on the model so that it can be serialized to JSON.
PyObjectId = Annotated[str, BeforeValidator(str)]

class StatusEnum(str, Enum):
    done = "done"
    undone = "undone"
    progress = "progress"

class TaskModel(BaseModel):
    ""
    id: Optional[PyObjectId] =Field(alias="_id",default=None)
    title: str = Field(min_length = 3, max_length = 100)
    description: str = Field(default = "", min_length = 3, max_length = 500)
    priority: int = Field(default = 10, min = 1, max = 10)
    status: StatusEnum = Field(...)
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "title": "To programming ",
                "description": "Programming in 15: 00",
                "priority": 10,
                "status": "progress",
            }
        },
    )
class UpdateTaskModel(BaseModel):
    ""
    id: Optional[PyObjectId] =Field(alias="_id",default=None)
    title: Optional[str] = Field(None, min_length = 3, max_length = 100)
    description: Optional[str] = Field(None, min_length = 3, max_length = 500)
    priority: Optional[int] = Field(None, min = 1, max = 10)
    status: Optional[StatusEnum] = Field(None)
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "title": "To programming ",
                "description": "Programming in 15: 00",
                "priority": 10,
                "status": "progress",
            }
        },
    )    
class TaskCollection(BaseModel):
    """
    A container holding a list of `TaskModel` instances.
    """

    tasks: List[TaskModel]

@app.post(
    "/tasks/",
    response_description="Add new task",
    response_model=TaskModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_task(task: TaskModel = Body(...)):
    """
    Insert a new task record.

    A unique `id` will be created and provided in the response.
    """
    new_task = await task_collection.insert_one(
        task.model_dump(by_alias=True, exclude=["id"])
    )
    created_task = await task_collection.find_one(
        {"_id": new_task.inserted_id}
    )
    return created_task

@app.get(
    "/tasks/",
    response_description="List all tasks",
    response_model=TaskCollection,
    response_model_by_alias=False,
)
async def list_tasks():
    """
    The response is unpaginated and limited to 1000 results.
    """
    return TaskCollection(tasks=await task_collection.find().to_list(1000))

@app.get(
    "/tasks/{id}",
    response_description="Get a single task",
    response_model=TaskModel,
    response_model_by_alias=False,
)
async def show_task(id: str):
    """
    Get the record for a specific task, looked up by `id`.
    """
    if (
        task := await task_collection.find_one({"_id": ObjectId(id)})
    ) is not None:
        return task

    raise HTTPException(status_code=404, detail=f"Task {id} not found")

@app.put(
    "/tasks/{id}",
    response_description="Update a task",
    response_model=UpdateTaskModel,
    response_model_by_alias=False,
)
async def update_task(id: str, task: UpdateTaskModel = Body(...)):
    """
    Update individual fields of an existing task record.

    Only the provided fields will be updated.
    Any missing or `null` fields will be ignored.
    """
    task = {
        k: v for k, v in task.model_dump(by_alias=True).items() if v is not None
    }

    if len(task) >= 1:
        update_result = await task_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": task},
            return_document=ReturnDocument.AFTER,
        )
        if update_result is not None:
            return update_result
        else:
            raise HTTPException(status_code=404, detail=f"Task {id} not found")

    # The update is empty, but we should still return the matching document:
    if (existing_task := await task_collection.find_one({"_id": id})) is not None:
        return existing_task

    raise HTTPException(status_code=404, detail=f"Task {id} not found")

@app.delete("/tasks/{id}", response_description="Delete a task")
async def delete_task(id: str):
    """
    Remove a single task record from the database.
    """
    delete_result = await task_collection.delete_one({"_id": ObjectId(id)})

    if delete_result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail=f"Task {id} not found")
