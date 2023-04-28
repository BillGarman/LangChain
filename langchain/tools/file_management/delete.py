import os
from typing import Type

from pydantic import BaseModel, Field

from langchain.tools.file_management.utils import (
    INVALID_PATH_TEMPLATE,
    BaseFileTool,
    FileValidationError,
)


class FileDeleteInput(BaseModel):
    """Input for DeleteFileTool."""

    file_path: str = Field(..., description="Path of the file to delete")


class DeleteFileTool(BaseFileTool):
    name: str = "file_delete"
    args_schema: Type[BaseModel] = FileDeleteInput
    description: str = "Delete a file"

    def _run(self, file_path: str) -> str:
        try:
            file_path_ = self.get_relative_path(file_path)
        except FileValidationError:
            return INVALID_PATH_TEMPLATE.format(arg_name="file_path", value=file_path)
        if not file_path_.exists():
            return f"Error: no such file or directory: {file_path}"
        try:
            os.remove(file_path_)
            return f"File deleted successfully: {file_path}."
        except Exception as e:
            return "Error: " + str(e)

    async def _arun(self, file_path: str) -> str:
        # TODO: Add aiofiles method
        raise NotImplementedError
