"""Feed ranking and filtering tests."""

import os
from datetime import datetime, timedelta
from unittest import TestCase

from models import (
    Bookmark,
    Follows,
    Hashtag,
    Like,
    Message,
    MessageHashtag,
    Notification,
    QuotePost,
    Reply,
    Repost,
    User,
    db,
)

os.environ['DATABASE_URL'] = "postgresql:///warbler-test"

from app import CURR_USER_KEY, app


db.create_all()
app.config['WTF_CSRF_ENABLED'] = False


class FeedViewTestCase(TestCase):
    """Tests for engagement-weighted feed ranking and low-signal filtering."""

    def setUp(self):
        db.session.rollback()

        Notification.query.delete()
        Bookmark.query.delete()
        QuotePost.query.delete()
        Repost.query.delete()
        Reply.query.delete()
        Like.query.delete()
        Follows.query.delete()
        MessageHashtag.query.delete()
        Hashtag.query.delete()
        Message.query.delete()
        User.query.delete()
        db.session.commit()

        self.client = app.test_client()

        self.viewer = User.signup(
            username="viewer",
            email="viewer@test.com",
            password="password",
            image_url=None,
        )
        self.author = User.signup(
            username="author",
            email="author@test.com",
            password="password",
            image_url=None,
        )
        self.liker = User.signup(
            username="liker",
            email="liker@test.com",
            password="password",
            image_url=None,
        )
        db.session.commit()

        self.viewer.following.append(self.author)
        db.session.commit()

        self.high_engagement_text = "This older post should rank highly with engagement."
        self.recent_text = "This is a newer post with little engagement but enough text."
        self.low_signal_text = "ok"

        self.high_engagement_msg = Message(
            text=self.high_engagement_text,
            user_id=self.author.id,
            timestamp=datetime.utcnow() - timedelta(days=3),
        )
        self.recent_msg = Message(
            text=self.recent_text,
            user_id=self.author.id,
            timestamp=datetime.utcnow(),
        )
        self.low_signal_msg = Message(
            text=self.low_signal_text,
            user_id=self.author.id,
            timestamp=datetime.utcnow(),
        )

        db.session.add_all([
            self.high_engagement_msg,
            self.recent_msg,
            self.low_signal_msg,
        ])
        db.session.commit()

        self.liker.liked_messages.append(self.high_engagement_msg)
        db.session.commit()

    def tearDown(self):
        db.session.rollback()

        Notification.query.delete()
        Bookmark.query.delete()
        QuotePost.query.delete()
        Repost.query.delete()
        Reply.query.delete()
        Like.query.delete()
        Follows.query.delete()
        MessageHashtag.query.delete()
        Hashtag.query.delete()
        Message.query.delete()
        User.query.delete()
        db.session.commit()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess[CURR_USER_KEY] = self.viewer.id

    def test_feed_ranks_engagement_before_recency(self):
        self._login()

        resp = self.client.get("/")
        html = resp.get_data(as_text=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.high_engagement_text, html)
        self.assertIn(self.recent_text, html)

        high_index = html.find(self.high_engagement_text)
        recent_index = html.find(self.recent_text)

        self.assertNotEqual(high_index, -1)
        self.assertNotEqual(recent_index, -1)
        self.assertLess(high_index, recent_index)

    def test_feed_filters_low_signal_posts(self):
        self._login()

        resp = self.client.get("/")
        html = resp.get_data(as_text=True)

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(f">{self.low_signal_text}<", html)
