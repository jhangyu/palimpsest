# backend/core/crypto.py
"""AES-GCM encryption/decryption helpers — ai_tokens vault removed (#24).

All token encryption functions were tied to the deprecated user_ai_tokens flow
and have been removed. If vault encryption is needed in future, reintroduce
encrypt_token / decrypt_token with PBKDF2-HMAC-SHA256 + AES-GCM-256.
"""
