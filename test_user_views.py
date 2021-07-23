"""Message View tests."""

# run these tests like:
#
#    FLASK_ENV=production python -m unittest test_user_views.py


import os
from unittest import TestCase

from models import db, connect_db, User

# BEFORE we import our app, let's set an environmental variable
# to use a different database for tests (we need to do this
# before we import our app, since that will have already
# connected to the database

os.environ['DATABASE_URL'] = "postgresql:///warbler-test"

# Now we can import app

from app import app, CURR_USER_KEY

# Create our tables (we do this here, so we only create the tables
# once for all tests --- in each test, we'll delete the data
# and create fresh new clean test data

db.drop_all()
db.create_all()

# Don't have WTForms use CSRF at all, since it's a pain to test

app.config['WTF_CSRF_ENABLED'] = False


class MessageViewTestCase(TestCase):
    """Test views for messages."""

    def setUp(self):
        """Create test client, add sample data."""

        User.query.delete()

        self.client = app.test_client()

        self.testuser = User.signup(username="testuser",
                                    email="test@test.com",
                                    password="testuser",
                                    image_url=None)
        
        db.session.commit()
        self.user_id = self.testuser
		
    # NOTE: how do we test for this? 
    # def test_add_user_to_g(self):
    #     """Can use add a user to g?"""


    #     with self.client as c:
    #         with c.session_transaction() as sess:
    #             sess[CURR_USER_KEY] = self.testuser.id
	# 	pass 

    def test_signup(self):
        """ test user signup page"""

        with self.client.session_transaction() as sess:
            sess[CURR_USER_KEY] = self.testuser.id

        # Test User Signup Page
            resp = self.client.get('/signup')
            html = resp.get_data(as_text=True)

            self.assertEqual(resp.status_code, 200)
            self.assertIn(  'User Signup', html)

    def test_signup_submit(self):

        with self.client.session_transaction() as sess:
            sess[CURR_USER_KEY] = self.testuser.id
            
            data = {
                "username":"testuser2",
                "password":"testpw2",
                "email":"test2@test.com",
                "image_url":"" 
            }            

            resp = self.client.post('/signup',
                                    data=data, 
                                    follow_redirects=True)

            html = resp.get_data(as_text=True)
            self.assertEqual(resp.status_code, 200)
            self.assertIn(f'{data["username"]}', html)