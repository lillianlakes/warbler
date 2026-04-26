"""Bootstrap an operator user safely.

Usage:
    python scripts/bootstrap_user.py --username admin --email admin@example.com --password strongpassword
"""

import argparse
import sys

from app import app
from models import User, bcrypt, db


def parse_args():
    parser = argparse.ArgumentParser(description="Create/update an initial operator user")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--image-url", default="")
    return parser.parse_args()


def main():
    args = parse_args()

    if len(args.password) < 8:
        print("Password must be at least 8 characters long.")
        return 1

    with app.app_context():
        existing_user = User.query.filter(
            (User.username == args.username) | (User.email == args.email)
        ).first()

        if existing_user:
            existing_user.username = args.username
            existing_user.email = args.email
            existing_user.password = bcrypt.generate_password_hash(args.password).decode("UTF-8")
            if args.image_url:
                existing_user.image_url = args.image_url
            db.session.commit()
            print(f"Updated existing operator user: @{existing_user.username}")
            return 0

        user = User.signup(
            username=args.username,
            email=args.email,
            password=args.password,
            image_url=args.image_url,
        )
        db.session.commit()
        print(f"Created operator user: @{user.username}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
