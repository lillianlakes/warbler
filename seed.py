"""Seed database with sample data from CSV Files."""

import os
from csv import DictReader
from pathlib import Path

from app import db
from models import User, Message, Follows

BASE_DIR = Path(__file__).resolve().parent
GENERATOR_DIR = BASE_DIR / 'generator'
ENV = os.getenv('FLASK_ENV', 'development').lower()

if ENV != 'development' and os.getenv('WARBLER_SEED_CONFIRM') != 'YES':
    raise RuntimeError(
        "Refusing to run destructive seed outside development. "
        "Set WARBLER_SEED_CONFIRM=YES to proceed."
    )

db.drop_all()
db.create_all()

with open(GENERATOR_DIR / 'users.csv', encoding='utf-8') as users:
    db.session.bulk_insert_mappings(User, DictReader(users))

with open(GENERATOR_DIR / 'messages.csv', encoding='utf-8') as messages:
    db.session.bulk_insert_mappings(Message, DictReader(messages))

with open(GENERATOR_DIR / 'follows.csv', encoding='utf-8') as follows:
    db.session.bulk_insert_mappings(Follows, DictReader(follows))

db.session.commit()

