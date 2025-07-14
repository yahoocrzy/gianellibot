import aiohttp
import json
from typing import Dict, Any, Optional, List
from loguru import logger

class ClaudeAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1"
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
    
    async def create_message(self, content: str, max_tokens: int = 4096, model: str = "claude-3-sonnet-20240229") -> Optional[str]:
        """Create a message using Claude's Messages API"""
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": content
                    }
                ]
            }
            
            try:
                async with session.post(
                    f"{self.base_url}/messages",
                    json=payload,
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("content", [{}])[0].get("text", "")
                    else:
                        error_text = await response.text()
                        logger.error(f"Claude API error: {response.status} - {error_text}")
                        return None
            except Exception as e:
                logger.error(f"Claude API request failed: {e}")
                return None
    
    async def test_connection(self) -> bool:
        """Test if the API key is valid"""
        try:
            response = await self.create_message("Hello, please respond with 'API key validated successfully'", max_tokens=50)
            return response is not None and "validated" in response.lower()
        except Exception as e:
            logger.error(f"Claude API test failed: {e}")
            return False
    
    async def parse_task_command(self, command: str) -> Dict[str, Any]:
        """Use Claude to parse natural language task commands"""
        prompt = f"""Parse this task command and return a JSON object with the task details.
        Command: "{command}"
        
        Extract:
        - name: task name (required)
        - description: task description (if any, can be empty string)
        - priority: one of "urgent", "high", "normal", "low" (default: "normal")
        - due_date: ISO date string or null
        - assignees: list of mentioned users (extract @usernames)
        - tags: list of hashtags or relevant tags
        
        Respond only with valid JSON, no additional text."""
        
        response = await self.create_message(prompt, max_tokens=1000)
        if not response:
            return self._fallback_parse(command)
        
        try:
            # Clean the response to extract just the JSON
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Claude response as JSON: {e}")
            return self._fallback_parse(command)
    
    def _fallback_parse(self, command: str) -> Dict[str, Any]:
        """Fallback parser when Claude fails"""
        return {
            "name": command[:100],  # Limit length
            "description": "",
            "priority": "normal",
            "due_date": None,
            "assignees": [],
            "tags": []
        }
    
    async def analyze_tasks(self, tasks: List[Dict[str, Any]]) -> str:
        """Analyze tasks and provide insights"""
        if not tasks:
            return "No tasks to analyze."
        
        tasks_summary = "\n".join([
            f"- {task.get('name', 'Unnamed')} (Priority: {task.get('priority', 'normal')}, Status: {task.get('status', 'unknown')})"
            for task in tasks[:10]  # Limit to 10 tasks
        ])
        
        prompt = f"""Analyze these tasks and provide insights:

{tasks_summary}

Provide a brief analysis covering:
1. Overall workload assessment
2. Priority distribution
3. Suggestions for task organization
4. Any patterns or recommendations

Keep the response concise and actionable."""
        
        response = await self.create_message(prompt, max_tokens=1000)
        return response or "Unable to analyze tasks at this time."
    
    async def suggest_task_improvements(self, task_name: str, task_description: str = "") -> str:
        """Suggest improvements for a task"""
        prompt = f"""Suggest improvements for this task:

Name: {task_name}
Description: {task_description}

Provide brief suggestions for:
1. Better task naming/clarity
2. Breaking into subtasks if needed
3. Priority assessment
4. Potential dependencies

Keep suggestions practical and concise."""
        
        response = await self.create_message(prompt, max_tokens=800)
        return response or "Unable to provide suggestions at this time."