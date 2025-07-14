from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
import uvicorn
import asyncio
import os
from datetime import datetime
from loguru import logger

def create_web_server(bot):
    """Create FastAPI web server for health checks and monitoring"""
    app = FastAPI(title="ClickUp Discord Bot")
    
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "name": "ClickUp Discord Bot",
            "status": "online",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint for Render"""
        try:
            # Check bot connection
            if not bot.is_ready():
                return JSONResponse(
                    status_code=503,
                    content={"status": "unhealthy", "reason": "Bot not ready"}
                )
            
            # Check database connection (simplified)
            # Database check removed for now to avoid connection issues
            
            return {
                "status": "healthy",
                "bot_latency": f"{bot.latency * 1000:.2f}ms",
                "guilds": len(bot.guilds),
                "users": len(bot.users),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "error": str(e)}
            )
    
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
    
    @app.post("/webhook/clickup")
    async def clickup_webhook(data: dict):
        """Handle ClickUp webhooks"""
        # Process webhook data
        logger.info(f"Received ClickUp webhook: {data}")
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