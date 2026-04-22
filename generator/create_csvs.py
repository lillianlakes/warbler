"""Generate realistic CSV seed data for Warbler.

This version avoids brittle external APIs and creates modern-looking content,
including recent timestamps and richer user bios.
"""

import csv
import random
from itertools import permutations

from helpers import get_random_datetime

MAX_WARBLER_LENGTH = 140

USERS_CSV_HEADERS = ['email', 'username', 'image_url', 'password', 'bio', 'header_image_url', 'location']
MESSAGES_CSV_HEADERS = ['text', 'timestamp', 'user_id']
FOLLOWS_CSV_HEADERS = ['user_being_followed_id', 'user_following_id']

NUM_USERS = 300
NUM_MESSAGES = 1000
NUM_FOLLWERS = 5000

# Generate random profile image URLs to use for users

image_urls = [
    f"https://randomuser.me/api/portraits/{kind}/{i}.jpg"
    for kind, count in [("men", 100), ("women", 100)]
    for i in range(count)
]

# Generate random header image URLs to use for users

header_image_urls = [
    f"https://picsum.photos/id/{img_id}/1200/400"
    for img_id in [
        10, 11, 14, 15, 16, 18, 21, 24, 28, 29,
        34, 35, 36, 42, 43, 50, 57, 64, 72, 79,
        82, 87, 92, 100, 102, 106, 110, 119, 127, 133,
    ]
]

first_names = [
    "Avery", "Jordan", "Taylor", "Riley", "Casey", "Morgan", "Jamie",
    "Drew", "Quinn", "Skyler", "Parker", "Alex", "Harper", "Rowan",
    "Cameron", "Emerson", "Reese", "Sage", "Finley", "Kendall",
]

last_names = [
    "Nguyen", "Patel", "Garcia", "Kim", "Lopez", "Hernandez", "Singh",
    "Brown", "Wilson", "Wright", "Davis", "Johnson", "Martin", "Lee",
    "Anderson", "Thomas", "Jackson", "Martinez", "Clark", "Lewis",
]

cities = [
    "San Francisco", "New York", "Austin", "Seattle", "Chicago",
    "Denver", "Atlanta", "Los Angeles", "Toronto", "London",
    "Berlin", "Lisbon", "Mumbai", "Singapore", "Sydney",
]

roles = [
    "Product designer", "Backend engineer", "Data analyst", "Founder",
    "Marketing lead", "DevRel", "Mobile developer", "ML engineer",
    "Student", "Teacher", "Content creator", "Photographer",
]

interests = [
    "coffee", "running", "hiking", "startups", "books", "AI",
    "movies", "gaming", "travel", "music", "cycling", "cooking",
    "design", "photography", "open source",
]

message_starters = [
    "Just shipped", "Hot take:", "Learning", "Today I learned",
    "Anyone else", "Weekend plan:", "Small win:", "PSA:",
    "Trying out", "Can we normalize", "Reminder:", "Quick thread:",
]

message_topics = [
    "a cleaner API pattern", "meal prep for busy weeks", "better onboarding",
    "how to stay focused", "using SQL window functions", "a side project",
    "testing Flask apps", "designing for accessibility", "debugging auth bugs",
    "keeping meetings short", "shipping without burnout", "writing docs first",
]

message_endings = [
    "Thoughts?", "Curious what worked for you.", "Would love recommendations.",
    "This saved me hours.", "Back to building.", "Happy to share notes.",
    "Let me know if you want details.", "Still iterating.",
]


def make_username(first_name, last_name, index):
    base = f"{first_name}{last_name}".lower()
    return f"{base}{index}"


def make_email(username):
    domains = ["gmail.com", "outlook.com", "proton.me", "yahoo.com"]
    return f"{username}@{random.choice(domains)}"


def make_bio():
    first_interest, second_interest = random.sample(interests, 2)
    return (
        f"{random.choice(roles)} in {random.choice(cities)}. "
        f"Into {first_interest} and {second_interest}."
    )


def make_message():
    text = (
        f"{random.choice(message_starters)} {random.choice(message_topics)}. "
        f"{random.choice(message_endings)}"
    )
    return text[:MAX_WARBLER_LENGTH]

with open('generator/users.csv', 'w') as users_csv:
    users_writer = csv.DictWriter(users_csv, fieldnames=USERS_CSV_HEADERS)
    users_writer.writeheader()

    for i in range(1, NUM_USERS + 1):
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        username = make_username(first_name, last_name, i)
        users_writer.writerow(dict(
            email=make_email(username),
            username=username,
            image_url=random.choice(image_urls),
            password='$2b$12$Q1PUFjhN/AWRQ21LbGYvjeLpZZB6lfZ1BPwifHALGO6oIbyC3CmJe',
            bio=make_bio(),
            header_image_url=random.choice(header_image_urls),
            location=random.choice(cities)
        ))

with open('generator/messages.csv', 'w') as messages_csv:
    messages_writer = csv.DictWriter(messages_csv, fieldnames=MESSAGES_CSV_HEADERS)
    messages_writer.writeheader()

    for i in range(NUM_MESSAGES):
        messages_writer.writerow(dict(
            text=make_message(),
            timestamp=get_random_datetime(year_gap=1),
            user_id=random.randint(1, NUM_USERS)
        ))

# Generate follows.csv from random pairings of users

with open('generator/follows.csv', 'w') as follows_csv:
    all_pairs = list(permutations(range(1, NUM_USERS + 1), 2))

    users_writer = csv.DictWriter(follows_csv, fieldnames=FOLLOWS_CSV_HEADERS)
    users_writer.writeheader()

    for followed_user, follower in random.sample(all_pairs, NUM_FOLLWERS):
        users_writer.writerow(dict(user_being_followed_id=followed_user, user_following_id=follower))
