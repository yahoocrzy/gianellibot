import aiohttp
from typing import Dict, Any, Optional
from loguru import logger

class ClaudeAPI:
    def __init__(self, api_url: str, api_key: Optional[str] = None):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def complete(self, prompt: str, **kwargs) -> str:
        """Send completion request to Claude"""
        async with aiohttp.ClientSession() as session:
            payload = {
                "prompt": prompt,
                **kwargs
            }
            
            try:
                async with session.post(
                    f"{self.api_url}/complete",
                    json=payload,
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("completion", "")
                    else:
                        error = await response.text()
                        logger.error(f"Claude API error: {response.status} - {error}")
                        return ""
            except Exception as e:
                logger.error(f"Claude API request failed: {e}")
                return ""
    
    async def parse_task_command(self, command: str) -> Dict[str, Any]:
        """Use Claude to parse natural language task commands"""
        prompt = f"""Parse this task command and return a JSON object with the task details.
        Command: "{command}"
        
        Extract:
        - name: task name
        - description: task description (if any)
        - priority: 1-4 (1=urgent, 2=high, 3=normal, 4=low)
        - due_date: ISO date string or null
        - assignees: list of mentioned users
        - tags: list of tags
        
        Respond only with valid JSON."""
        
        response = await self.complete(prompt)
        try:
            import json
            return json.loads(response)
        except:
            return {
                "name": command,
                "description": "",
                "priority": 3,
                "due_date": None,
                "assignees": [],
                "tags": []
            }