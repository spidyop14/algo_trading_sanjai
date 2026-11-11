import os
from cryptography.fernet import Fernet, InvalidToken
from broker.exceptions import BrokerError

def _cipher():
    key = os.getenv("ORBIT_TOKEN_ENCRYPTION_KEY")
    if not key: raise BrokerError("Token encryption is not configured. Set ORBIT_TOKEN_ENCRYPTION_KEY on the server.")
    try: return Fernet(key.encode())
    except (ValueError, TypeError) as error: raise BrokerError("Token encryption key is invalid") from error
def encrypt_token(token: str) -> str: return _cipher().encrypt(token.encode()).decode()
def decrypt_token(token: str) -> str:
    try: return _cipher().decrypt(token.encode()).decode()
    except InvalidToken as error: raise BrokerError("Stored broker session cannot be decrypted") from error
