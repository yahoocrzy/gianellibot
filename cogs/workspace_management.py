import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from services.clickup_oauth import clickup_oauth
from repositories.clickup_oauth_workspaces import ClickUpOAuthWorkspaceRepository
from utils.embed_factory import EmbedFactory
from loguru import logger
import os

class WorkspaceManagement(commands.Cog):
    """OAuth2-based ClickUp workspace management for the server"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="clickup-setup", description="Set up ClickUp integration using OAuth2 login")
    @app_commands.default_permissions(administrator=True)
    async def clickup_setup(self, interaction: discord.Interaction):
        """Complete ClickUp setup using OAuth2 - one-click login"""
        
        # Check if OAuth2 is configured
        if not clickup_oauth.is_configured():
            embed = EmbedFactory.create_error_embed(
                "OAuth2 Not Configured",
                "ClickUp OAuth2 credentials are not configured on this bot instance."
            )
            embed.add_field(
                name="Configuration Required",
                value="The bot administrator needs to set:\n"
                      "• `CLICKUP_CLIENT_ID`\n"
                      "• `CLICKUP_CLIENT_SECRET`\n"
                      "• `CLICKUP_REDIRECT_URI`",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check if already configured
        workspaces = await ClickUpOAuthWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if workspaces:
            # Already configured - offer options
            default_workspace = await ClickUpOAuthWorkspaceRepository.get_default_workspace(interaction.guild_id)
            
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
                
                @discord.ui.button(label="Add More Workspaces", style=discord.ButtonStyle.primary, emoji="➕")
                async def add_workspace(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    self.stop()
                    await self.parent_cog._start_oauth_flow(button_interaction)
                
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
        
        # Not configured - do the actual OAuth2 setup
        await self._start_oauth_flow(interaction)
    
    async def _start_oauth_flow(self, interaction: discord.Interaction):
        """Start the OAuth2 flow"""
        try:
            # Create OAuth2 state
            state, auth_url = await ClickUpOAuthWorkspaceRepository.create_oauth_state(
                interaction.guild_id, 
                interaction.user.id
            )
            
            # Create embed with login button
            embed = EmbedFactory.create_info_embed(
                "🔐 ClickUp OAuth2 Login",
                "Click the button below to securely connect your ClickUp account!"
            )
            
            embed.add_field(
                name="How it Works",
                value="1. Click **Login with ClickUp** below\n"
                      "2. You'll be redirected to ClickUp's secure login page\n"
                      "3. Sign in with your ClickUp credentials\n"
                      "4. Choose which workspaces to authorize\n"
                      "5. Return here - setup complete! 🎉",
                inline=False
            )
            
            embed.add_field(
                name="✅ Benefits of OAuth2",
                value="• **Secure** - No copying API tokens\n"
                      "• **Easy** - Just click and login\n"
                      "• **Automatic** - Tokens managed for you\n"
                      "• **Multiple Workspaces** - Authorize as many as you want",
                inline=False
            )
            
            embed.add_field(
                name="🔒 Privacy & Security",
                value="• Your login credentials are never stored\n"
                      "• Only authorized workspace data is accessed\n"
                      "• You can revoke access anytime in ClickUp settings",
                inline=False
            )
            
            class OAuthLoginView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=300)  # 5 minutes to click
                    
                    # Add login button
                    login_button = discord.ui.Button(
                        label="🔐 Login with ClickUp",
                        style=discord.ButtonStyle.link,
                        url=auth_url,
                        emoji="🚀"
                    )
                    self.add_item(login_button)
            
            oauth_view = OAuthLoginView()
            
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, view=oauth_view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=oauth_view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error starting OAuth flow: {e}")
            embed = EmbedFactory.create_error_embed(
                "Setup Failed",
                f"Failed to start OAuth2 setup: {str(e)}"
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="workspace-add", description="Add additional ClickUp workspaces using OAuth2")
    @app_commands.default_permissions(administrator=True)
    async def workspace_add(self, interaction: discord.Interaction):
        """Add a new ClickUp workspace using OAuth2"""
        if not clickup_oauth.is_configured():
            embed = EmbedFactory.create_error_embed(
                "OAuth2 Not Configured",
                "ClickUp OAuth2 credentials are not configured."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        await self._start_oauth_flow(interaction)
    
    @app_commands.command(name="workspace-list", description="List all configured workspaces")
    async def workspace_list(self, interaction: discord.Interaction):
        """List all workspaces configured for this server"""
        workspaces = await ClickUpOAuthWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if not workspaces:
            embed = EmbedFactory.create_info_embed(
                "No Workspaces Configured",
                "No ClickUp workspaces have been added to this server.\n"
                "Use `/clickup-setup` to get started!"
            )
            embed.add_field(
                name="🚀 Getting Started",
                value="1. Run `/clickup-setup`\n"
                      "2. Click **Login with ClickUp**\n"
                      "3. Sign in and authorize workspaces\n"
                      "4. Start using ClickUp commands!",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get default workspace
        default_workspace = await ClickUpOAuthWorkspaceRepository.get_default_workspace(interaction.guild_id)
        default_id = default_workspace.id if default_workspace else None
        
        embed = EmbedFactory.create_info_embed(
            f"📋 Connected Workspaces ({len(workspaces)})",
            "All ClickUp workspaces authorized for this server:"
        )
        
        for workspace in workspaces:
            is_default = "🏆 " if workspace.id == default_id else ""
            status = "✅ Active" if workspace.is_active else "❌ Inactive"
            
            embed.add_field(
                name=f"{is_default}{workspace.workspace_name}",
                value=f"• Status: {status}\n"
                      f"• ID: `{workspace.workspace_id}`\n"
                      f"• Authorized: <t:{int(workspace.authorized_at.timestamp())}:R>",
                inline=True
            )
        
        embed.add_field(
            name="🛠️ Management Commands",
            value="• `/workspace-switch` - Change default workspace\n"
                  "• `/workspace-remove` - Remove a workspace\n"
                  "• `/workspace-clear` - Remove all workspaces",
            inline=False
        )
        
        embed.set_footer(text="🏆 = Default workspace • OAuth2 tokens never expire")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="workspace-switch", description="Switch the default workspace")
    async def workspace_switch(self, interaction: discord.Interaction):
        """Switch the default workspace for this server"""
        workspaces = await ClickUpOAuthWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if not workspaces:
            embed = EmbedFactory.create_error_embed(
                "No Workspaces",
                "No workspaces configured. Use `/clickup-setup` first."
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
        current_default = await ClickUpOAuthWorkspaceRepository.get_default_workspace(interaction.guild_id)
        
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
        success = await ClickUpOAuthWorkspaceRepository.set_default_workspace(
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
        workspaces = await ClickUpOAuthWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
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
            "This will delete the OAuth2 authorization and workspace configuration."
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
        success = await ClickUpOAuthWorkspaceRepository.remove_workspace(remove_view.selected_workspace.id)
        
        if success:
            embed = EmbedFactory.create_success_embed(
                "Workspace Removed",
                f"✅ Removed workspace: **{remove_view.selected_workspace.workspace_name}**"
            )
            
            # Check if we need to set a new default
            remaining_workspaces = await ClickUpOAuthWorkspaceRepository.get_all_workspaces(interaction.guild_id)
            if remaining_workspaces:
                # Auto-set first remaining workspace as default
                await ClickUpOAuthWorkspaceRepository.set_default_workspace(
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
    
    @app_commands.command(name="workspace-clear", description="Clear ALL workspaces from this server")
    @app_commands.default_permissions(administrator=True)
    async def workspace_clear(self, interaction: discord.Interaction):
        """Clear all workspaces from this server - WARNING: This will remove all ClickUp configuration"""
        workspaces = await ClickUpOAuthWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if not workspaces:
            embed = EmbedFactory.create_info_embed(
                "No Workspaces",
                "No workspaces are currently configured to clear."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Show warning and confirmation
        embed = EmbedFactory.create_warning_embed(
            "⚠️ DANGER: Clear All Workspaces",
            f"This will **permanently remove ALL {len(workspaces)} workspace(s)** from this server."
        )
        
        embed.add_field(
            name="What Will Be Deleted",
            value=f"• All {len(workspaces)} ClickUp workspace configurations\n"
                  "• All OAuth2 access tokens\n" 
                  "• All workspace preferences\n"
                  "• Default workspace settings",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ This Action Cannot Be Undone",
            value="You will need to run `/clickup-setup` again to reconfigure ClickUp.",
            inline=False
        )
        
        # Show workspace list
        workspace_list = "\n".join([f"• {ws.workspace_name} (`{ws.workspace_id}`)" for ws in workspaces[:10]])
        if len(workspaces) > 10:
            workspace_list += f"\n• ...and {len(workspaces) - 10} more"
            
        embed.add_field(
            name="Workspaces to be Removed",
            value=workspace_list,
            inline=False
        )
        
        class ClearConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.confirmed = False
            
            @discord.ui.button(label="🗑️ YES - Clear All Workspaces", style=discord.ButtonStyle.danger)
            async def confirm_clear(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.confirmed = True
                self.stop()
                await button_interaction.response.defer()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel_clear(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.stop()
                await button_interaction.response.defer()
        
        confirm_view = ClearConfirmView()
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)
        
        await confirm_view.wait()
        
        if not confirm_view.confirmed:
            embed = EmbedFactory.create_info_embed("Cancelled", "Workspace clearing cancelled.")
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        # Clear all workspaces
        try:
            success_count = 0
            for workspace in workspaces:
                success = await ClickUpOAuthWorkspaceRepository.remove_workspace(workspace.id)
                if success:
                    success_count += 1
            
            if success_count == len(workspaces):
                embed = EmbedFactory.create_success_embed(
                    "✅ All Workspaces Cleared",
                    f"Successfully removed all {success_count} workspace(s) from this server."
                )
                embed.add_field(
                    name="Next Steps",
                    value="• Run `/clickup-setup` to configure ClickUp again\n"
                          "• Or use `/workspace-add` to add specific workspaces",
                    inline=False
                )
            else:
                embed = EmbedFactory.create_warning_embed(
                    "Partial Success",
                    f"Removed {success_count} out of {len(workspaces)} workspace(s). Some may have failed to delete."
                )
        except Exception as e:
            logger.error(f"Error clearing workspaces: {e}")
            embed = EmbedFactory.create_error_embed(
                "Clear Failed",
                f"Failed to clear workspaces: {str(e)}"
            )
        
        await interaction.edit_original_response(embed=embed, view=None)
    
    @app_commands.command(name="workspace-status", description="Show current workspace status")
    async def workspace_status(self, interaction: discord.Interaction):
        """Show which workspace is currently active"""
        workspaces = await ClickUpOAuthWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if not workspaces:
            embed = EmbedFactory.create_error_embed(
                "No Workspaces",
                "No workspaces configured. Use `/clickup-setup` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get current default
        current_default = await ClickUpOAuthWorkspaceRepository.get_default_workspace(interaction.guild_id)
        
        if current_default:
            embed = EmbedFactory.create_success_embed(
                "✅ Current Active Workspace",
                f"**{current_default.workspace_name}**"
            )
            
            embed.add_field(
                name="Workspace Details",
                value=f"• **Name:** {current_default.workspace_name}\n"
                      f"• **ID:** `{current_default.workspace_id}`\n"
                      f"• **Authorized:** <t:{int(current_default.authorized_at.timestamp())}:R>\n"
                      f"• **Status:** {'✅ Active' if current_default.is_active else '❌ Inactive'}\n"
                      f"• **Auth Type:** OAuth2 (Secure)",
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
    
    @app_commands.command(name="workspace-add-token", description="Add personal API token for full workspace access")
    @app_commands.default_permissions(administrator=True)
    async def workspace_add_token(self, interaction: discord.Interaction):
        """Add personal API token to enable full workspace functionality"""
        workspaces = await ClickUpOAuthWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if not workspaces:
            embed = EmbedFactory.create_error_embed(
                "No Workspaces",
                "No workspaces configured. Use `/clickup-setup` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = EmbedFactory.create_info_embed(
            "🔑 Add Personal API Token",
            "Due to ClickUp's OAuth limitations, personal API tokens are needed for full access to spaces and tasks."
        )
        
        embed.add_field(
            name="Why Personal API Tokens?",
            value="• OAuth2 works for workspace management\n"
                  "• Personal tokens enable space/task operations\n"
                  "• Provides full functionality until ClickUp improves OAuth\n"
                  "• Optional - only needed for `/task-create`, `/calendar`, etc.",
            inline=False
        )
        
        embed.add_field(
            name="How to Get Your Token:",
            value="1. Go to [ClickUp Settings > Apps](https://app.clickup.com/settings/apps)\n"
                  "2. Scroll to **Personal API Token**\n"
                  "3. Click **Generate** or **Copy** your token\n"
                  "4. Select a workspace below and enter the token",
            inline=False
        )
        
        # Create workspace selection
        class WorkspaceTokenView(discord.ui.View):
            def __init__(self, parent_cog):
                super().__init__(timeout=300)
                self.parent_cog = parent_cog
                self.selected_workspace = None
                
                options = []
                for ws in workspaces:
                    has_token = "✅" if ws.personal_api_token else "❌"
                    options.append(
                        discord.SelectOption(
                            label=f"{ws.workspace_name}",
                            value=str(ws.id),
                            description=f"Personal token: {has_token} | ID: {ws.workspace_id}",
                            emoji="🔑" if not ws.personal_api_token else "✅"
                        )
                    )
                
                select = discord.ui.Select(
                    placeholder="Choose workspace to add token...",
                    options=options
                )
                select.callback = self.select_callback
                self.add_item(select)
            
            async def select_callback(self, select_interaction: discord.Interaction):
                workspace_db_id = int(select_interaction.data['values'][0])
                self.selected_workspace = next((ws for ws in workspaces if ws.id == workspace_db_id), None)
                self.stop()
                await select_interaction.response.defer_update()
        
        token_view = WorkspaceTokenView(self)
        await interaction.response.send_message(embed=embed, view=token_view, ephemeral=True)
        
        await token_view.wait()
        
        if not token_view.selected_workspace:
            return
        
        # Show token input modal
        class TokenModal(discord.ui.Modal):
            def __init__(self, workspace):
                super().__init__(title=f"Add Token for {workspace.workspace_name}")
                self.workspace = workspace
                
                self.token_input = discord.ui.TextInput(
                    label="Personal API Token",
                    placeholder="pk_123456789_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
                    style=discord.TextStyle.short,
                    max_length=100,
                    required=True
                )
                self.add_item(self.token_input)
            
            async def on_submit(self, modal_interaction: discord.Interaction):
                token = self.token_input.value.strip()
                
                if not token.startswith('pk_'):
                    embed = EmbedFactory.create_error_embed(
                        "Invalid Token",
                        "ClickUp personal API tokens start with 'pk_'. Please check your token."
                    )
                    await modal_interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                
                # Save the token
                success = await ClickUpOAuthWorkspaceRepository.set_personal_api_token(
                    self.workspace.id, token
                )
                
                if success:
                    embed = EmbedFactory.create_success_embed(
                        "✅ Token Added Successfully",
                        f"Personal API token added to **{self.workspace.workspace_name}**"
                    )
                    
                    embed.add_field(
                        name="What's Enabled Now",
                        value="• Full access to spaces and tasks\n"
                              "• `/task-create` will work properly\n"
                              "• `/calendar` will show all tasks\n"
                              "• All ClickUp commands fully functional",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="Test It Out",
                        value="Try `/task-create` or `/calendar` now!",
                        inline=False
                    )
                else:
                    embed = EmbedFactory.create_error_embed(
                        "Failed to Save Token",
                        "Could not save the personal API token. Please try again."
                    )
                
                await modal_interaction.response.send_message(embed=embed, ephemeral=True)
        
        modal = TokenModal(token_view.selected_workspace)
        await interaction.edit_original_response(embed=embed, view=None)
        await interaction.followup.send("Opening token input form...", ephemeral=True)
        await interaction.followup.send_modal(modal)

async def setup(bot):
    await bot.add_cog(WorkspaceManagement(bot))