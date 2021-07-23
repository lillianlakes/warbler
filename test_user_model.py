"""User model tests."""

# run these tests like:
#
#    python -m unittest test_user_model.py


from logging import error
import os
from unittest import TestCase
from flask_bcrypt import Bcrypt
from models import db, User, Message, Follows
from psycopg2.errors import UniqueViolation
from sqlalchemy import exc
import pdb

bcrypt = Bcrypt()

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
    "password" : "HASHED_PASSWORD",
    "image_url": ""
}

U2 = { 
    "email" : "test2@test.com",
    "username" : "testuser2",
    "password" : "HASHED_PASSWORD",
    "image_url": ""
}

class UserModelTestCase(TestCase):
    """Test views for messages."""

    def setUp(self):
        """Create test client, add sample data."""

        User.query.delete()
        Message.query.delete()
        Follows.query.delete()

        self.client = app.test_client()

        u1 = User.signup(**U1)
        u2 = User.signup(**U2)

        db.session.add_all([u1, u2])
        db.session.commit()

        self.u1_id = u1.id
        self.u2_id = u2.id



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
        
    def test_user_is_followed_by(self):
        """Should detect user1 is being followed by user2"""

        u1 = User.query.get(self.u1_id)
        u2 = User.query.get(self.u2_id)
        db.session.commit()

        u2.following.append(u1)
        db.session.commit()

        result = u1.is_followed_by(u2)
        self.assertTrue(result)

    def test_user_is_not_followed_by(self):
        """Should detect user1 is not being followed by user2"""

        u1 = User.query.get(self.u1_id)
        u2 = User.query.get(self.u2_id)
        db.session.commit()

        u2.following.append(u1)
        db.session.commit()

        u2.following.remove(u1)
        db.session.commit()

        result = u1.is_followed_by(u2)

        self.assertFalse(result)

    def test_user_signup(self):
        """Make sure User.signup succesfully creates a new user given valid
           credentials"""
    
        u3_data = {
         "email" : "test3@test.com",
         "username" : "testuser3",
         "password" : "HASHED_PASSWORD",
         "image_url": ""
        }
        user = User.signup(**u3_data)
        db.session.commit()

        self.assertEqual(user.email, u3_data['email'])
        self.assertEqual(user.username, u3_data['username'])
        self.assertEqual(user.image_url, u3_data['image_url'])

        # probably easier to just test that we have 3 users now
        

    def test_user_signup_nonunique(self):
        """Make sure User.signup fails to create a new user if credentials are
           not unique"""
                    
        with self.assertRaises(exc.IntegrityError):
            u3 = User.signup(**U1)  
            db.session.commit()


    def test_user_signup_nonnullable(self):
        """Make sure User.signup fails to create a new user if non-nullable
           field is left blank"""

        u3_data = {
         "username" : "testuser3",
         "password" : "HASHED_PASSWORD",
         "image_url": ""
        }

        with self.assertRaises(TypeError):
            u3 = User.signup(**u3_data)
            db.session.commit()


    def test_authenticate(self):
        """Make sure User.authenticate successfully returns a user when given 
           a valid username and password"""
        u1 = User.query.get(self.u1_id)

        result1 = User.authenticate('testuser1', 'HASHED_PASSWORD')

        self.assertEqual(result1, u1)

        """Make sure User.authenticate fails to return a user when given an 
        invalid username"""

        result2 = User.authenticate('testuser4', 'HASHED_PASSWORD')
    
        self.assertFalse(result2)

        """Make sure User.authenticate fails to return a user when given an 
           invalid password """
    
        result3 = User.authenticate('testuser1', 'WRONG_PASSWORD')

        self.assertFalse(result3)

