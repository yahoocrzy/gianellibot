import aiohttp
import os
import secrets
import urllib.parse
from typing import Optional, Dict, Any
from loguru import logger

class ClickUpOAuth:
    """ClickUp OAuth2 authentication service"""
    
    def __init__(self):
        self.client_id = os.getenv("CLICKUP_CLIENT_ID")
        self.client_secret = os.getenv("CLICKUP_CLIENT_SECRET")
        self.redirect_uri = os.getenv("CLICKUP_REDIRECT_URI", "https://your-bot-domain.onrender.com/auth/clickup/callback")
        
        self.auth_url = "https://app.clickup.com/api"
        self.token_url = "https://api.clickup.com/api/v2/oauth/token"
        self.api_base = "https://api.clickup.com/api/v2"
        
        if not self.client_id or not self.client_secret:
            logger.warning("ClickUp OAuth credentials not configured. Set CLICKUP_CLIENT_ID and CLICKUP_CLIENT_SECRET")
    
    def generate_auth_url(self, state: Optional[str] = None) -> str:
        """Generate OAuth2 authorization URL"""
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state
        }
        
        auth_url = f"{self.auth_url}?" + urllib.parse.urlencode(params)
        logger.info(f"Generated auth URL with state: {state}")
        return auth_url, state
    
    async def exchange_code_for_token(self, code: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access token"""
        try:
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.token_url, data=data) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        logger.info("Successfully exchanged code for token")
                        return token_data
                    else:
                        error_text = await response.text()
                        logger.error(f"Token exchange failed: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error exchanging code for token: {e}")
            return None
    
    async def get_authorized_workspaces(self, access_token: str) -> Optional[list]:
        """Get workspaces the user has authorized"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                # Try the standard teams endpoint first
                async with session.get(f"{self.api_base}/team", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        workspaces = data.get("teams", [])
                        logger.info(f"Retrieved {len(workspaces)} authorized workspaces")
                        return workspaces
                    elif response.status == 401:
                        # Token might be invalid, try to get user info first to validate token
                        logger.warning("Token rejected for teams endpoint, checking token validity")
                        async with session.get(f"{self.api_base}/user", headers=headers) as user_response:
                            if user_response.status == 200:
                                user_data = await user_response.json()
                                logger.info(f"Token is valid for user: {user_data.get('user', {}).get('username', 'unknown')}")
                                # Try teams endpoint again
                                async with session.get(f"{self.api_base}/team", headers=headers) as retry_response:
                                    if retry_response.status == 200:
                                        retry_data = await retry_response.json()
                                        workspaces = retry_data.get("teams", [])
                                        logger.info(f"Retrieved {len(workspaces)} authorized workspaces on retry")
                                        return workspaces
                                    else:
                                        retry_error = await retry_response.text()
                                        logger.error(f"Teams endpoint failed on retry: {retry_response.status} - {retry_error}")
                                        return None
                            else:
                                user_error = await user_response.text()
                                logger.error(f"Token validation failed: {user_response.status} - {user_error}")
                                return None
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to get workspaces: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error getting authorized workspaces: {e}")
            return None
    
    async def test_token(self, access_token: str) -> bool:
        """Test if access token is valid"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_base}/user", headers=headers) as response:
                    if response.status == 200:
                        logger.info("Access token is valid")
                        return True
                    else:
                        logger.warning(f"Access token test failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error testing token: {e}")
            return False
    
    def is_configured(self) -> bool:
        """Check if OAuth2 is properly configured"""
        return bool(self.client_id and self.client_secret)

# Global instance
clickup_oauth = ClickUpOAuth()