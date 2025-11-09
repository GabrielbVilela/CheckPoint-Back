from passlib.context import CryptContext

# Single shared password hashing context to keep hashing consistent across modules
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check if the provided plaintext password matches the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using the configured context."""
    return pwd_context.hash(password)
