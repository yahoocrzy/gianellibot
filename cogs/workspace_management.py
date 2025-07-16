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
    
    @app_commands.command(name="workspace-add", description="Add a new ClickUp workspace")
    @app_commands.default_permissions(administrator=True)
    async def workspace_add(self, interaction: discord.Interaction):
        """Add a new ClickUp workspace to the server"""
        
        # Show secure token input modal
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
                        workspaces = await api.get_workspaces()
                    
                    if not workspaces:
                        embed = EmbedFactory.create_error_embed(
                            "No Workspaces Found",
                            "No workspaces found with this token. Please check your API key."
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
                                workspace_id = select_interaction.data['values'][0]
                                self.selected_workspace = next(
                                    (ws for ws in workspaces if ws['id'] == workspace_id), None
                                )
                                self.stop()
                                await select_interaction.response.defer_update()
                        
                        workspace_view = WorkspaceSelect()
                        await modal_interaction.followup.send(embed=embed, view=workspace_view, ephemeral=True)
                        
                        timed_out = await workspace_view.wait()
                        
                        if timed_out or not workspace_view.selected_workspace:
                            embed = EmbedFactory.create_error_embed("Timeout", "Workspace selection timed out.")
                            await modal_interaction.edit_original_response(embed=embed, view=None)
                            return
                        
                        selected_workspace = workspace_view.selected_workspace
                    else:
                        selected_workspace = workspaces[0]
                    
                    # Save the workspace
                    workspace_config = await ClickUpWorkspaceRepository.create_workspace(
                        guild_id=modal_interaction.guild_id,
                        workspace_id=selected_workspace['id'],
                        workspace_name=selected_workspace['name'],
                        token=token,
                        added_by_user_id=modal_interaction.user.id
                    )
                    
                    if workspace_config:
                        embed = EmbedFactory.create_success_embed(
                            "Workspace Added Successfully!",
                            f"✅ Added workspace: **{selected_workspace['name']}**"
                        )
                        
                        embed.add_field(
                            name="Workspace Info",
                            value=f"• Name: {selected_workspace['name']}\n"
                                  f"• ID: `{selected_workspace['id']}`\n"
                                  f"• Added by: {modal_interaction.user.mention}",
                            inline=False
                        )
                        
                        # Check if this is the first workspace (auto-set as default)
                        existing_workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(modal_interaction.guild_id)
                        if len(existing_workspaces) == 1:
                            await ClickUpWorkspaceRepository.set_default_workspace(
                                modal_interaction.guild_id, workspace_config.id
                            )
                            embed.add_field(
                                name="Default Workspace",
                                value="✅ This workspace has been set as the default",
                                inline=False
                            )
                        
                        embed.add_field(
                            name="Available Commands",
                            value="• `/task-create` - Create new tasks\n"
                                  "• `/task-list` - View tasks\n"
                                  "• `/calendar` - Calendar view\n"
                                  "• `/workspace-switch` - Switch workspaces",
                            inline=False
                        )
                        
                        await modal_interaction.followup.send(embed=embed, ephemeral=True)
                        
                        logger.info(f"Workspace {selected_workspace['name']} added to guild {modal_interaction.guild_id}")
                    else:
                        embed = EmbedFactory.create_error_embed(
                            "Failed to Add Workspace",
                            "There was an error saving the workspace configuration."
                        )
                        await modal_interaction.followup.send(embed=embed, ephemeral=True)
                
                except Exception as e:
                    logger.error(f"Error adding workspace: {e}")
                    embed = EmbedFactory.create_error_embed(
                        "Error Adding Workspace",
                        f"Failed to add workspace: {str(e)}"
                    )
                    await modal_interaction.followup.send(embed=embed, ephemeral=True)
        
        modal = TokenModal()
        await interaction.response.send_modal(modal)
    
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
                "No workspaces configured. Use `/clickup-setup` OR `/workspace-add` first."
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
                "No workspaces configured. Use `/clickup-setup` OR `/workspace-add` first."
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