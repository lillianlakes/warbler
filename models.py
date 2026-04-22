"""SQLAlchemy models for Warbler."""

from datetime import datetime

from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.schema import UniqueConstraint

bcrypt = Bcrypt()
db = SQLAlchemy()


class Follows(db.Model):
    """Connection of a follower <-> followed_user."""

    __tablename__ = 'follows'

    user_being_followed_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete="cascade"),
        primary_key=True,
    )

    user_following_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete="cascade"),
        primary_key=True,
    )


class User(db.Model):
    """User in the system."""

    __tablename__ = 'users'

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    email = db.Column(
        db.Text,
        nullable=False,
        unique=True,
    )

    username = db.Column(
        db.Text,
        nullable=False,
        unique=True,
    )

    image_url = db.Column(
        db.Text,
        default="/static/images/default-pic.png",
    )

    header_image_url = db.Column(
        db.Text,
        default="/static/images/warbler-hero.jpg"
    )

    bio = db.Column(
        db.Text,
    )

    location = db.Column(
        db.Text,
    )

    password = db.Column(
        db.Text,
        nullable=False,
    )  ## to change later

    messages = db.relationship('Message', order_by='Message.timestamp.desc()')


    # users who follow this user -- many to one
    followers = db.relationship(
        "User",
        secondary="follows",
        primaryjoin=(Follows.user_being_followed_id == id),
        secondaryjoin=(Follows.user_following_id == id)
    )

    # users who this user follows  -- many to one
    following = db.relationship(
        "User",
        secondary="follows",
        primaryjoin=(Follows.user_following_id == id),
        secondaryjoin=(Follows.user_being_followed_id == id)
    )
    # Property that shows the messages liked by a user
    liked_messages = db.relationship('Message', secondary="likes", backref='users_who_like')
    bookmarked_messages = db.relationship(
        'Message',
        secondary="bookmarks",
        backref='users_who_bookmark'
    )
    quote_posts = db.relationship('QuotePost', backref='author', cascade='all, delete-orphan')
    reposts = db.relationship('Repost', backref='user', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User #{self.id}: {self.username}, {self.email}>"

    def is_followed_by(self, other_user):
        """Is this user followed by `other_user`?"""

        found_user_list = [user for user in self.followers if user == other_user]
        return len(found_user_list) == 1

    def is_following(self, other_user):
        """Is this user following `other_use`?"""

        found_user_list = [user for user in self.following if user == other_user]
        return len(found_user_list) == 1

    def has_liked_message(self, message):
        """Has this user liked this message?"""

        return message in self.liked_messages

    def has_bookmarked_message(self, message):
        """Has this user bookmarked this message?"""

        return message in self.bookmarked_messages

    def has_reposted_message(self, message):
        """Has this user reposted this message?"""

        return any(repost.message_id == message.id for repost in self.reposts)
    

    @classmethod
    def signup(cls, username, email, password, image_url):
        """Sign up user.

        Hashes password and adds user to system.
        """

        hashed_pwd = bcrypt.generate_password_hash(password).decode('UTF-8')

        user = User(
            username=username,
            email=email,
            password=hashed_pwd,
            image_url=image_url,
        )

        db.session.add(user)
        return user

    @classmethod
    def authenticate(cls, username, password):
        """Find user with `username` and `password`.

        This is a class method (call it on the class, not an individual user.)
        It searches for a user whose password hash matches this password
        and, if it finds such a user, returns that user object.

        If can't find matching user (or if password is wrong), returns False.
        """

        user = cls.query.filter_by(username=username).first()

        if user:
            is_auth = bcrypt.check_password_hash(user.password, password)
            if is_auth:
                return user

        return False


class Message(db.Model):
    """An individual message ("warble")."""

    __tablename__ = 'messages'

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    text = db.Column(
        db.String(140),
        nullable=False,
    )

    
    timestamp = db.Column( db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    
    # id of user who posted
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )

    user = db.relationship('User')
    like = db.relationship('Like', backref='messages')
    reply_parent_links = db.relationship(
        'Reply',
        foreign_keys='Reply.parent_message_id',
        backref='parent_message',
        cascade='all, delete-orphan'
    )
    reply_child_link = db.relationship(
        'Reply',
        foreign_keys='Reply.child_message_id',
        backref='child_message',
        uselist=False,
        cascade='all, delete-orphan'
    )
    reposts = db.relationship('Repost', backref='message', cascade='all, delete-orphan')
    quote_posts = db.relationship('QuotePost', backref='quoted_message', cascade='all, delete-orphan')
    hashtags = db.relationship('Hashtag', secondary='message_hashtags', backref='messages')

    def __repr__(self):
        return f"<Message #{self.id}: {self.text}, {self.timestamp}, {self.user_id}>"



# ================================================================= Likes
class Like(db.Model):
    """User liked messages""" 
    # every user can like many messages
    # every message can have many users liking it 

    __tablename__= "likes"
    message_id = db.Column(db.Integer,
                           db.ForeignKey('messages.id'), 
                           primary_key=True,
                           nullable=False)
                           
    users_id = db.Column(db.Integer,
                         db.ForeignKey('users.id'), 
                         primary_key=True, 
                         nullable=False) 


class Reply(db.Model):
    """Link between a parent message and a reply message."""

    __tablename__ = "replies"

    id = db.Column(db.Integer, primary_key=True)
    parent_message_id = db.Column(
        db.Integer,
        db.ForeignKey('messages.id', ondelete='CASCADE'),
        nullable=False,
    )
    child_message_id = db.Column(
        db.Integer,
        db.ForeignKey('messages.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Repost(db.Model):
    """A user reposted another message."""

    __tablename__ = "reposts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )
    message_id = db.Column(
        db.Integer,
        db.ForeignKey('messages.id', ondelete='CASCADE'),
        nullable=False,
    )
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('user_id', 'message_id', name='uq_repost_user_message'),)


class QuotePost(db.Model):
    """A user quoted a message with their own text."""

    __tablename__ = "quote_posts"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(140), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )
    message_id = db.Column(
        db.Integer,
        db.ForeignKey('messages.id', ondelete='CASCADE'),
        nullable=False,
    )


class Bookmark(db.Model):
    """Private user bookmark for a message."""

    __tablename__ = "bookmarks"

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False,
    )
    message_id = db.Column(
        db.Integer,
        db.ForeignKey('messages.id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False,
    )
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Notification(db.Model):
    """A user-facing notification event."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    recipient_user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )
    actor_user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id', ondelete='CASCADE'))
    quote_post_id = db.Column(db.Integer, db.ForeignKey('quote_posts.id', ondelete='CASCADE'))
    category = db.Column(db.String(30), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    recipient = db.relationship('User', foreign_keys=[recipient_user_id], backref='notifications')
    actor = db.relationship('User', foreign_keys=[actor_user_id])
    message = db.relationship('Message')
    quote_post = db.relationship('QuotePost')


class Hashtag(db.Model):
    """Normalized hashtag value (without #)."""

    __tablename__ = "hashtags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)


class MessageHashtag(db.Model):
    """Join table between messages and hashtags."""

    __tablename__ = "message_hashtags"

    message_id = db.Column(
        db.Integer,
        db.ForeignKey('messages.id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False,
    )
    hashtag_id = db.Column(
        db.Integer,
        db.ForeignKey('hashtags.id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False,
    )


def connect_db(app):
    """Connect this database to provided Flask app.

    You should call this in your Flask app.
    """

    db.app = app
    db.init_app(app)