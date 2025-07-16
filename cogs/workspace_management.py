import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from services.clickup_api import ClickUpAPI
from repositories.clickup_workspaces import ClickUpWorkspaceRepository
from utils.embed_factory import EmbedFactory
from loguru import logger

class WorkspaceManagement(commands.Cog):
    """Manage ClickUp workspaces for the server"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="clickup-setup", description="Set up ClickUp integration for this server")
    @app_commands.default_permissions(administrator=True)
    async def clickup_setup(self, interaction: discord.Interaction):
        """Complete ClickUp setup - checks status and guides through configuration"""
        
        # Check if already configured
        workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if workspaces:
            # Already configured - offer options
            default_workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
            
            embed = EmbedFactory.create_info_embed(
                "🔧 ClickUp Setup Options",
                f"ClickUp is already configured with {len(workspaces)} workspace(s)."
            )
            
            embed.add_field(
                name="Current Setup",
                value=f"**Default Workspace**: {default_workspace.workspace_name if default_workspace else 'None'}\n"
                      f"**Total Workspaces**: {len(workspaces)}\n"
                      f"**Status**: ✅ Ready to use",
                inline=False
            )
            
            embed.add_field(
                name="What would you like to do?",
                value="Choose an option below:",
                inline=False
            )
            
            class SetupOptionsView(discord.ui.View):
                def __init__(self, parent_cog):
                    super().__init__(timeout=60)
                    self.parent_cog = parent_cog
                
                @discord.ui.button(label="Add Another Workspace", style=discord.ButtonStyle.primary, emoji="➕")
                async def add_workspace(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    self.stop()
                    # Use the parent cog's method to show token modal
                    await self.parent_cog._show_token_modal(button_interaction)
                
                @discord.ui.button(label="View Current Status", style=discord.ButtonStyle.secondary, emoji="📊")
                async def view_status(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    self.stop()
                    status_embed = EmbedFactory.create_success_embed(
                        "✅ ClickUp Status",
                        f"ClickUp is working perfectly!"
                    )
                    
                    status_embed.add_field(
                        name="Available Commands",
                        value="• `/task-create` - Create new tasks\n"
                              "• `/task-list` - View and manage tasks\n"
                              "• `/calendar` - View tasks in calendar\n"
                              "• `/workspace-list` - Manage workspaces\n"
                              "• `/upcoming` - See upcoming tasks\n"
                              "• `/today` - View today's tasks",
                        inline=False
                    )
                    
                    await button_interaction.response.edit_message(embed=status_embed, view=None)
            
            setup_view = SetupOptionsView(self)
            await interaction.response.send_message(embed=embed, view=setup_view, ephemeral=True)
            return
        
        # Not configured - do the actual setup
        embed = EmbedFactory.create_info_embed(
            "🚀 ClickUp Setup",
            "Let's set up ClickUp for your server. I'll need your ClickUp API token."
        )
        
        embed.add_field(
            name="Get Your API Token",
            value="1. Go to [ClickUp Settings](https://app.clickup.com/settings/apps)\n"
                  "2. Click **API** in the left sidebar\n"
                  "3. Click **Generate** to create a new token\n"
                  "4. Copy the token (starts with `pk_`)",
            inline=False
        )
        
        # Show the same modal as workspace-add
        await self._show_token_modal(interaction)
    
    async def _show_token_modal(self, interaction: discord.Interaction):
        """Show the token input modal"""
        class TokenModal(discord.ui.Modal, title="ClickUp Workspace Setup"):
            def __init__(self):
                super().__init__()
                
                self.token_input = discord.ui.TextInput(
                    label="ClickUp API Token",
                    placeholder="Enter your ClickUp API token (pk_...)",
                    style=discord.TextStyle.short,
                    required=True,
                    min_length=10,
                    max_length=200
                )
                self.add_item(self.token_input)
            
            async def on_submit(self, modal_interaction: discord.Interaction):
                await modal_interaction.response.defer(ephemeral=True)
                
                token = self.token_input.value
                
                try:
                    # Test the token and get workspace info
                    api = ClickUpAPI(token)
                    async with api:
                        logger.info(f"Testing ClickUp API token for guild {modal_interaction.guild_id}")
                        workspaces = await api.get_workspaces()
                        logger.info(f"ClickUp API returned {len(workspaces)} workspaces")
                    
                    if not workspaces:
                        embed = EmbedFactory.create_error_embed(
                            "No Workspaces Found",
                            "No workspaces found with this token. Please check your API key.\n\n"
                            "**Common issues:**\n"
                            "• Token doesn't start with `pk_`\n"
                            "• Token is expired or invalid\n"
                            "• You don't have access to any workspaces"
                        )
                        await modal_interaction.followup.send(embed=embed, ephemeral=True)
                        return
                    
                    # If multiple workspaces, let user choose
                    if len(workspaces) > 1:
                        embed = EmbedFactory.create_info_embed(
                            "Select Workspace",
                            f"Found {len(workspaces)} workspaces. Choose which one to add:"
                        )
                        
                        class WorkspaceSelect(discord.ui.View):
                            def __init__(self):
                                super().__init__(timeout=60)
                                self.selected_workspace = None
                                
                                options = []
                                for ws in workspaces[:25]:
                                    options.append(
                                        discord.SelectOption(
                                            label=ws['name'][:100],
                                            value=ws['id'],
                                            description=f"ID: {ws['id']}"
                                        )
                                    )
                                
                                select = discord.ui.Select(
                                    placeholder="Choose a workspace...",
                                    options=options
                                )
                                select.callback = self.select_callback
                                self.add_item(select)
                            
                            async def select_callback(self, select_interaction: discord.Interaction):
                                self.selected_workspace = next(
                                    (ws for ws in workspaces if ws['id'] == select_interaction.data['values'][0]), 
                                    None
                                )
                                self.stop()
                                await select_interaction.response.defer_update()
                        
                        workspace_view = WorkspaceSelect()
                        await modal_interaction.followup.send(embed=embed, view=workspace_view, ephemeral=True)
                        
                        await workspace_view.wait()
                        
                        if not workspace_view.selected_workspace:
                            return
                        
                        selected_workspace = workspace_view.selected_workspace
                    else:
                        # Only one workspace
                        selected_workspace = workspaces[0]
                    
                    # Save the workspace
                    new_workspace = await ClickUpWorkspaceRepository.create_workspace(
                        guild_id=modal_interaction.guild_id,
                        workspace_id=selected_workspace['id'],
                        workspace_name=selected_workspace['name'],
                        token=token,
                        added_by_user_id=modal_interaction.user.id
                    )
                    
                    if new_workspace:
                        # Set as default if it's the first workspace
                        existing_workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(modal_interaction.guild_id)
                        if len(existing_workspaces) == 1:
                            await ClickUpWorkspaceRepository.set_default_workspace(
                                modal_interaction.guild_id, 
                                new_workspace.id
                            )
                        
                        embed = EmbedFactory.create_success_embed(
                            "✅ ClickUp Setup Complete!",
                            f"Successfully added workspace: **{selected_workspace['name']}**"
                        )
                        
                        if len(existing_workspaces) == 1:
                            embed.add_field(
                                name="Default Workspace",
                                value="✅ This workspace has been set as the default",
                                inline=False
                            )
                        
                        embed.add_field(
                            name="🎉 You're all set! Try these commands:",
                            value="• `/task-create` - Create your first task\n"
                                  "• `/task-list` - View existing tasks\n"
                                  "• `/calendar` - See tasks in calendar view\n"
                                  "• `/help` - Get full command list",
                            inline=False
                        )
                        
                        await modal_interaction.followup.send(embed=embed, ephemeral=True)
                        
                        logger.info(f"ClickUp setup completed for guild {modal_interaction.guild_id}")
                    else:
                        embed = EmbedFactory.create_error_embed(
                            "Setup Failed",
                            "There was an error saving the workspace configuration."
                        )
                        await modal_interaction.followup.send(embed=embed, ephemeral=True)
                
                except Exception as e:
                    logger.error(f"Error in ClickUp setup: {e}")
                    logger.error(f"Error type: {type(e).__name__}")
                    logger.error(f"Token starts with pk_: {token.startswith('pk_') if token else 'No token'}")
                    
                    # Provide specific error messages
                    error_message = "Failed to set up ClickUp."
                    
                    if "401" in str(e) or "Unauthorized" in str(e):
                        error_message += "\n\n**Issue**: Invalid or expired API token"
                        error_message += "\n**Solution**: Get a new token from ClickUp Settings → API"
                    elif "403" in str(e) or "Forbidden" in str(e):
                        error_message += "\n\n**Issue**: Token doesn't have workspace access"
                        error_message += "\n**Solution**: Make sure you have admin access to the workspace"
                    elif "timeout" in str(e).lower() or "network" in str(e).lower():
                        error_message += "\n\n**Issue**: Network connection problem"
                        error_message += "\n**Solution**: Try again in a moment"
                    elif not token.startswith('pk_'):
                        error_message += "\n\n**Issue**: Invalid token format"
                        error_message += "\n**Solution**: ClickUp API tokens start with 'pk_'"
                    else:
                        error_message += f"\n\n**Error**: {str(e)}"
                    
                    embed = EmbedFactory.create_error_embed(
                        "Setup Failed",
                        error_message
                    )
                    await modal_interaction.followup.send(embed=embed, ephemeral=True)
        
        modal = TokenModal()
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="workspace-add", description="Add a new ClickUp workspace")
    @app_commands.default_permissions(administrator=True)
    async def workspace_add(self, interaction: discord.Interaction):
        """Add a new ClickUp workspace to the server"""
        await self._show_token_modal(interaction)
    
    @app_commands.command(name="workspace-list", description="List all configured workspaces")
    async def workspace_list(self, interaction: discord.Interaction):
        """List all workspaces configured for this server"""
        workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if not workspaces:
            embed = EmbedFactory.create_info_embed(
                "No Workspaces Configured",
                "No ClickUp workspaces have been added to this server.\n"
                "Use `/workspace-add` to get started!"
            )
            embed.add_field(
                name="Getting Started",
                value="1. Get your ClickUp API token from [ClickUp Settings](https://app.clickup.com/settings/apps)\n"
                      "2. Run `/workspace-add` and paste your token\n"
                      "3. Select which workspace to use",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get default workspace
        default_workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
        default_id = default_workspace.id if default_workspace else None
        
        embed = EmbedFactory.create_info_embed(
            f"📋 Configured Workspaces ({len(workspaces)})",
            "All ClickUp workspaces configured for this server:"
        )
        
        for workspace in workspaces:
            is_default = "🏆 " if workspace.id == default_id else ""
            status = "✅ Active" if workspace.is_active else "❌ Inactive"
            
            embed.add_field(
                name=f"{is_default}{workspace.workspace_name}",
                value=f"• Status: {status}\n"
                      f"• ID: `{workspace.workspace_id}`\n"
                      f"• Added: <t:{int(workspace.created_at.timestamp())}:R>",
                inline=True
            )
        
        embed.add_field(
            name="Commands",
            value="• `/workspace-switch` - Change default workspace\n"
                  "• `/workspace-remove` - Remove a workspace",
            inline=False
        )
        
        embed.set_footer(text="🏆 = Default workspace")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="workspace-switch", description="Switch the default workspace")
    async def workspace_switch(self, interaction: discord.Interaction):
        """Switch the default workspace for this server"""
        workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if not workspaces:
            embed = EmbedFactory.create_error_embed(
                "No Workspaces",
                "No workspaces configured. Use `/clickup-setup` or `/workspace-add` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if len(workspaces) == 1:
            embed = EmbedFactory.create_info_embed(
                "Only One Workspace",
                f"Only one workspace is configured: **{workspaces[0].workspace_name}**"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get current default
        current_default = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
        
        embed = EmbedFactory.create_info_embed(
            "Switch Default Workspace",
            "Choose which workspace to set as default:"
        )
        
        class WorkspaceSwitchView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.selected_workspace = None
                
                options = []
                for ws in workspaces:
                    is_current = " (Current)" if current_default and ws.id == current_default.id else ""
                    options.append(
                        discord.SelectOption(
                            label=f"{ws.workspace_name}{is_current}",
                            value=str(ws.id),
                            description=f"ID: {ws.workspace_id}",
                            default=(current_default and ws.id == current_default.id)
                        )
                    )
                
                select = discord.ui.Select(
                    placeholder="Choose workspace to set as default...",
                    options=options
                )
                select.callback = self.select_callback
                self.add_item(select)
            
            async def select_callback(self, select_interaction: discord.Interaction):
                workspace_db_id = int(select_interaction.data['values'][0])
                self.selected_workspace = next((ws for ws in workspaces if ws.id == workspace_db_id), None)
                self.stop()
                await select_interaction.response.defer_update()
        
        switch_view = WorkspaceSwitchView()
        await interaction.response.send_message(embed=embed, view=switch_view, ephemeral=True)
        
        await switch_view.wait()
        
        if not switch_view.selected_workspace:
            return
        
        # Update default workspace
        success = await ClickUpWorkspaceRepository.set_default_workspace(
            interaction.guild_id, switch_view.selected_workspace.id
        )
        
        if success:
            embed = EmbedFactory.create_success_embed(
                "Default Workspace Updated",
                f"✅ **{switch_view.selected_workspace.workspace_name}** is now the default workspace"
            )
            
            embed.add_field(
                name="What This Means",
                value="• `/calendar`, `/upcoming`, `/today` will show tasks from this workspace\n"
                      "• `/task-create` will default to lists in this workspace\n"
                      "• AI commands will operate in this workspace\n"
                      "• You can switch workspaces anytime with `/workspace-switch`",
                inline=False
            )
        else:
            embed = EmbedFactory.create_error_embed(
                "Update Failed",
                "Failed to update the default workspace."
            )
        
        await interaction.edit_original_response(embed=embed, view=None)
    
    @app_commands.command(name="workspace-remove", description="Remove a workspace from this server")
    @app_commands.default_permissions(administrator=True)
    async def workspace_remove(self, interaction: discord.Interaction):
        """Remove a workspace from this server"""
        workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if not workspaces:
            embed = EmbedFactory.create_error_embed(
                "No Workspaces",
                "No workspaces configured to remove."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = EmbedFactory.create_warning_embed(
            "Remove Workspace",
            "⚠️ Choose which workspace to remove:"
        )
        
        class WorkspaceRemoveView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.selected_workspace = None
                
                options = []
                for ws in workspaces:
                    options.append(
                        discord.SelectOption(
                            label=ws.workspace_name,
                            value=str(ws.id),
                            description=f"ID: {ws.workspace_id}"
                        )
                    )
                
                select = discord.ui.Select(
                    placeholder="Choose workspace to remove...",
                    options=options
                )
                select.callback = self.select_callback
                self.add_item(select)
            
            async def select_callback(self, select_interaction: discord.Interaction):
                workspace_db_id = int(select_interaction.data['values'][0])
                self.selected_workspace = next((ws for ws in workspaces if ws.id == workspace_db_id), None)
                self.stop()
                await select_interaction.response.defer_update()
        
        remove_view = WorkspaceRemoveView()
        await interaction.response.send_message(embed=embed, view=remove_view, ephemeral=True)
        
        await remove_view.wait()
        
        if not remove_view.selected_workspace:
            return
        
        # Confirm removal
        embed = EmbedFactory.create_warning_embed(
            "Confirm Removal",
            f"⚠️ Are you sure you want to remove workspace:\n**{remove_view.selected_workspace.workspace_name}**?\n\n"
            "This will delete the stored API token and workspace configuration."
        )
        
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.confirmed = False
            
            @discord.ui.button(label="Remove Workspace", style=discord.ButtonStyle.danger)
            async def confirm(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.confirmed = True
                self.stop()
                await button_interaction.response.defer_update()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.stop()
                await button_interaction.response.defer_update()
        
        confirm_view = ConfirmView()
        await interaction.edit_original_response(embed=embed, view=confirm_view)
        
        await confirm_view.wait()
        
        if not confirm_view.confirmed:
            embed = EmbedFactory.create_info_embed("Cancelled", "Workspace removal cancelled.")
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        # Remove the workspace
        success = await ClickUpWorkspaceRepository.remove_workspace(remove_view.selected_workspace.id)
        
        if success:
            embed = EmbedFactory.create_success_embed(
                "Workspace Removed",
                f"✅ Removed workspace: **{remove_view.selected_workspace.workspace_name}**"
            )
            
            # Check if we need to set a new default
            remaining_workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
            if remaining_workspaces:
                # Auto-set first remaining workspace as default
                await ClickUpWorkspaceRepository.set_default_workspace(
                    interaction.guild_id, remaining_workspaces[0].id
                )
                embed.add_field(
                    name="New Default",
                    value=f"**{remaining_workspaces[0].workspace_name}** is now the default workspace",
                    inline=False
                )
        else:
            embed = EmbedFactory.create_error_embed(
                "Removal Failed",
                "Failed to remove the workspace."
            )
        
        await interaction.edit_original_response(embed=embed, view=None)
    
    @app_commands.command(name="workspace-status", description="Show current workspace status")
    async def workspace_status(self, interaction: discord.Interaction):
        """Show which workspace is currently active"""
        workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if not workspaces:
            embed = EmbedFactory.create_error_embed(
                "No Workspaces",
                "No workspaces configured. Use `/clickup-setup` or `/workspace-add` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get current default
        current_default = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
        
        if current_default:
            embed = EmbedFactory.create_success_embed(
                "✅ Current Active Workspace",
                f"**{current_default.workspace_name}**"
            )
            
            embed.add_field(
                name="Workspace Details",
                value=f"• **Name:** {current_default.workspace_name}\n"
                      f"• **ID:** `{current_default.workspace_id}`\n"
                      f"• **Added:** <t:{int(current_default.created_at.timestamp())}:R>\n"
                      f"• **Status:** {'✅ Active' if current_default.is_active else '❌ Inactive'}",
                inline=False
            )
            
            embed.add_field(
                name="Commands Using This Workspace",
                value="• `/calendar` - View all tasks in calendar\n"
                      "• `/upcoming` - See upcoming tasks\n"
                      "• `/today` - View today's tasks\n"
                      "• `/task-create` - Create new tasks\n"
                      "• `/ai-assistant` - AI-powered features",
                inline=False
            )
            
            if len(workspaces) > 1:
                embed.add_field(
                    name="Switch Workspace",
                    value="Use `/workspace-switch` to change active workspace",
                    inline=False
                )
        else:
            embed = EmbedFactory.create_warning_embed(
                "No Default Workspace",
                "No default workspace is set."
            )
            
            embed.add_field(
                name="Available Workspaces",
                value="\n".join([f"• {ws.workspace_name}" for ws in workspaces]),
                inline=False
            )
            
            embed.add_field(
                name="Set Default",
                value="Use `/workspace-switch` to set a default workspace",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(WorkspaceManagement(bot))