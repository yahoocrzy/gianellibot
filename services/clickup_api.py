import aiohttp
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
import asyncio

class ClickUpAPI:
    BASE_URL = "https://api.clickup.com/api/v2"
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            "Authorization": api_token,
            "Content-Type": "application/json"
        }
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self._session = aiohttp.ClientSession(headers=self.headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request with retry logic"""
        url = f"{self.BASE_URL}/{endpoint}"
        
        # Ensure session exists and is not closed
        if not self._session or self._session.closed:
            logger.warning("Session is closed or None, creating new session")
            if self._session:
                await self._session.close()
            self._session = aiohttp.ClientSession(headers=self.headers)
        
        try:
            async with self._session.request(method, url, **kwargs) as response:
                data = await response.json()
                
                if response.status == 429:  # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited, waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    raise Exception("Rate limited")
                
                if response.status >= 400:
                    logger.error(f"API error: {response.status} - {data}")
                    raise Exception(f"ClickUp API error: {data}")
                
                return data
        except aiohttp.ClientError as e:
            logger.error(f"Network error in ClickUp API request: {e}")
            raise RuntimeError(f"Network error: {e}")
    
    # Workspace & Teams
    async def get_workspaces(self) -> List[Dict[str, Any]]:
        """Get all workspaces"""
        data = await self._request("GET", "team")
        return data.get("teams", [])
    
    # Spaces
    async def get_spaces(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get all spaces in a workspace"""
        data = await self._request("GET", f"team/{workspace_id}/space")
        return data.get("spaces", [])
    
    async def create_space(self, workspace_id: str, name: str, **kwargs) -> Dict[str, Any]:
        """Create a new space"""
        return await self._request("POST", f"team/{workspace_id}/space", json={"name": name, **kwargs})
    
    # Folders
    async def get_folders(self, space_id: str) -> List[Dict[str, Any]]:
        """Get all folders in a space"""
        data = await self._request("GET", f"space/{space_id}/folder")
        return data.get("folders", [])
    
    async def create_folder(self, space_id: str, name: str) -> Dict[str, Any]:
        """Create a new folder"""
        return await self._request("POST", f"space/{space_id}/folder", json={"name": name})
    
    # Lists
    async def get_lists(self, folder_id: str) -> List[Dict[str, Any]]:
        """Get all lists in a folder"""
        data = await self._request("GET", f"folder/{folder_id}/list")
        return data.get("lists", [])
    
    async def get_folderless_lists(self, space_id: str) -> List[Dict[str, Any]]:
        """Get lists not in any folder"""
        data = await self._request("GET", f"space/{space_id}/list")
        return data.get("lists", [])
    
    async def create_list(self, folder_id: str, name: str, **kwargs) -> Dict[str, Any]:
        """Create a new list"""
        return await self._request("POST", f"folder/{folder_id}/list", json={"name": name, **kwargs})
    
    # Tasks
    async def get_tasks(self, list_id: str, **params) -> List[Dict[str, Any]]:
        """Get tasks from a list"""
        data = await self._request("GET", f"list/{list_id}/task", params=params)
        return data.get("tasks", [])
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get a specific task"""
        return await self._request("GET", f"task/{task_id}")
    
    async def create_task(self, list_id: str, name: str, **kwargs) -> Dict[str, Any]:
        """Create a new task"""
        return await self._request("POST", f"list/{list_id}/task", json={"name": name, **kwargs})
    
    async def update_task(self, task_id: str, **kwargs) -> Dict[str, Any]:
        """Update a task"""
        return await self._request("PUT", f"task/{task_id}", json=kwargs)
    
    async def delete_task(self, task_id: str) -> None:
        """Delete a task"""
        await self._request("DELETE", f"task/{task_id}")
    
    # Comments
    async def get_comments(self, task_id: str) -> List[Dict[str, Any]]:
        """Get comments on a task"""
        data = await self._request("GET", f"task/{task_id}/comment")
        return data.get("comments", [])
    
    async def create_comment(self, task_id: str, comment_text: str, **kwargs) -> Dict[str, Any]:
        """Create a comment on a task"""
        return await self._request("POST", f"task/{task_id}/comment", json={"comment_text": comment_text, **kwargs})
    
    # Attachments
    async def upload_attachment(self, task_id: str, file_data: bytes, filename: str) -> Dict[str, Any]:
        """Upload an attachment to a task"""
        data = aiohttp.FormData()
        data.add_field('attachment', file_data, filename=filename)
        return await self._request("POST", f"task/{task_id}/attachment", data=data)
    
    # Custom Fields
    async def get_custom_fields(self, list_id: str) -> List[Dict[str, Any]]:
        """Get custom fields for a list"""
        data = await self._request("GET", f"list/{list_id}/field")
        return data.get("fields", [])
    
    async def set_custom_field_value(self, task_id: str, field_id: str, value: Any) -> Dict[str, Any]:
        """Set custom field value on a task"""
        return await self._request("POST", f"task/{task_id}/field/{field_id}", json={"value": value})
    
    # Members
    async def get_members(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get all members in a workspace"""
        data = await self._request("GET", f"team/{workspace_id}/member")
        return data.get("members", [])
    
    async def assign_task(self, task_id: str, assignee_ids: List[int]) -> Dict[str, Any]:
        """Assign users to a task"""
        return await self._request("PUT", f"task/{task_id}", json={"assignees": assignee_ids})
    
    # Time Tracking
    async def get_time_entries(self, workspace_id: str, **params) -> List[Dict[str, Any]]:
        """Get time entries"""
        data = await self._request("GET", f"team/{workspace_id}/time_entries", params=params)
        return data.get("data", [])
    
    async def start_timer(self, task_id: str, description: str = "") -> Dict[str, Any]:
        """Start a time tracking timer"""
        return await self._request("POST", f"task/{task_id}/time", json={"description": description})
    
    async def stop_timer(self, workspace_id: str) -> Dict[str, Any]:
        """Stop the current timer"""
        return await self._request("POST", f"team/{workspace_id}/time_entries/stop")
    
    # Goals
    async def get_goals(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get all goals"""
        data = await self._request("GET", f"team/{workspace_id}/goal")
        return data.get("goals", [])
    
    async def create_goal(self, workspace_id: str, name: str, **kwargs) -> Dict[str, Any]:
        """Create a new goal"""
        return await self._request("POST", f"team/{workspace_id}/goal", json={"name": name, **kwargs})
    
    # Webhooks
    async def get_webhooks(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get all webhooks"""
        data = await self._request("GET", f"team/{workspace_id}/webhook")
        return data.get("webhooks", [])
    
    async def create_webhook(self, workspace_id: str, endpoint: str, events: List[str]) -> Dict[str, Any]:
        """Create a webhook"""
        return await self._request("POST", f"team/{workspace_id}/webhook", json={
            "endpoint": endpoint,
            "events": events
        })
    
    # Views
    async def get_views(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get all views"""
        data = await self._request("GET", f"team/{workspace_id}/view")
        return data.get("views", [])
    
    async def get_view_tasks(self, view_id: str, **params) -> List[Dict[str, Any]]:
        """Get tasks from a view"""
        data = await self._request("GET", f"view/{view_id}/task", params=params)
        return data.get("tasks", [])