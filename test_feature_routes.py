"""Feature route tests for reposts, quotes, hashtags, and AI assistant."""

import os
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


class FeatureRoutesTestCase(TestCase):
    """Covers high-value feature routes added in Phase 2."""

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

        self.actor = User.signup(
            username="actor",
            email="actor@test.com",
            password="password",
            image_url=None,
        )
        self.owner = User.signup(
            username="owner",
            email="owner@test.com",
            password="password",
            image_url=None,
        )
        db.session.commit()

        self.source_message = Message(
            text="This is the original message for reposts, quotes, and hashtags.",
            user_id=self.owner.id,
        )
        db.session.add(self.source_message)
        db.session.commit()
        self.source_message_id = self.source_message.id

    def tearDown(self):
        db.session.rollback()

    def _login_actor(self):
        with self.client.session_transaction() as sess:
            sess[CURR_USER_KEY] = self.actor.id

    def test_repost_add_and_toggle_remove(self):
        self._login_actor()

        first_resp = self.client.post(
            f"/messages/{self.source_message_id}/repost",
            follow_redirects=True,
        )
        self.assertEqual(first_resp.status_code, 200)

        repost_count = Repost.query.filter_by(
            user_id=self.actor.id,
            message_id=self.source_message_id,
        ).count()
        self.assertEqual(repost_count, 1)

        second_resp = self.client.post(
            f"/messages/{self.source_message_id}/repost",
            follow_redirects=True,
        )
        self.assertEqual(second_resp.status_code, 200)

        repost_count_after_toggle = Repost.query.filter_by(
            user_id=self.actor.id,
            message_id=self.source_message_id,
        ).count()
        self.assertEqual(repost_count_after_toggle, 0)

    def test_quote_post_creation(self):
        self._login_actor()

        resp = self.client.post(
            f"/messages/{self.source_message_id}/quote",
            data={"text": "This is my quote take."},
            follow_redirects=True,
        )

        self.assertEqual(resp.status_code, 200)

        quote = QuotePost.query.filter_by(
            user_id=self.actor.id,
            message_id=self.source_message_id,
        ).first()
        self.assertIsNotNone(quote)
        self.assertEqual(quote.text, "This is my quote take.")

    def test_trending_hashtags_route(self):
        hashtag = Hashtag(name="phase2")
        db.session.add(hashtag)
        db.session.flush()

        db.session.add(
            MessageHashtag(message_id=self.source_message.id, hashtag_id=hashtag.id)
        )
        db.session.commit()

        resp = self.client.get("/hashtags/trending")
        html = resp.get_data(as_text=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn("Trending Hashtags", html)
        self.assertIn("#phase2", html)
        self.assertIn("1 post", html)

    def test_hashtag_show_route(self):
        hashtag = Hashtag(name="launch")
        db.session.add(hashtag)
        db.session.flush()

        db.session.add(
            MessageHashtag(message_id=self.source_message.id, hashtag_id=hashtag.id)
        )
        db.session.commit()

        resp = self.client.get("/hashtags/launch")
        html = resp.get_data(as_text=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn("#launch", html)
        self.assertIn(self.source_message.text, html)

    def test_ai_assistant_requires_login(self):
        resp = self.client.get("/ai/assistant", follow_redirects=False)

        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers.get("Location", ""))

    def test_ai_assistant_compose_mode(self):
        self._login_actor()

        resp = self.client.post(
            "/ai/assistant",
            data={
                "task": "compose",
                "input_text": "I want to ship this feature this week.",
                "tone": "",
                "source_message_id": "",
            },
            follow_redirects=True,
        )
        html = resp.get_data(as_text=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn("Compose help", html)
        self.assertIn("Suggested draft", html)

    def test_ai_assistant_summary_mode(self):
        self._login_actor()

        resp = self.client.post(
            "/ai/assistant",
            data={
                "task": "summary",
                "input_text": "We launched a feature. Users liked it. We plan to iterate next week.",
                "tone": "",
                "source_message_id": "",
            },
            follow_redirects=True,
        )
        html = resp.get_data(as_text=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn("Thread summary", html)
        self.assertIn("Main keywords", html)

    def test_ai_assistant_rewrite_mode(self):
        self._login_actor()

        resp = self.client.post(
            "/ai/assistant",
            data={
                "task": "rewrite",
                "input_text": "this launch went great and we appreciate everyone",
                "tone": "professional",
                "source_message_id": "",
            },
            follow_redirects=True,
        )
        html = resp.get_data(as_text=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn("Tone rewrite (professional)", html)
        self.assertIn("Rewrite options", html)
