import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Union
from repositories.reaction_roles import ReactionRoleRepository
from utils.embed_factory import EmbedFactory
from loguru import logger

class ReactionRoleChannelSelectView(discord.ui.View):
    def __init__(self, setup_callback):
        super().__init__(timeout=180)
        self.setup_callback = setup_callback
    
    def setup_for_guild(self, guild: discord.Guild):
        """Set up the channel dropdown for the specific guild"""
        # Get all text channels in the guild
        text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]
        
        if text_channels:
            # Create dropdown options (Discord limit: 25)
            options = []
            
            for channel in text_channels[:25]:
                options.append(discord.SelectOption(
                    label=f"#{channel.name}",
                    value=str(channel.id),
                    description=f"Create reaction roles in {channel.name}",
                    emoji="🔄"
                ))
            
            self.channel_select = discord.ui.Select(
                placeholder="Choose a channel for the reaction role message...",
                options=options,
                min_values=1,
                max_values=1
            )
            self.channel_select.callback = self.channel_callback
            self.add_item(self.channel_select)
        else:
            # No text channels found (shouldn't happen)
            self.add_item(discord.ui.Button(
                label="No text channels available",
                style=discord.ButtonStyle.secondary,
                disabled=True
            ))
    
    async def channel_callback(self, interaction: discord.Interaction):
        channel_id = int(self.channel_select.values[0])
        channel = interaction.guild.get_channel(channel_id)
        
        if not channel or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ Selected channel is no longer available.",
                ephemeral=True
            )
            return
        
        await self.setup_callback(interaction, channel)

