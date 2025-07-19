from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn
import asyncio
import os
from datetime import datetime
from loguru import logger
from services.google_calendar_api import GoogleCalendarAPI
from repositories.google_oauth_repository import GoogleOAuthRepository
import os

def create_web_server(bot):
    """Create FastAPI web server for health checks and monitoring"""
    app = FastAPI(title="Calendar Discord Bot")
    
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "name": "Calendar Discord Bot",
            "status": "online",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint for Render and keep-alive"""
        try:
            # Check bot connection
            if not bot.is_ready():
                return JSONResponse(
                    status_code=503,
                    content={"status": "unhealthy", "reason": "Bot not ready"}
                )
            
            # Check database connection (simplified)
            # Database check removed for now to avoid connection issues
            
            uptime = "unknown"
            if hasattr(bot, 'start_time'):
                uptime_delta = datetime.utcnow() - bot.start_time
                uptime = str(uptime_delta)
            
            return {
                "status": "healthy",
                "bot_latency": f"{bot.latency * 1000:.2f}ms",
                "guilds": len(bot.guilds),
                "users": len(bot.users),
                "uptime": uptime,
                "timestamp": datetime.utcnow().isoformat(),
                "keep_alive": True
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "error": str(e)}
            )
    
    @app.get("/ping")
    async def ping():
        """Simple ping endpoint for keep-alive"""
        return {"pong": True, "timestamp": datetime.utcnow().isoformat()}
    
    @app.get("/uptime")
    async def uptime():
        """Uptime information"""
        if not hasattr(bot, 'start_time'):
            return {"uptime": "unknown"}
        
        uptime_delta = datetime.utcnow() - bot.start_time
        return {
            "uptime_seconds": int(uptime_delta.total_seconds()),
            "uptime_human": str(uptime_delta),
            "started_at": bot.start_time.isoformat(),
            "current_time": datetime.utcnow().isoformat()
        }
    
    @app.get("/stats")
    async def stats():
        """Bot statistics endpoint"""
        if not bot.is_ready():
            return {"error": "Bot not ready"}
        
        return {
            "guilds": len(bot.guilds),
            "users": len(bot.users),
            "commands": len(bot.commands),
            "cogs": len(bot.cogs),
            "latency": f"{bot.latency * 1000:.2f}ms",
            "uptime": str(datetime.utcnow() - bot.start_time) if hasattr(bot, 'start_time') else "Unknown"
        }
    
    @app.get("/auth/google/callback")
    async def google_oauth_callback(request: Request):
        """Handle Google OAuth2 callback"""
        try:
            # Get query parameters
            query_params = dict(request.query_params)
            code = query_params.get('code')
            state = query_params.get('state')
            error = query_params.get('error')
            
            if error:
                logger.error(f"OAuth2 error: {error}")
                return HTMLResponse(f"""
                <html>
                    <head><title>Google Calendar Setup Failed</title></head>
                    <body style="font-family: Arial; text-align: center; padding: 50px;">
                        <h1>❌ Google Calendar Setup Failed</h1>
                        <p>Error: {error}</p>
                        <p>Please try again in Discord with <code>/calendar-setup</code></p>
                    </body>
                </html>
                """, status_code=400)
            
            if not code or not state:
                raise HTTPException(status_code=400, detail="Missing code or state parameter")
            
            # Validate state
            validation_result = await GoogleOAuthRepository.validate_oauth_state(state)
            if not validation_result:
                raise HTTPException(status_code=400, detail="Invalid or expired state")
            
            guild_id, user_id = validation_result
            
            # Exchange code for token using Google OAuth flow
            redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:10000/auth/google/callback")
            flow = GoogleCalendarAPI.create_auth_flow(redirect_uri)
            flow.fetch_token(code=code)
            
            # Get credentials
            credentials = flow.credentials
            if not credentials:
                raise HTTPException(status_code=400, detail="Failed to get credentials")
            
            # Get user info to extract email
            from google.oauth2 import service_account
            import google.auth.transport.requests
            from google.auth.transport.requests import Request as GoogleRequest
            import aiohttp
            
            # Get user email from Google
            async with aiohttp.ClientSession() as session:
                headers = {'Authorization': f'Bearer {credentials.token}'}
                async with session.get('https://www.googleapis.com/oauth2/v1/userinfo', headers=headers) as resp:
                    if resp.status == 200:
                        user_info = await resp.json()
                        email = user_info.get('email', 'Unknown')
                    else:
                        email = 'Unknown'
            
            # Save credentials
            saved_cred = await GoogleOAuthRepository.save_credentials(
                guild_id, user_id, email, credentials.to_json()
            )
            
            logger.info(f"OAuth2 setup completed for guild {guild_id}, user {email}")
            
            return HTMLResponse(f"""
            <html>
                <head><title>Google Calendar Setup Complete</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px; background: #f0f8ff;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 30px; background: white; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        <h1 style="color: #28a745;">✅ Google Calendar Setup Complete!</h1>
                        <p style="font-size: 18px; color: #333;">Successfully connected Google Calendar</p>
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                            Connected account: {email}
                        </div>
                        <p style="color: #666;">You can now close this tab and return to Discord.</p>
                        <div style="margin-top: 30px; padding: 20px; background: #e8f5e8; border-radius: 5px;">
                            <h3 style="color: #155724; margin: 0 0 10px 0;">🎉 Ready to use!</h3>
                            <p style="margin: 0; color: #155724;">Try these commands in Discord:</p>
                            <ul style="text-align: left; display: inline-block; color: #155724;">
                                <li><code>/calendar</code> - View your calendar</li>
                                <li><code>/calendar-events</code> - List upcoming events</li>
                                <li><code>/calendar-today</code> - See today's events</li>
                            </ul>
                        </div>
                    </div>
                </body>
            </html>
            """)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in OAuth callback: {e}")
            return HTMLResponse(f"""
            <html>
                <head><title>Setup Error</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1>❌ Setup Error</h1>
                    <p>An error occurred during setup: {str(e)}</p>
                    <p>Please try again in Discord with <code>/calendar-setup</code></p>
                </body>
            </html>
            """, status_code=500)
    
    @app.post("/webhook/google")
    async def google_webhook(data: dict):
        """Handle Google Calendar webhooks"""
        # Process webhook data
        logger.info(f"Received Google webhook: {data}")
        # You can emit events to the bot here
        return {"status": "received"}
    
    class Server:
        def __init__(self, app):
            self.app = app
            self.server = None
            
        async def serve(self):
            """Start the web server"""
            config = uvicorn.Config(
                self.app,
                host="0.0.0.0",
                port=int(os.getenv("PORT", 10000)),
                log_level="info"
            )
            server = uvicorn.Server(config)
            self.server = server
            await server.serve()
        
        async def shutdown(self):
            """Shutdown the web server"""
            if self.server:
                await self.server.shutdown()
    
    return Server(app)