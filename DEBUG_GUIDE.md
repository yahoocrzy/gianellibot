# Debug Guide for ClickUp Discord Bot

## Quick Diagnosis Steps

### 1. Run Diagnostics Script
```bash
python diagnostics.py
```
This will check:
- Environment variables
- File structure
- Dependencies
- Database connection
- Cog health

### 2. Test Connections
```bash
python test_connections.py
```
This will verify:
- Discord token validity
- Database connectivity
- Encryption functionality
- ClickUp API (if configured)
- Claude API (if configured)
- Web server dependencies

### 3. Check Bot Logs
The bot now has enhanced logging:
- **Console**: Real-time colored output
- **logs/debug_YYYY-MM-DD.log**: Detailed debug logs
- **logs/errors_YYYY-MM-DD.log**: Error-specific logs

### 4. Use Debug Commands (Admin Only)

Once the bot is running, use these slash commands:

- `/debug` - Show overall bot health and statistics
- `/debug-config` - Check server configuration status
- `/debug-test-api` - Test API connections
- `/debug-errors` - View recent errors
- `/debug-cogs` - Check cog loading status

## Common Issues and Solutions

### Bot Not Starting

1. **Missing Environment Variables**
   ```bash
   # Required variables:
   DISCORD_TOKEN=your_bot_token
   ENCRYPTION_KEY=your_32_char_key
   CLAUDE_API_URL=https://api.anthropic.com/v1
   ```

2. **Database Issues**
   - The bot uses SQLite by default (bot_data.db)
   - For PostgreSQL, set DATABASE_URL
   - Tables are auto-created on first run

3. **Import Errors**
   ```bash
   pip install -r requirements.txt
   ```

### Commands Not Showing

1. **Sync Issue**
   - Bot automatically syncs on startup
   - Check logs for sync errors
   - May take up to an hour for Discord to update

2. **Permission Issues**
   - Bot needs application.commands scope
   - Admin commands need administrator permission

### ClickUp Integration Issues

1. **No Configuration**
   - Use `/clickup-setup` or `/workspace-add`
   - Check with `/debug-config`

2. **API Errors**
   - Verify token with `/debug-test-api`
   - Check rate limits in logs
   - Token might be expired

### Debug Environment Variables

Set these for more debugging info:
```bash
DEBUG=true          # Enable debug logging
LOG_LEVEL=DEBUG     # Set log level
```

## Log Analysis

### Understanding Log Entries

```
2024-01-14 10:30:45 | INFO | cogs.debug_dashboard:setup:201 - Loaded cog: debug_dashboard
```
- Timestamp
- Log level (DEBUG, INFO, WARNING, ERROR)
- Module:function:line
- Message

### Key Events to Monitor

1. **Startup Sequence**
   - `bot_startup` - Bot initialization
   - `database` - Database connection
   - `cog_load` - Cog loading status
   - `command_sync` - Command registration

2. **Runtime Events**
   - `command` - Command executions
   - `api_call` - External API calls
   - `error` - Error occurrences

## Debugging Workflow

1. **Initial Setup**
   ```bash
   # 1. Run diagnostics
   python diagnostics.py
   
   # 2. Fix any critical issues
   
   # 3. Test connections
   python test_connections.py
   
   # 4. Start bot with debug mode
   DEBUG=true python main.py
   ```

2. **Runtime Debugging**
   - Monitor console output
   - Use `/debug` commands
   - Check log files for errors
   - Review debug dashboard

3. **Issue Resolution**
   - Identify error in logs
   - Use `/debug-errors` for details
   - Check relevant configuration
   - Test specific component

## Performance Monitoring

The debug dashboard tracks:
- Command execution counts
- API call success rates
- Error frequency
- System resource usage

Use `/debug` regularly to monitor bot health.

## Getting Help

1. Check this guide first
2. Review error logs
3. Run diagnostic scripts
4. Use debug commands
5. Check recent commits for changes

Remember: The debug tools are only accessible to server administrators for security reasons.