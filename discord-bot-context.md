# Discord ClickUp Bot - Project Context for Claude Code

## Project Overview

This is a Discord bot project that needs to be built and deployed on Render for 24/7 online operation. The bot integrates ClickUp project management and Claude AI to create a powerful workspace automation tool for Discord servers.

## Key Requirements

### Core Functionality
- **ClickUp Integration**: Complete API v2 integration allowing users to manage ALL ClickUp features without logging into ClickUp
- **Claude AI Integration**: Natural language processing using the API at https://claudeup.onrender.com
- **Persistent Online Operation**: Must run 24/7 on Render's platform
- **Interactive Setup**: Carl-bot style setup wizard for easy configuration
- **Reaction Roles**: Discord reaction role management system

### Technical Requirements
- **Language**: Python with discord.py library
- **Database**: PostgreSQL (provided by Render) for persistent storage
- **Deployment**: Render web service with health monitoring
- **Security**: Encrypted token storage, secure API handling
- **Architecture**: Simple, maintainable code structure for easy review

## User Stories

1. **As a Discord server admin**, I want to run a single `!setup` command that walks me through connecting my ClickUp workspace, so configuration is simple and interactive.

2. **As a team member**, I want to create tasks using natural language like "create high priority bug fix task due tomorrow", without needing to know ClickUp's interface.

3. **As a project manager**, I want to manage all ClickUp features (tasks, time tracking, comments, etc.) directly from Discord, eliminating the need to switch applications.

4. **As a Discord user**, I want to use reaction roles to self-assign team roles, making onboarding seamless.

## Implementation Priorities

1. **Core Bot Structure**: Set up the bot framework with Render deployment configuration
2. **Database Models**: PostgreSQL schema for storing encrypted tokens and configurations  
3. **Setup Wizard**: Interactive configuration system with modals and buttons
4. **ClickUp API Wrapper**: Complete implementation of all ClickUp v2 endpoints
5. **Claude Integration**: Natural language command processing
6. **Reaction Roles**: Role management system
7. **Error Handling**: Comprehensive error handling and logging

## Deployment Requirements

- Must deploy to Render as a web service
- Include health check endpoint to prevent service sleeping
- PostgreSQL database for data persistence
- Environment variable management for sensitive data
- Automatic restart on failure

## File References

- **Implementation Guide**: See `discord-bot-implementation.md` for complete code and detailed implementation instructions
- **All code should follow the structure and patterns defined in the implementation guide**

## Development Approach

When implementing this bot:
1. Start with the basic bot structure and Render configuration
2. Implement one feature at a time, testing each thoroughly
3. Keep code simple and well-commented for easy maintenance
4. Follow the modular architecture defined in the implementation guide
5. Ensure all ClickUp API endpoints are implemented as shown in the guide

## Success Criteria

- Bot runs continuously on Render without downtime
- All ClickUp features accessible through Discord commands
- Natural language processing works for common task operations
- Setup process takes less than 2 minutes for new servers
- Reaction roles work reliably
- All API tokens are securely encrypted

## Important Notes

- The Claude API endpoint (https://claudeup.onrender.com) is already deployed and ready to use
- Focus on simplicity - the code needs to be easily reviewable and maintainable
- Implement ALL ClickUp functionality, not just basic features
- The bot should effectively replace the need to use ClickUp's web interface