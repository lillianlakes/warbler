"""Notification view tests."""

import os
import re
from unittest import TestCase

from models import Message, Notification, User, db

os.environ['DATABASE_URL'] = "postgresql:///warbler-test"

from app import CURR_USER_KEY, app


db.create_all()
app.config['WTF_CSRF_ENABLED'] = False


class NotificationViewTestCase(TestCase):
    """Tests for unread badge and notification read transitions."""

    def setUp(self):
        Notification.query.delete()
        Message.query.delete()
        User.query.delete()

        self.client = app.test_client()

        self.recipient = User.signup(
            username="recipient",
            email="recipient@test.com",
            password="password",
            image_url=None,
        )
        self.actor = User.signup(
            username="actor",
            email="actor@test.com",
            password="password",
            image_url=None,
        )
        db.session.commit()

        self.message = Message(text="hello world", user_id=self.recipient.id)
        db.session.add(self.message)
        db.session.flush()

        self.notification = Notification(
            recipient_user_id=self.recipient.id,
            actor_user_id=self.actor.id,
            message_id=self.message.id,
            category="like",
            is_read=False,
        )
        db.session.add(self.notification)
        db.session.commit()

        self.recipient_id = self.recipient.id
        self.actor_id = self.actor.id
        self.message_id = self.message.id
        self.notification_id = self.notification.id

    def tearDown(self):
        db.session.rollback()

    def _login_as_recipient(self):
        with self.client.session_transaction() as sess:
            sess[CURR_USER_KEY] = self.recipient_id

    def test_unread_badge_shows_count(self):
        self._login_as_recipient()

        resp = self.client.get("/notifications")
        html = resp.get_data(as_text=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn('badge-danger', html)
        self.assertRegex(html, r">\s*1\s*<")

    def test_view_marks_single_notification_read(self):
        self._login_as_recipient()

        resp = self.client.get(f"/notifications/{self.notification_id}/view")

        self.assertEqual(resp.status_code, 302)

        refreshed = Notification.query.get(self.notification_id)
        self.assertTrue(refreshed.is_read)

    def test_mark_all_read_marks_all_unread(self):
        self._login_as_recipient()

        second_notification = Notification(
            recipient_user_id=self.recipient_id,
            actor_user_id=self.actor_id,
            message_id=self.message_id,
            category="reply",
            is_read=False,
        )
        db.session.add(second_notification)
        db.session.commit()

        resp = self.client.post("/notifications/read-all", follow_redirects=True)

        self.assertEqual(resp.status_code, 200)

        unread_count = Notification.query.filter_by(
            recipient_user_id=self.recipient_id,
            is_read=False,
        ).count()
        self.assertEqual(unread_count, 0)
