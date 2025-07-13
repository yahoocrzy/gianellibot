from cryptography.fernet import Fernet
from typing import Optional
import os
from loguru import logger

class SecurityService:
    def __init__(self):
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            logger.warning("No encryption key found, generating new one")
            key = Fernet.generate_key().decode()
            logger.info(f"Generated encryption key: {key}")
        self.fernet = Fernet(key.encode() if isinstance(key, str) else key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data"""
        try:
            encrypted = self.fernet.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        try:
            decrypted = self.fernet.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise

security_service = SecurityService()