import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from utils.embed_factory import EmbedFactory
from repositories.clickup_workspaces import ClickUpWorkspaceRepository
from services.clickup_api import ClickUpAPI
from loguru import logger

class WorkspaceSelectView(discord.ui.View):
    def __init__(self, workspaces: List, action: str = "select"):
        super().__init__(timeout=300)
        self.selected_workspace = None
        self.action = action
        
        # Create dropdown with workspaces
        options = []
        for ws in workspaces[:25]:  # Discord limit
            options.append(
                discord.SelectOption(
                    label=ws.workspace_name,
                    value=ws.workspace_id,
                    description=f"ID: {ws.workspace_id}",
                    default=ws.is_default
                )
            )
        
        select = discord.ui.Select(
            placeholder="Choose a workspace...",
            options=options,
            min_values=1,
            max_values=1
        )
        select.callback = self.workspace_callback
        self.add_item(select)
    
    async def workspace_callback(self, interaction: discord.Interaction):
        self.selected_workspace = interaction.data['values'][0]
        self.stop()
        
        if self.action == "select":
            await interaction.response.send_message(
                f"Selected workspace: {interaction.data['values'][0]}",
                ephemeral=True
            )
        else:
            await interaction.response.defer()

class WorkspaceManagement(commands.Cog):
    """Commands for managing multiple ClickUp workspaces"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="workspace-add", description="Add a new ClickUp workspace")
    @app_commands.default_permissions(administrator=True)
    async def workspace_add(self, interaction: discord.Interaction):
        """Add a new ClickUp workspace to the server"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Test the token and get workspace info
            api = ClickUpAPI(token)
            workspaces = await api.get_workspaces()
            
            if not workspaces:
                embed = EmbedFactory.create_error_embed(
                    "Invalid Token",
                    "Could not access any workspaces with this token. Please check your API token."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Show workspace selection
            embed = EmbedFactory.create_info_embed(
                "Select Workspace",
                f"Found {len(workspaces)} workspace(s). Please select which one to add:"
            )
            
            # Format workspace list
            ws_list = "\n".join([f"• **{ws['name']}** (ID: {ws['id']})" for ws in workspaces[:10]])
            embed.add_field(name="Available Workspaces", value=ws_list, inline=False)
            
            # Create selection view
            options = []
            for ws in workspaces[:25]:  # Discord limit
                options.append(
                    discord.SelectOption(
                        label=ws['name'],
                        value=ws['id'],
                        description=f"ID: {ws['id']}"
                    )
                )
            
            class WorkspaceAddView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=60)
                    self.selected = None
                
                @discord.ui.select(
                    placeholder="Choose a workspace to add...",
                    options=options
                )
                async def select_workspace(self, interaction: discord.Interaction, select: discord.ui.Select):
                    self.selected = select.values[0]
                    self.stop()
                    await interaction.response.defer()
            
            view = WorkspaceAddView()
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
            await view.wait()
            
            if not view.selected:
                embed = EmbedFactory.create_info_embed(
                    "Cancelled",
                    "Workspace addition cancelled."
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Find selected workspace
            selected_ws = next(ws for ws in workspaces if ws['id'] == view.selected)
            
            # Check if workspace already exists
            if await ClickUpWorkspaceRepository.workspace_exists(interaction.guild_id, selected_ws['id']):
                # Offer to update token
                embed = EmbedFactory.create_warning_embed(
                    "Workspace Exists",
                    f"The workspace **{selected_ws['name']}** is already configured.\n"
                    "Would you like to update its API token?"
                )
                
                class UpdateConfirmView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=30)
                        self.confirmed = False
                    
                    @discord.ui.button(label="Update Token", style=discord.ButtonStyle.primary)
                    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                        self.confirmed = True
                        self.stop()
                        await interaction.response.defer()
                    
                    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
                    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                        self.stop()
                        await interaction.response.defer()
                
                confirm_view = UpdateConfirmView()
                await interaction.edit_original_response(embed=embed, view=confirm_view)
                
                await confirm_view.wait()
                
                if confirm_view.confirmed:
                    success = await ClickUpWorkspaceRepository.update_workspace_token(
                        interaction.guild_id,
                        selected_ws['id'],
                        token
                    )
                    
                    if success:
                        embed = EmbedFactory.create_success_embed(
                            "Token Updated",
                            f"Successfully updated API token for **{selected_ws['name']}**"
                        )
                    else:
                        embed = EmbedFactory.create_error_embed(
                            "Update Failed",
                            "Failed to update workspace token."
                        )
                else:
                    embed = EmbedFactory.create_info_embed(
                        "Cancelled",
                        "Token update cancelled."
                    )
                
                await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Check if this is the first workspace
            existing_workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
            is_first = len(existing_workspaces) == 0
            
            # Add the workspace
            await ClickUpWorkspaceRepository.create_workspace(
                guild_id=interaction.guild_id,
                workspace_id=selected_ws['id'],
                workspace_name=selected_ws['name'],
                token=token,
                added_by_user_id=interaction.user.id,
                is_default=is_first  # First workspace is default
            )
            
            embed = EmbedFactory.create_success_embed(
                "Workspace Added",
                f"Successfully added workspace **{selected_ws['name']}**"
            )
            
            if is_first:
                embed.add_field(
                    name="Default Workspace",
                    value="This is your first workspace and has been set as default.",
                    inline=False
                )
            
            embed.add_field(
                name="Next Steps",
                value="• Use `/workspace-list` to see all workspaces\n"
                      "• Use `/workspace-switch` to change active workspace\n"
                      "• Use `/select-list` to browse lists in this workspace",
                inline=False
            )
            
            await interaction.edit_original_response(embed=embed, view=None)
            
            logger.info(f"Added workspace {selected_ws['name']} to guild {interaction.guild_id}")
            
        except Exception as e:
            logger.error(f"Error adding workspace: {e}")
            embed = EmbedFactory.create_error_embed(
                "Error",
                f"Failed to add workspace: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed, view=None)
    
    @app_commands.command(name="workspace-list", description="List all configured workspaces")
    async def workspace_list(self, interaction: discord.Interaction):
        """List all workspaces for this server"""
        await interaction.response.defer(ephemeral=True)
        
        workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if not workspaces:
            embed = EmbedFactory.create_info_embed(
                "No Workspaces",
                "No workspaces have been configured yet.\n"
                "Use `/workspace-add` to add your first workspace."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        embed = EmbedFactory.create_info_embed(
            "ClickUp Workspaces",
            f"Found {len(workspaces)} configured workspace(s):"
        )
        
        for ws in workspaces:
            status = "🟢 Default" if ws.is_default else "⚪ Active"
            added_by = f"<@{ws.added_by_user_id}>"
            
            embed.add_field(
                name=f"{status} {ws.workspace_name}",
                value=f"ID: `{ws.workspace_id}`\nAdded by: {added_by}\nAdded: <t:{int(ws.created_at.timestamp())}:R>",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="workspace-switch", description="Switch the default workspace")
    async def workspace_switch(self, interaction: discord.Interaction):
        """Switch between workspaces"""
        await interaction.response.defer(ephemeral=True)
        
        workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if not workspaces:
            embed = EmbedFactory.create_info_embed(
                "No Workspaces",
                "No workspaces have been configured yet.\n"
                "Use `/workspace-add` to add workspaces."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        if len(workspaces) == 1:
            embed = EmbedFactory.create_info_embed(
                "Single Workspace",
                f"Only one workspace is configured: **{workspaces[0].workspace_name}**\n"
                "Add more workspaces with `/workspace-add` to switch between them."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        embed = EmbedFactory.create_info_embed(
            "Switch Workspace",
            "Select the workspace to set as default:"
        )
        
        view = WorkspaceSelectView(workspaces, action="switch")
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
        await view.wait()
        
        if not view.selected_workspace:
            embed = EmbedFactory.create_info_embed(
                "Cancelled",
                "Workspace switch cancelled."
            )
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        # Set as default
        success = await ClickUpWorkspaceRepository.set_default_workspace(
            interaction.guild_id,
            view.selected_workspace
        )
        
        if success:
            # Get the workspace details
            workspace = await ClickUpWorkspaceRepository.get_workspace(
                interaction.guild_id,
                view.selected_workspace
            )
            
            embed = EmbedFactory.create_success_embed(
                "Workspace Switched",
                f"Default workspace changed to **{workspace.workspace_name}**\n"
                "All ClickUp commands will now use this workspace by default."
            )
        else:
            embed = EmbedFactory.create_error_embed(
                "Switch Failed",
                "Failed to switch workspace. Please try again."
            )
        
        await interaction.edit_original_response(embed=embed, view=None)
    
    @app_commands.command(name="workspace-remove", description="Remove a workspace")
    @app_commands.default_permissions(administrator=True)
    async def workspace_remove(self, interaction: discord.Interaction):
        """Remove a workspace from the server"""
        await interaction.response.defer(ephemeral=True)
        
        workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if not workspaces:
            embed = EmbedFactory.create_info_embed(
                "No Workspaces",
                "No workspaces to remove."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        embed = EmbedFactory.create_warning_embed(
            "Remove Workspace",
            "Select a workspace to remove:"
        )
        
        view = WorkspaceSelectView(workspaces, action="remove")
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
        await view.wait()
        
        if not view.selected_workspace:
            embed = EmbedFactory.create_info_embed(
                "Cancelled",
                "Workspace removal cancelled."
            )
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        # Get workspace details before removal
        workspace = await ClickUpWorkspaceRepository.get_workspace(
            interaction.guild_id,
            view.selected_workspace
        )
        
        # Confirm removal
        embed = EmbedFactory.create_warning_embed(
            "Confirm Removal",
            f"Are you sure you want to remove **{workspace.workspace_name}**?\n"
            "This action cannot be undone."
        )
        
        class RemoveConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.confirmed = False
            
            @discord.ui.button(label="Remove", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.confirmed = True
                self.stop()
                await interaction.response.defer()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.stop()
                await interaction.response.defer()
        
        confirm_view = RemoveConfirmView()
        await interaction.edit_original_response(embed=embed, view=confirm_view)
        
        await confirm_view.wait()
        
        if not confirm_view.confirmed:
            embed = EmbedFactory.create_info_embed(
                "Cancelled",
                "Workspace removal cancelled."
            )
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        # Remove the workspace
        success = await ClickUpWorkspaceRepository.deactivate_workspace(
            interaction.guild_id,
            view.selected_workspace
        )
        
        if success:
            embed = EmbedFactory.create_success_embed(
                "Workspace Removed",
                f"Successfully removed **{workspace.workspace_name}**"
            )
            
            # Check if there are other workspaces
            remaining = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
            if remaining and not any(ws.is_default for ws in remaining):
                # Set the first one as default
                await ClickUpWorkspaceRepository.set_default_workspace(
                    interaction.guild_id,
                    remaining[0].workspace_id
                )
                embed.add_field(
                    name="New Default",
                    value=f"**{remaining[0].workspace_name}** is now the default workspace.",
                    inline=False
                )
        else:
            embed = EmbedFactory.create_error_embed(
                "Removal Failed",
                "Failed to remove workspace. Please try again."
            )
        
        await interaction.edit_original_response(embed=embed, view=None)
        
        logger.info(f"Removed workspace {workspace.workspace_name} from guild {interaction.guild_id}")

async def setup(bot):
    await bot.add_cog(WorkspaceManagement(bot))