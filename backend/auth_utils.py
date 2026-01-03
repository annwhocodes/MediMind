
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional

import hashlib

# Configuration
SECRET_KEY = "your-secret-key-keep-it-secret" # Change this for production!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    # Pre-hash with SHA256 to bypass bcrypt's 72-byte limit
    # SHA256 hexdigest is 64 characters, which fits safely within bcrypt's limit
    secure_password = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
    return pwd_context.verify(secure_password, hashed_password)

def get_password_hash(password):
    # Pre-hash with SHA256
    secure_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    return pwd_context.hash(secure_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