class ReactionRoleSetupView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=300)
        self.channel = channel
        self.roles_data = []
        self.message_title = "React for Roles"
        self.message_description = "React to this message to get roles!"
        self.embed_color = "#0099ff"  # Default blue color
    
    @discord.ui.button(label="Set Title", style=discord.ButtonStyle.secondary)
    async def set_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SetTitleModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Set Description", style=discord.ButtonStyle.secondary)
    async def set_description(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SetDescriptionModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Set Color", style=discord.ButtonStyle.secondary)
    async def set_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SetColorModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Add Role", style=discord.ButtonStyle.primary)
    async def add_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddRoleModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Remove Role", style=discord.ButtonStyle.danger)
    async def remove_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.roles_data:
            await interaction.response.send_message("No roles to remove!", ephemeral=True)
            return
        
        view = RemoveRoleView(self)
        await interaction.response.send_message("Select a role to remove:", view=view, ephemeral=True)
    
    @discord.ui.button(label="Deploy Message", style=discord.ButtonStyle.success)
    async def deploy_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.roles_data:
            await interaction.response.send_message("Add at least one role first!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Create the reaction role message
            # Convert hex color to discord color
            color_int = int(self.embed_color.replace('#', ''), 16)
            embed = discord.Embed(
                title=self.message_title,
                description=self.message_description,
                color=color_int
            )
            
            # Add role information to embed
            role_text = ""
            for role_data in self.roles_data:
                role = interaction.guild.get_role(role_data['role_id'])
                if role:
                    role_text += f"{role_data['emoji']} - {role.mention}\n"
            
            if role_text:
                embed.add_field(name="Available Roles", value=role_text, inline=False)
            
            embed.set_footer(text="React with the corresponding emoji to get/remove roles")
            
            # Send message to the selected channel
            message = await self.channel.send(embed=embed)
            
            # Add reactions
            for role_data in self.roles_data:
                await message.add_reaction(role_data['emoji'])
            
            # Store in database
            repo = ReactionRoleRepository()
            for role_data in self.roles_data:
                await repo.add_reaction_role(
                    guild_id=interaction.guild.id,
                    message_id=message.id,
                    channel_id=self.channel.id,
                    emoji=role_data['emoji'],
                    role_id=role_data['role_id'],
                    exclusive=role_data.get('exclusive', False),
                    embed_color=self.embed_color
                )
            
            success_embed = EmbedFactory.create_success_embed(
                "Reaction Roles Deployed! 🎉",
                f"Successfully created reaction role message in {self.channel.mention}\n\n"
                f"**Message ID:** {message.id}\n"
                f"**Roles Added:** {len(self.roles_data)}\n\n"
                f"Users can now react to get their roles!"
            )
            
            await interaction.followup.send(embed=success_embed)
            
        except Exception as e:
            logger.error(f"Failed to deploy reaction roles: {e}")
            await interaction.followup.send(f"❌ Failed to deploy reaction roles: {str(e)}")
    
    async def update_preview(self, interaction: discord.Interaction):
        """Update the setup preview"""
        embed = EmbedFactory.create_info_embed(
            "Reaction Roles Setup",
            f"**Channel:** {self.channel.mention}\n"
            f"**Title:** {self.message_title}\n"
            f"**Description:** {self.message_description}\n"
            f"**Color:** {self.embed_color}\n\n"
            f"**Roles ({len(self.roles_data)}):**"
        )
        
        if self.roles_data:
            roles_text = ""
            for role_data in self.roles_data[:10]:  # Limit display
                role = interaction.guild.get_role(role_data['role_id'])
                if role:
                    roles_text += f"{role_data['emoji']} - {role.name}\n"
            embed.add_field(name="Role Assignments", value=roles_text or "None", inline=False)
        else:
            embed.add_field(name="Role Assignments", value="None - Add roles using the button below", inline=False)
        
        try:
            # Try to edit the original response first
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.InteractionResponded:
            # If already responded, edit the original response
            await interaction.edit_original_response(embed=embed, view=self)
        except Exception as e:
            # Fallback - send a new message
            await interaction.followup.send(embed=embed, view=self, ephemeral=True)
    
    async def update_preview_silent(self):
        """Update the setup preview without interaction (used after role creation)"""
        # This method is called when we need to update the preview but don't have an interaction
        # The actual update will happen when the user next interacts with the setup view
        pass

class SetTitleModal(discord.ui.Modal, title="Set Message Title"):
    def __init__(self, setup_view):
        super().__init__()
        self.setup_view = setup_view
    
    title_input = discord.ui.TextInput(
        label="Message Title",
        placeholder="React for Roles",
        default="React for Roles",
        max_length=256
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        self.setup_view.message_title = self.title_input.value
        await self.setup_view.update_preview(interaction)

class SetDescriptionModal(discord.ui.Modal, title="Set Message Description"):
    def __init__(self, setup_view):
        super().__init__()
        self.setup_view = setup_view
    
    description_input = discord.ui.TextInput(
        label="Message Description",
        placeholder="React to this message to get roles!",
        default="React to this message to get roles!",
        style=discord.TextStyle.paragraph,
        max_length=1000
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        self.setup_view.message_description = self.description_input.value
        await self.setup_view.update_preview(interaction)

class SetColorModal(discord.ui.Modal, title="Set Embed Color"):
    def __init__(self, setup_view):
        super().__init__()
        self.setup_view = setup_view
    
    color_input = discord.ui.TextInput(
        label="Hex Color",
        placeholder="#FF0000 for red, #00FF00 for green, etc.",
        default="#0099ff",
        max_length=7,
        min_length=7
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        color = self.color_input.value.strip()
        
        # Validate hex color format
        if not color.startswith('#') or len(color) != 7:
            await interaction.response.send_message(
                "❌ Invalid color format. Please use hex format like #FF0000",
                ephemeral=True
            )
            return
        
        try:
            # Validate it's a valid hex color
            int(color[1:], 16)
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid hex color. Please use format like #FF0000",
                ephemeral=True
            )
            return
        
        self.setup_view.embed_color = color
        await self.setup_view.update_preview(interaction)

class AddRoleModal(discord.ui.Modal, title="Add Role Assignment"):
    def __init__(self, setup_view):
        super().__init__()
        self.setup_view = setup_view
    
    emoji = discord.ui.TextInput(
        label="Emoji",
        placeholder="👍 or :custom_emoji:",
        max_length=100
    )
    
    role_input = discord.ui.TextInput(
        label="Role",
        placeholder="@Role, role ID, or new role name to create",
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Parse role
        role = None
        role_text = self.role_input.value.strip()
        
        if role_text.startswith('<@&') and role_text.endswith('>'):
            # Role mention
            role_id = int(role_text[3:-1])
            role = interaction.guild.get_role(role_id)
        elif role_text.startswith('@'):
            # Role name
            role_name = role_text[1:]
            role = discord.utils.get(interaction.guild.roles, name=role_name)
        else:
            # Try as role ID
            try:
                role_id = int(role_text)
                role = interaction.guild.get_role(role_id)
            except ValueError:
                # Try as role name
                role = discord.utils.get(interaction.guild.roles, name=role_text)
        
        if not role:
            # Role doesn't exist, offer to create it
            create_view = CreateRoleConfirmView(self.setup_view, role_text, self.emoji.value.strip())
            await interaction.response.send_message(
                f"❌ Role '{role_text}' not found. Would you like to create it?",
                view=create_view,
                ephemeral=True
            )
            return
        
        # Check if emoji or role already exists
        emoji_text = self.emoji.value.strip()
        for existing in self.setup_view.roles_data:
            if existing['emoji'] == emoji_text:
                await interaction.response.send_message(
                    "❌ That emoji is already used for another role.",
                    ephemeral=True
                )
                return
            if existing['role_id'] == role.id:
                await interaction.response.send_message(
                    "❌ That role is already assigned to another emoji.",
                    ephemeral=True
                )
                return
        
        # Add role data
        self.setup_view.roles_data.append({
            'emoji': emoji_text,
            'role_id': role.id,
            'exclusive': False
        })
        
        await self.setup_view.update_preview(interaction)

class CreateRoleConfirmView(discord.ui.View):
    def __init__(self, setup_view, role_name, emoji):
        super().__init__(timeout=60)
        self.setup_view = setup_view
        self.role_name = role_name.lstrip('@')  # Remove @ if present
        self.emoji = emoji
    
    @discord.ui.button(label="Create Role", style=discord.ButtonStyle.success, emoji="✅")
    async def create_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Create the role
            new_role = await interaction.guild.create_role(
                name=self.role_name,
                reason=f"Created by {interaction.user} for reaction roles"
            )
            
            # Check if emoji or role already exists in setup
            for existing in self.setup_view.roles_data:
                if existing['emoji'] == self.emoji:
                    await interaction.response.send_message(
                        "❌ That emoji is already used for another role.",
                        ephemeral=True
                    )
                    return
                if existing['role_id'] == new_role.id:
                    await interaction.response.send_message(
                        "❌ That role is already assigned to another emoji.",
                        ephemeral=True
                    )
                    return
            
            # Add role data
            self.setup_view.roles_data.append({
                'emoji': self.emoji,
                'role_id': new_role.id,
                'exclusive': False
            })
            
            await interaction.response.send_message(
                f"✅ Role '{new_role.name}' created and added to reaction roles!",
                ephemeral=True
            )
            
            # Update the preview in the setup view
            await self.setup_view.update_preview_silent()
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to create roles. Please check my permissions.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"❌ Failed to create role: {str(e)}",
                ephemeral=True
            )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Role creation cancelled.", ephemeral=True)

class RemoveRoleView(discord.ui.View):
    def __init__(self, setup_view):
        super().__init__(timeout=60)
        self.setup_view = setup_view
        
        # Create select menu with current roles
        options = []
        for i, role_data in enumerate(setup_view.roles_data[:25]):  # Discord limit
            role = setup_view.channel.guild.get_role(role_data['role_id'])
            if role:
                options.append(discord.SelectOption(
                    label=f"{role_data['emoji']} {role.name}",
                    value=str(i),
                    description=f"Role ID: {role.id}"
                ))
        
        if options:
            self.role_select = discord.ui.Select(
                placeholder="Select role to remove",
                options=options
            )
            self.role_select.callback = self.remove_role_callback
            self.add_item(self.role_select)
    
    async def remove_role_callback(self, interaction: discord.Interaction):
        index = int(self.role_select.values[0])
        removed_role = self.setup_view.roles_data.pop(index)
        
        await interaction.response.send_message(
            f"✅ Removed {removed_role['emoji']} role assignment.",
            ephemeral=True
        )
        
        # Update the main view
        await self.setup_view.update_preview(interaction)

class ReactionRoles(commands.Cog):
    """Reaction role management system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.repo = ReactionRoleRepository()
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle reaction additions"""
        if payload.user_id == self.bot.user.id:
            return
        
        # Get reaction role mapping
        emoji_str = str(payload.emoji)
        mapping = await self.repo.get_reaction_role_by_message_emoji(
            payload.message_id, emoji_str
        )
        
        if not mapping:
            return
        
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        
        member = guild.get_member(payload.user_id)
        role = guild.get_role(mapping['role_id'])
        
        if not member or not role:
            return
        
        try:
            if role not in member.roles:
                await member.add_roles(role, reason="Reaction role")
                logger.info(f"Added role {role.name} to {member} via reaction")
        except discord.Forbidden:
            logger.warning(f"Missing permissions to add role {role.name} to {member}")
        except Exception as e:
            logger.error(f"Failed to add reaction role: {e}")
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle reaction removals"""
        if payload.user_id == self.bot.user.id:
            return
        
        # Get reaction role mapping
        emoji_str = str(payload.emoji)
        mapping = await self.repo.get_reaction_role_by_message_emoji(
            payload.message_id, emoji_str
        )
        
        if not mapping:
            return
        
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        
        member = guild.get_member(payload.user_id)
        role = guild.get_role(mapping['role_id'])
        
        if not member or not role:
            return
        
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Reaction role removed")
                logger.info(f"Removed role {role.name} from {member} via reaction removal")
        except discord.Forbidden:
            logger.warning(f"Missing permissions to remove role {role.name} from {member}")
        except Exception as e:
            logger.error(f"Failed to remove reaction role: {e}")
    
    @app_commands.command(name="reaction-roles-setup", description="Set up reaction roles for your server")
    @app_commands.default_permissions(administrator=True)
    async def setup_reaction_roles(self, interaction: discord.Interaction):
        """Set up reaction roles with channel selection"""
        
        async def channel_selected(channel_interaction: discord.Interaction, channel: discord.TextChannel):
            # Start the setup process
            setup_view = ReactionRoleSetupView(channel)
            
            embed = EmbedFactory.create_info_embed(
                "Reaction Roles Setup",
                f"**Channel:** {channel.mention}\n"
                f"**Title:** {setup_view.message_title}\n"
                f"**Description:** {setup_view.message_description}\n"
                f"**Color:** {setup_view.embed_color}\n\n"
                f"**Roles ({len(setup_view.roles_data)}):**"
            )
            embed.add_field(name="Role Assignments", value="None - Add roles using the button below", inline=False)
            
            await channel_interaction.response.edit_message(embed=embed, view=setup_view)
        
        # Show channel selection dropdown
        embed = EmbedFactory.create_info_embed(
            "Reaction Roles Setup",
            "Choose a channel where the reaction role message will be posted.\n\n"
            "Users will react to the message in this channel to get roles."
        )
        
        channel_view = ReactionRoleChannelSelectView(channel_selected)
        channel_view.setup_for_guild(interaction.guild)
        
        await interaction.response.send_message(embed=embed, view=channel_view, ephemeral=True)
    
    @app_commands.command(name="reaction-roles-list", description="List all reaction role messages")
    @app_commands.default_permissions(administrator=True)
    async def list_reaction_roles(self, interaction: discord.Interaction):
        """List all reaction role messages in the server"""
        reaction_roles = await self.repo.get_reaction_roles(interaction.guild.id)
        
        if not reaction_roles:
            await interaction.response.send_message("No reaction role messages found.", ephemeral=True)
            return
        
        # Group by message
        messages = {}
        for rr in reaction_roles:
            msg_id = rr['message_id']
            if msg_id not in messages:
                messages[msg_id] = {
                    'channel_id': rr['channel_id'],
                    'roles': []
                }
            messages[msg_id]['roles'].append(rr)
        
        embed = EmbedFactory.create_info_embed(
            "Reaction Role Messages",
            f"Found {len(messages)} reaction role messages"
        )
        
        for msg_id, data in list(messages.items())[:10]:  # Limit to 10 messages
            channel = interaction.guild.get_channel(data['channel_id'])
            channel_name = channel.mention if channel else f"<#{data['channel_id']}>"
            
            roles_text = ""
            for role_data in data['roles'][:5]:  # Limit to 5 roles per message
                role = interaction.guild.get_role(role_data['role_id'])
                role_name = role.name if role else f"<@&{role_data['role_id']}>"
                roles_text += f"{role_data['emoji']} {role_name}\n"
            
            embed.add_field(
                name=f"Message {msg_id}",
                value=f"**Channel:** {channel_name}\n**Roles:**\n{roles_text}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))