"""User model tests."""

# run these tests like:
#
#    python -m unittest test_user_model.py


import os
from unittest import TestCase

from models import db, User, Message, Follows

# BEFORE we import our app, let's set an environmental variable
# to use a different database for tests (we need to do this
# before we import our app, since that will have already
# connected to the database

os.environ['DATABASE_URL'] = "postgresql:///warbler-test"

# Now we can import app

from app import app

# Create our tables (we do this here, so we only create the tables
# once for all tests --- in each test, we'll delete the data
# and create fresh new clean test data

db.create_all()


class UserModelTestCase(TestCase):
    """Test views for messages."""

    def setUp(self):
        """Create test client, add sample data."""

        User.query.delete()
        Message.query.delete()
        Follows.query.delete()

        self.client = app.test_client()

        u1 = User(
            email="test1@test.com",
            username="testuser1",
            password="HASHED_PASSWORD"
        )
        
        u2 = User(
            email="test2@test.com",
            username="testuser2",
            password="HASHED_PASSWORD"
        )
        self.u1_id = u1.id
        self.u2_id = u2.id
        print(self.u1_id, 'Printing user id')
        print(u1, 'Printing user')
        db.session.add_all([u1,u2])
        db.session.commit()

    def test_user_model(self):
        """Does basic model work?"""
        u1 = User.query.get(self.u1_id)
        # User should have no messages & no followers
        self.assertEqual(len(u1.messages), 0)
        self.assertEqual(len(u1.followers), 0)

    def test_user_repr(self):
        """Test user repr"""

        u1 = User.query.get(self.u1_id)
        

        # User should see the repr

        self.assertEqual( f"<User #{u1.id}: {u1.username}, {u1.email}>",
                          u1.__repr__() )
      

        

    
