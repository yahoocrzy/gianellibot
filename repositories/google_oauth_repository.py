from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
from database.models import async_session, GoogleOAuthState, GoogleCredential
from typing import Optional, Tuple
from datetime import datetime, timedelta
import uuid
import json
from loguru import logger
from services.security import encrypt_token, decrypt_token

class GoogleOAuthRepository:
    """Repository for Google OAuth operations"""
    
    @staticmethod
    async def create_oauth_state(guild_id: str, user_id: str) -> Tuple[str, str]:
        """Create OAuth2 state for security
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            
        Returns:
            Tuple of (state, auth_url)
        """
        from services.google_calendar_api import GoogleCalendarAPI
        import os
        
        state = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        async with async_session() as session:
            oauth_state = GoogleOAuthState(
                state=state,
                guild_id=guild_id,
                user_id=user_id,
                expires_at=expires_at
            )
            session.add(oauth_state)
            await session.commit()
        
        # Create auth URL
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:10000/auth/google/callback")
        flow = GoogleCalendarAPI.create_auth_flow(redirect_uri)
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'
        )
        
        return state, auth_url
    
    @staticmethod
    async def validate_oauth_state(state: str) -> Optional[Tuple[str, str]]:
        """Validate OAuth2 state and return guild_id, user_id if valid
        
        Args:
            state: OAuth2 state to validate
            
        Returns:
            Tuple of (guild_id, user_id) or None if invalid
        """
        async with async_session() as session:
            result = await session.execute(
                select(GoogleOAuthState).where(
                    and_(
                        GoogleOAuthState.state == state,
                        GoogleOAuthState.expires_at > datetime.utcnow()
                    )
                )
            )
            oauth_state = result.scalar_one_or_none()
            
            if oauth_state:
                # Delete the state after use
                await session.delete(oauth_state)
                await session.commit()
                return oauth_state.guild_id, oauth_state.user_id
            
            return None
    
    @staticmethod
    async def cleanup_expired_states():
        """Clean up expired OAuth states"""
        async with async_session() as session:
            await session.execute(
                delete(GoogleOAuthState).where(
                    GoogleOAuthState.expires_at <= datetime.utcnow()
                )
            )
            await session.commit()
    
    @staticmethod
    async def save_credentials(
        guild_id: str,
        user_id: str,
        email: str,
        credentials_json: str
    ) -> GoogleCredential:
        """Save Google credentials for a user
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            email: Google email address
            credentials_json: JSON credentials from Google
            
        Returns:
            Saved GoogleCredential object
        """
        encrypted_creds = encrypt_token(credentials_json)
        
        async with async_session() as session:
            # Check if credentials already exist
            result = await session.execute(
                select(GoogleCredential).where(
                    and_(
                        GoogleCredential.guild_id == guild_id,
                        GoogleCredential.user_id == user_id
                    )
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing credentials
                existing.email = email
                existing.credentials_encrypted = encrypted_creds
                existing.updated_at = datetime.utcnow()
                await session.commit()
                return existing
            else:
                # Create new credentials
                # Check if this should be default
                count_result = await session.execute(
                    select(GoogleCredential).where(
                        GoogleCredential.guild_id == guild_id
                    )
                )
                is_first = len(count_result.scalars().all()) == 0
                
                new_cred = GoogleCredential(
                    guild_id=guild_id,
                    user_id=user_id,
                    email=email,
                    credentials_encrypted=encrypted_creds,
                    is_default=is_first
                )
                session.add(new_cred)
                await session.commit()
                await session.refresh(new_cred)
                return new_cred
    
    @staticmethod
    async def get_credentials(guild_id: str, user_id: str = None) -> Optional[GoogleCredential]:
        """Get credentials for a guild/user
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID (optional, gets default if not provided)
            
        Returns:
            GoogleCredential object or None
        """
        async with async_session() as session:
            if user_id:
                # Get specific user's credentials
                result = await session.execute(
                    select(GoogleCredential).where(
                        and_(
                            GoogleCredential.guild_id == guild_id,
                            GoogleCredential.user_id == user_id
                        )
                    )
                )
            else:
                # Get default credentials
                result = await session.execute(
                    select(GoogleCredential).where(
                        and_(
                            GoogleCredential.guild_id == guild_id,
                            GoogleCredential.is_default == True
                        )
                    )
                )
            
            return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_credentials(guild_id: str) -> list[GoogleCredential]:
        """Get all credentials for a guild
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            List of GoogleCredential objects
        """
        async with async_session() as session:
            result = await session.execute(
                select(GoogleCredential).where(
                    GoogleCredential.guild_id == guild_id
                )
            )
            return result.scalars().all()
    
    @staticmethod
    async def set_default_credentials(guild_id: str, user_id: str) -> bool:
        """Set a user's credentials as default for the guild
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            
        Returns:
            True if successful, False otherwise
        """
        async with async_session() as session:
            # Update all to not default
            result = await session.execute(
                select(GoogleCredential).where(
                    GoogleCredential.guild_id == guild_id
                )
            )
            for cred in result.scalars():
                cred.is_default = False
            
            # Set the specified one as default
            result = await session.execute(
                select(GoogleCredential).where(
                    and_(
                        GoogleCredential.guild_id == guild_id,
                        GoogleCredential.user_id == user_id
                    )
                )
            )
            cred = result.scalar_one_or_none()
            
            if cred:
                cred.is_default = True
                await session.commit()
                return True
            
            return False
    
    @staticmethod
    async def remove_credentials(guild_id: str, user_id: str) -> bool:
        """Remove a user's credentials
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            
        Returns:
            True if removed, False if not found
        """
        async with async_session() as session:
            result = await session.execute(
                select(GoogleCredential).where(
                    and_(
                        GoogleCredential.guild_id == guild_id,
                        GoogleCredential.user_id == user_id
                    )
                )
            )
            cred = result.scalar_one_or_none()
            
            if cred:
                await session.delete(cred)
                await session.commit()
                return True
            
            return False
    
    @staticmethod
    def decrypt_credentials(encrypted_creds: str) -> Optional[str]:
        """Decrypt stored credentials
        
        Args:
            encrypted_creds: Encrypted credentials
            
        Returns:
            Decrypted JSON credentials or None
        """
        try:
            return decrypt_token(encrypted_creds)
        except Exception as e:
            logger.error(f"Failed to decrypt credentials: {e}")
            return None