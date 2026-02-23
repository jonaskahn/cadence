#!/usr/bin/env python3
"""Bootstrap Cadence with a default sys_admin user and issue an initial token.

Creates a sys_admin user (no org membership) and prints a ready-to-use JWT.

Usage:
    poetry run python scripts/bootstrap.py
    poetry run python scripts/bootstrap.py --username alice --email alice@example.com

    # Create an additional sys_admin (no org creation):
    poetry run python scripts/bootstrap.py --add-sys-admin --username bob

Options:
    --user-id       Admin user ID     (default: auto-generated UUID)
    --username      Admin username    (default: admin)
    --email         Admin email       (default: admin@localhost)
    --password      Admin password    (default: auto-generated)
    --force         Overwrite existing user without prompting
    --add-sys-admin Create a new sys_admin user (skips schema creation)
"""

import argparse
import asyncio
import hashlib
import os
import secrets
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt.

    Format: pbkdf2:sha256:260000:<hex-salt>:<hex-digest>
    """
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return f"pbkdf2:sha256:260000:{salt.hex()}:{digest.hex()}"


def _generate_password() -> str:
    """Generate a random 20-character URL-safe password."""
    return secrets.token_urlsafe(15)


def _box(lines: list[str], title: str = "") -> str:
    """Return a simple ASCII box around the given lines."""
    width = max(len(line) for line in lines + [title]) + 25
    border = "─" * width
    out = [f"╔{border}╗"]
    if title:
        pad = width - len(title) - 2
        out.append(f"║  {title}{' ' * pad}║")
        out.append(f"╠{border}╣")
    for line in lines:
        pad = width - len(line) - 2
        out.append(f"║  {line}{' ' * pad}║")
    out.append(f"╚{border}╝")
    return "\n".join(out)


async def _create_sys_admin_user(
    *,
    client,
    user_id: str,
    username: str,
    email: str,
    password: str,
    force: bool,
    step_num: int,
) -> str:
    """Create (or reuse) a sys_admin user.

    Returns:
        Final user_id
    """
    from sqlalchemy import select

    from cadence.infrastructure.persistence.postgresql.models import User

    print(f"{step_num}. Creating sys_admin user...")
    password_hash = _hash_password(password)

    async with client.session() as session:
        existing_user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()

        existing_by_username = (
            await session.execute(
                select(User).where(User.username == username, ~User.is_deleted)
            )
        ).scalar_one_or_none()

        target_user = existing_user or existing_by_username
        if target_user:
            if not force:
                ans = input(
                    f"   User '{username}' already exists. Update password? (Y/n): "
                )
                if ans.strip().lower() == "n":
                    print("   Skipping user update.")
                    return str(target_user.id)
                else:
                    target_user.password_hash = password_hash
                    await session.commit()
                    print(f"   ✓ Password updated for existing user: {username}")
                    return str(target_user.id)
            else:
                target_user.password_hash = password_hash
                await session.commit()
                print(f"   ✓ Using existing user: {username}")
                return str(target_user.id)
        else:
            new_user = User(
                id=user_id,
                username=username,
                email=email,
                is_sys_admin=True,
                password_hash=password_hash,
            )
            session.add(new_user)
            await session.commit()
            print(f"   ✓ sys_admin user created: {username} ({email})")
            return user_id


async def _issue_token(
    *,
    redis_client,
    settings,
    user_id: str,
    step_num: int,
) -> str:
    """Create a Redis session and return a signed JWT for the given user.

    Returns:
        Signed JWT string
    """
    from datetime import datetime, timedelta, timezone

    import jwt

    from cadence.repository.session_store_repository import SessionStoreRepository

    print(f"{step_num}. Issuing session token...")

    ttl_seconds = settings.access_token_expire_minutes * 60
    store = SessionStoreRepository(
        redis_client.get_client(), default_ttl_seconds=ttl_seconds
    )

    session = await store.create_session(
        user_id=user_id,
        is_sys_admin=True,
        org_admin=[],
        org_user=[],
        ttl_seconds=ttl_seconds,
    )

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "jti": session.jti,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    print("   ✓ Token issued")
    return token


def _print_summary(
    *,
    user_id: str,
    username: str,
    email: str,
    password: str,
    token: str,
) -> None:
    """Print credentials and token summary box."""
    summary = [
        f"User ID   : {user_id}",
        f"Username  : {username}",
        f"Email     : {email}",
        "Role      : sys_admin",
        f"Password  : {password}",
        "Bearer    : "
        "(Store credentials securely — they cannot be recovered after this session)",
    ]
    print()
    print(_box(summary, title="Credentials"))
    print(f"{token}")
    print()


async def bootstrap(
    user_id: str,
    username: str,
    email: str,
    password: str,
    force: bool,
) -> None:
    """Bootstrap a new Cadence installation with a sys_admin user and initial token."""
    from cadence.config.app_settings import AppSettings
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient
    from cadence.infrastructure.persistence.postgresql.models import BaseModel
    from cadence.infrastructure.persistence.redis.client import RedisClient

    settings = AppSettings()
    pg_client = PostgreSQLClient(settings.postgres_url)
    redis_client = RedisClient(settings.redis_url, settings.redis_default_db)

    print("=== Cadence Bootstrap ===\n")
    db_host = settings.postgres_url.split("@")[-1]
    print(f"  Database : {db_host}")
    print(f"  Username : {username}")
    print()

    try:
        print("1. Connecting to PostgreSQL...")
        await pg_client.connect()
        print("   ✓ Connected")

        print("2. Ensuring schema exists...")
        async with pg_client.engine.begin() as conn:
            await conn.run_sync(BaseModel.metadata.create_all)
        print("   ✓ Schema ready")

        final_user_id = await _create_sys_admin_user(
            client=pg_client,
            user_id=user_id,
            username=username,
            email=email,
            password=password,
            force=force,
            step_num=3,
        )

        print("4. Connecting to Redis...")
        await redis_client.connect()
        print("   ✓ Connected")

        token = await _issue_token(
            redis_client=redis_client,
            settings=settings,
            user_id=final_user_id,
            step_num=5,
        )

        _print_summary(
            user_id=final_user_id,
            username=username,
            email=email,
            password=password,
            token=token,
        )

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        await pg_client.disconnect()
        await redis_client.disconnect()


async def add_sys_admin(
    user_id: str,
    username: str,
    email: str,
    password: str,
    force: bool,
) -> None:
    """Create a new sys_admin user and issue an initial token."""
    from cadence.config.app_settings import AppSettings
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient
    from cadence.infrastructure.persistence.redis.client import RedisClient

    settings = AppSettings()
    pg_client = PostgreSQLClient(settings.postgres_url)
    redis_client = RedisClient(settings.redis_url, settings.redis_default_db)

    print("=== Cadence Add sys_admin ===\n")
    db_host = settings.postgres_url.split("@")[-1]
    print(f"  Database : {db_host}")
    print(f"  Username : {username}")
    print()

    try:
        print("1. Connecting to PostgreSQL...")
        await pg_client.connect()
        print("   ✓ Connected")

        final_user_id = await _create_sys_admin_user(
            client=pg_client,
            user_id=user_id,
            username=username,
            email=email,
            password=password,
            force=force,
            step_num=2,
        )

        print("3. Connecting to Redis...")
        await redis_client.connect()
        print("   ✓ Connected")

        token = await _issue_token(
            redis_client=redis_client,
            settings=settings,
            user_id=final_user_id,
            step_num=4,
        )

        _print_summary(
            user_id=final_user_id,
            username=username,
            email=email,
            password=password,
            token=token,
        )

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        await pg_client.disconnect()
        await redis_client.disconnect()


def main() -> None:
    """Entry point for the bootstrap CLI."""
    parser = argparse.ArgumentParser(
        description="Bootstrap Cadence with a sys_admin user and initial token"
    )
    parser.add_argument(
        "--user-id", default=str(uuid4()), help="Admin user ID (default: random UUID)"
    )
    parser.add_argument("--username", default="admin", help="Admin username")
    parser.add_argument("--email", default="admin@localhost", help="Admin email")
    parser.add_argument(
        "--password",
        default=None,
        help="Admin password (default: auto-generated)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing user without prompting",
    )
    parser.add_argument(
        "--add-sys-admin",
        action="store_true",
        help="Create a new sys_admin user (skips schema creation)",
    )
    args = parser.parse_args()

    password = args.password or _generate_password()

    if args.add_sys_admin:
        asyncio.run(
            add_sys_admin(
                user_id=args.user_id,
                username=args.username,
                email=args.email,
                password=password,
                force=args.force,
            )
        )
    else:
        asyncio.run(
            bootstrap(
                user_id=args.user_id,
                username=args.username,
                email=args.email,
                password=password,
                force=args.force,
            )
        )


if __name__ == "__main__":
    main()
