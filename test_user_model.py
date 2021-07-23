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

db.drop_all() # added drop_all
db.create_all()

U1 = {
    "email" : "test1@test.com",
    "username" : "testuser1",
    "password" : "HASHED_PASSWORD"
}

U2 = { 
    "email" : "test2@test.com",
    "username" : "testuser2",
    "password" : "HASHED_PASSWORD"
}

class UserModelTestCase(TestCase):
    """Test views for messages."""

    def setUp(self):
        """Create test client, add sample data."""

        User.query.delete()
        Message.query.delete()
        Follows.query.delete()

        self.client = app.test_client()

        u1 = User(**U1)
        u2 = User(**U2)

        db.session.add_all([u1, u2])
        db.session.commit()

        self.u1_id = u1.id
        self.u2_id = u2.id

        # self.u1 = u1
        # self.u2 = u2


    def tearDown(self):
        """Clean up fouled transactions."""

        db.session.rollback()


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
      
    
    def test_user_is_following(self):
        """Make sure is_following successfully detects when user1 is following 
        user2"""

        u1 = User.query.get(self.u1_id)
        u2 = User.query.get(self.u2_id)

        u1.following.append(u2)
        db.session.commit()

        result = u1.is_following(u2)

        self.assertTrue(result)

    def test_user_is_not_following(self):
        """Make sure is_following successfully detects when user1 is not following 
        user2"""

        u1 = User.query.get(self.u1_id)
        u2 = User.query.get(self.u2_id)

        u1.following.append(u2)
        db.session.commit()

        u1.following.remove(u2)
        db.session.commit()

        result = u1.is_following(u2)

        self.assertFalse(result)
        

    
