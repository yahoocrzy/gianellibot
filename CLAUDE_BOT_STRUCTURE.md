# ClickBot Structure Documentation

This document provides a comprehensive overview of the ClickBot Discord bot architecture for Claude AI to understand the codebase structure and functionality.

## Project Overview

ClickBot is a multi-purpose Discord bot featuring ClickUp project management integration, reaction roles, mood systems, moderation tools, and various utility features. The bot includes infrastructure for Claude AI integration but this feature is not yet fully implemented. Built using discord.py 2.4.0 with async SQLAlchemy for database operations.

## Core Architecture

### Entry Points
- **`main.py`** - Main bot application with ClickUpBot class and event handlers
- **`web_server.py`** - FastAPI web server for OAuth callbacks and health checks
- **`config.py`** - Configuration management and environment variables

### Database Layer (`/database/`)
- **`models.py`** - SQLAlchemy ORM models with async support
  - `ServerConfig` - Guild-specific configuration and encrypted tokens
  - `ReactionRole` - Reaction-based role assignment system
  - `UserPreference` - User-specific settings and preferences
  - `ClickUpOAuthState` - OAuth2 state management with expiration
  - `ClickUpWorkspace` - ClickUp workspace and token management
  - `ClaudeConfig` - Claude AI configuration per guild
  - `Cache` - Generic key-value cache with TTL

### Data Access Layer (`/repositories/`)
- **`server_config.py`** - Server configuration data operations
- **`reaction_roles.py`** - Reaction roles database operations
- **`mood_system.py`** - Mood system data management
- **`claude_config.py`** - Claude AI configuration storage
- **`clickup_oauth_workspaces.py`** - ClickUp workspace management

### Business Logic Layer (`/services/`)
- **`claude_api.py`** - Claude AI API integration and conversation management
- **`clickup_api.py`** - ClickUp API wrapper with OAuth2 support
- **`clickup_oauth.py`** - OAuth2 flow implementation for ClickUp
- **`security.py`** - Encryption/decryption utilities for sensitive data

### Command Layer (`/cogs/`)

#### AI Integration Cogs
- **`ai_assistant.py`** - Core Claude AI assistant functionality
- **`ai_commands_enhanced.py`** - Enhanced AI command processing
- **`ai_conversation.py`** - Conversation management and context
- **`ai_complete_dropdown.py`** - AI completion dropdown interactions
- **`claude_setup.py`** - Claude AI configuration and setup

#### ClickUp Integration Cogs
- **`clickup_tasks_enhanced.py`** - Enhanced ClickUp task management
- **`workspace_management.py`** - ClickUp workspace configuration

#### Feature Cogs
- **`reaction_roles.py`** - Reaction-based role assignment system
- **`mood_system.py`** - User mood tracking with emoji reactions
- **`moderation.py`** - Message moderation and cleanup commands
- **`calendar_commands.py`** - Calendar and scheduling functionality
- **`help_command.py`** - Custom help system
- **`help_pin.py`** - Automated help message pinning

#### Administrative Cogs
- **`config_health.py`** - Configuration health monitoring
- **`debug_dashboard.py`** - Debug and diagnostics interface

### Utility Layer (`/utils/`)
- **`helpers.py`** - General utility functions and decorators
- **`embed_factory.py`** - Discord embed creation utilities
- **`selection_views.py`** - Discord UI views for user selections
- **`enhanced_selections.py`** - Enhanced selection components
- **`debug_logger.py`** - Comprehensive debug logging system

## Key Features

### 1. Reaction Roles System
- Custom embed colors and descriptions
- Exclusive vs non-exclusive role assignment
- Multiple emoji-to-role mappings per message
- Automatic role management on reaction add/remove

### 2. Mood System
- Emoji-based mood tracking
- Automatic nickname updates with mood emojis
- Role-based mood categorization

### 3. ClickUp Integration
- OAuth2 authentication flow
- Task creation and management
- Workspace configuration
- Hybrid token system (OAuth + personal tokens)

### 4. Claude AI Integration (Infrastructure Only - Not Yet Implemented)
- Database models and configuration system prepared
- Per-guild API key storage infrastructure
- Command structure defined but not functional
- Secure API key encryption system ready

### 5. Moderation Tools
- Bulk message deletion with filters
- User-specific and bot-specific purging
- Permission-based access control

## Database Schema

### Key Relationships
- `ServerConfig` stores guild-level configuration
- `ReactionRole` links messages to role assignments
- `ClickUpWorkspace` manages OAuth tokens per workspace
- `ClaudeConfig` stores encrypted API keys per guild
- `UserPreference` maintains user-specific settings

### Security Features
- Encrypted storage for sensitive tokens
- OAuth2 state validation with expiration
- Permission-based command restrictions
- Graceful error handling for missing permissions

## Command Architecture

### Permission Levels
- **Public Commands** - Available to all users
- **Admin Commands** - Require Administrator permission
- **Owner Commands** - Bot owner only

### Command Categories
- **Setup Commands** - Initial configuration (`/clickup-setup`, `/claude-setup`)
- **Management Commands** - Ongoing administration (`/workspace-add`, `/reaction-roles-setup`)
- **User Commands** - End-user functionality (AI chat, task creation)
- **Debug Commands** - Diagnostics and troubleshooting

## Configuration Management

### Environment Variables
- `DATABASE_URL` - Database connection string
- `DISCORD_TOKEN` - Bot authentication token
- `CLICKUP_CLIENT_ID` - ClickUp OAuth client ID
- `CLICKUP_CLIENT_SECRET` - ClickUp OAuth client secret
- `ENCRYPTION_KEY` - Key for sensitive data encryption

### Runtime Configuration
- Dynamic prefix per guild
- Per-guild feature toggles
- User preference storage
- Cached configuration for performance

## Deployment

### Supported Platforms
- **Development** - SQLite with aiosqlite
- **Production** - PostgreSQL with asyncpg on Render
- **Docker** - Containerized deployment support

### Dependencies
- discord.py 2.4.0 - Discord API wrapper
- SQLAlchemy 2.0.23 - ORM with async support
- FastAPI 0.104.1 - Web server for OAuth callbacks
- Cryptography 41.0.4 - Encryption utilities
- aiohttp 3.8.4 - HTTP client for API calls

## Error Handling

### Graceful Degradation
- Missing permissions handled with user feedback
- API failures logged with retry mechanisms
- Database errors with fallback behaviors
- OAuth token refresh automation

### Logging
- Structured logging with loguru
- Debug event tracking
- Error context preservation
- Performance monitoring

## Security Considerations

### Data Protection
- Encrypted token storage
- Secure OAuth2 implementation
- Input validation and sanitization
- Rate limiting on API calls

### Access Control
- Permission-based command restrictions
- Role hierarchy respect
- Admin-only configuration commands
- Audit logging for sensitive operations

This structure follows clean architecture principles with clear separation of concerns, making the codebase maintainable and extensible.