import mimetypes
import os
import re

from flask import Flask, flash, g, redirect, render_template, request, session
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError

from forms import (
    AIAssistantForm,
    LoginForm,
    MessageForm,
    QuotePostForm,
    ReplyForm,
    UserAddForm,
    UserEditForm,
)
from models import (
    Bookmark,
    Hashtag,
    Message,
    MessageHashtag,
    Notification,
    QuotePost,
    Reply,
    Repost,
    User,
    connect_db,
    db,
)

CURR_USER_KEY = "curr_user"

mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "postgresql:///warbler")
database_url = os.environ.get("DATABASE_URL", "postgresql:///warbler")
database_url = database_url.replace("postgres://", "postgresql://")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = False
app.config["DEBUG_TB_INTERCEPT_REDIRECTS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "it's a secret")
app.config["SQLALCHEMY_DATABASE_URI"] = database_url

connect_db(app)

with app.app_context():
    db.create_all()

print("database url is ", database_url)


def _extract_hashtag_names(text):
    return {tag.lower() for tag in re.findall(r"#([A-Za-z0-9_]+)", text or "")}


def _attach_hashtags_to_message(message):
    hashtag_names = _extract_hashtag_names(message.text)

    for name in hashtag_names:
        hashtag = Hashtag.query.filter_by(name=name).first()
        if not hashtag:
            hashtag = Hashtag(name=name)
            db.session.add(hashtag)
            db.session.flush()

        if hashtag not in message.hashtags:
            message.hashtags.append(hashtag)


def _create_notification(recipient_user_id, category, actor_user_id, message_id=None, quote_post_id=None):
    if recipient_user_id == actor_user_id:
        return

    notification = Notification(
        recipient_user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        message_id=message_id,
        quote_post_id=quote_post_id,
        category=category,
    )
    db.session.add(notification)


def _run_ai_assistant(task, input_text, tone):
    cleaned = " ".join(input_text.strip().split())

    if task == "compose":
        return (
            "Draft idea:\n"
            f"{cleaned}\n\n"
            "Suggested post (140 chars):\n"
            f"{cleaned[:120]} #warbler"
        )

    if task == "summary":
        chunks = [chunk.strip() for chunk in re.split(r"[.!?]", cleaned) if chunk.strip()]
        if not chunks:
            return "No content found to summarize."

        top_chunks = chunks[:3]
        bullets = "\n".join([f"- {chunk}" for chunk in top_chunks])
        return f"Thread summary:\n{bullets}"

    rewrite_tone = (tone or "clear and concise").strip()
    return (
        f"Tone rewrite ({rewrite_tone}):\n"
        f"{cleaned}\n\n"
        "Alternative shorter version:\n"
        f"{cleaned[:100]}"
    )


@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""

    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])
    else:
        g.user = None


def do_login(user):
    """Log in user."""

    session[CURR_USER_KEY] = user.id


def do_logout():
    """Logout user."""

    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Handle user signup."""

    form = UserAddForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                password=form.password.data,
                email=form.email.data,
                image_url=form.image_url.data or User.image_url.default.arg,
            )
            db.session.commit()
        except IntegrityError:
            flash("Username already taken", "danger")
            return render_template("users/signup.html", form=form)

        do_login(user)
        return redirect("/")

    return render_template("users/signup.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""

    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(form.username.data, form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.username}!", "success")
            return redirect("/")

        flash("Invalid credentials.", "danger")

    return render_template("users/login.html", form=form)


@app.route("/logout")
def logout():
    """Handle logout of user."""

    do_logout()
    flash("You have been logged out.")
    return redirect("/login")


@app.route("/users")
def list_users():
    """Page with listing of users."""

    search = request.args.get("q")

    if not search:
        users = User.query.all()
    else:
        users = User.query.filter(User.username.like(f"%{search}%")).all()

    return render_template("users/index.html", users=users)


@app.route("/users/<int:user_id>")
def users_show(user_id):
    """Show user profile."""

    user = User.query.get_or_404(user_id)
    quote_posts = (
        QuotePost.query.filter_by(user_id=user.id).order_by(desc(QuotePost.timestamp)).limit(20).all()
    )

    return render_template("users/show.html", user=user, quote_posts=quote_posts)


@app.route("/users/<int:user_id>/following")
def show_following(user_id):
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template("users/following.html", user=user)


@app.route("/users/<int:user_id>/followers")
def users_followers(user_id):
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template("users/followers.html", user=user)


@app.route("/users/follow/<int:follow_id>", methods=["POST"])
def add_follow(follow_id):
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get_or_404(follow_id)
    g.user.following.append(followed_user)
    _create_notification(followed_user.id, "follow", g.user.id)
    db.session.commit()

    return redirect(request.referrer or f"/users/{g.user.id}/following")


@app.route("/users/stop-following/<int:follow_id>", methods=["POST"])
def stop_following(follow_id):
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get_or_404(follow_id)
    if followed_user in g.user.following:
        g.user.following.remove(followed_user)
        db.session.commit()

    return redirect(request.referrer or f"/users/{g.user.id}/following")


@app.route("/users/profile", methods=["GET", "POST"])
def profile():
    form = UserEditForm()

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    if form.validate_on_submit():
        is_valid_pw = User.authenticate(g.user.username, form.password.data)

        if not is_valid_pw:
            flash("Access unauthorized.", "danger")
            return redirect("/")

        g.user.username = form.username.data or g.user.username
        g.user.email = form.email.data or g.user.email
        g.user.image_url = form.image_url.data or g.user.image_url
        g.user.header_image_url = form.header_image_url.data or g.user.header_image_url
        g.user.bio = form.bio.data or g.user.bio

        db.session.commit()

        return redirect(f"/users/{g.user.id}")

    return render_template("users/edit.html", form=form)


@app.route("/users/delete", methods=["POST"])
def delete_user():
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    do_logout()
    db.session.delete(g.user)
    db.session.commit()

    return redirect("/signup")


@app.route("/messages/new", methods=["GET", "POST"])
def messages_add():
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = MessageForm()

    if form.validate_on_submit():
        msg = Message(text=form.text.data)
        g.user.messages.append(msg)
        db.session.flush()
        _attach_hashtags_to_message(msg)
        db.session.commit()

        return redirect(f"/users/{g.user.id}")

    return render_template("messages/new.html", form=form)


@app.route("/messages/<int:message_id>", methods=["GET"])
def messages_show(message_id):
    msg = Message.query.get_or_404(message_id)

    replies = (
        Message.query.join(Reply, Reply.child_message_id == Message.id)
        .filter(Reply.parent_message_id == msg.id)
        .order_by(Message.timestamp.asc())
        .all()
    )
    quote_posts = QuotePost.query.filter_by(message_id=msg.id).order_by(desc(QuotePost.timestamp)).all()

    return render_template("messages/show.html", message=msg, replies=replies, quote_posts=quote_posts)


@app.route("/messages/<int:message_id>/delete", methods=["POST"])
def messages_destroy(message_id):
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    msg = Message.query.get_or_404(message_id)

    if msg.user_id != g.user.id:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    db.session.delete(msg)
    db.session.commit()

    return redirect(f"/users/{g.user.id}")


@app.route("/messages/<int:message_id>/reply", methods=["GET", "POST"])
def messages_reply(message_id):
    if not g.user:
        flash("You must be logged in to reply.", "danger")
        return redirect("/")

    parent_message = Message.query.get_or_404(message_id)
    form = ReplyForm()

    if form.validate_on_submit():
        reply_message = Message(text=form.text.data, user_id=g.user.id)
        db.session.add(reply_message)
        db.session.flush()

        reply_link = Reply(parent_message_id=parent_message.id, child_message_id=reply_message.id)
        db.session.add(reply_link)
        _attach_hashtags_to_message(reply_message)
        _create_notification(parent_message.user_id, "reply", g.user.id, message_id=reply_message.id)
        db.session.commit()

        return redirect(f"/messages/{parent_message.id}")

    return render_template("messages/reply.html", form=form, parent_message=parent_message)


@app.route("/messages/<int:message_id>/repost", methods=["POST"])
def messages_repost(message_id):
    if not g.user:
        flash("You must be logged in to repost.", "danger")
        return redirect("/")

    message = Message.query.get_or_404(message_id)
    existing = Repost.query.filter_by(user_id=g.user.id, message_id=message.id).first()

    if existing:
        db.session.delete(existing)
        flash("Repost removed.", "info")
    else:
        repost = Repost(user_id=g.user.id, message_id=message.id)
        db.session.add(repost)
        _create_notification(message.user_id, "repost", g.user.id, message_id=message.id)
        flash("Reposted.", "success")

    db.session.commit()
    return redirect(request.referrer or "/")


@app.route("/messages/<int:message_id>/quote", methods=["GET", "POST"])
def messages_quote(message_id):
    if not g.user:
        flash("You must be logged in to quote post.", "danger")
        return redirect("/")

    message = Message.query.get_or_404(message_id)
    form = QuotePostForm()

    if form.validate_on_submit():
        quote_post = QuotePost(text=form.text.data, user_id=g.user.id, message_id=message.id)
        db.session.add(quote_post)
        _create_notification(message.user_id, "quote", g.user.id, message_id=message.id, quote_post_id=None)
        db.session.commit()

        return redirect(f"/messages/{message.id}")

    return render_template("messages/quote.html", form=form, message=message)


@app.route("/messages/<int:message_id>/like", methods=["POST"])
def messages_like(message_id):
    if not g.user:
        flash("You must be logged in to like a message.", "danger")
        return redirect("/")

    liked_message = Message.query.get_or_404(message_id)

    if liked_message not in g.user.liked_messages:
        g.user.liked_messages.append(liked_message)
        _create_notification(liked_message.user_id, "like", g.user.id, message_id=liked_message.id)
        db.session.commit()

    return redirect(request.referrer or "/")


@app.route("/messages/<int:message_id>/unlike", methods=["POST"])
def messages_unlike(message_id):
    if not g.user:
        flash("You must be logged in to unlike a message.", "danger")
        return redirect("/")

    unliked_message = Message.query.get_or_404(message_id)

    if unliked_message in g.user.liked_messages:
        g.user.liked_messages.remove(unliked_message)
        db.session.commit()

    return redirect(request.referrer or "/")


@app.route("/messages/<int:message_id>/bookmark", methods=["POST"])
def messages_bookmark(message_id):
    if not g.user:
        flash("You must be logged in to bookmark.", "danger")
        return redirect("/")

    message = Message.query.get_or_404(message_id)

    if message in g.user.bookmarked_messages:
        g.user.bookmarked_messages.remove(message)
        flash("Bookmark removed.", "info")
    else:
        g.user.bookmarked_messages.append(message)
        flash("Bookmarked.", "success")

    db.session.commit()
    return redirect(request.referrer or "/")


@app.route("/users/<int:user_id>/liked_messages")
def show_liked_messages(user_id):
    if not g.user:
        flash("You must be logged in to see messages liked.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template("users/liked_messages.html", user=user)


@app.route("/users/<int:user_id>/bookmarks")
def show_bookmarks(user_id):
    if not g.user:
        flash("You must be logged in to see bookmarks.", "danger")
        return redirect("/")

    if g.user.id != user_id:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template("users/bookmarks.html", user=user)


@app.route("/notifications")
def notifications_index():
    if not g.user:
        flash("You must be logged in to view notifications.", "danger")
        return redirect("/")

    notifications = (
        Notification.query.filter_by(recipient_user_id=g.user.id)
        .order_by(desc(Notification.timestamp))
        .limit(100)
        .all()
    )

    return render_template("notifications/index.html", notifications=notifications)


@app.route("/notifications/read-all", methods=["POST"])
def notifications_read_all():
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    Notification.query.filter_by(recipient_user_id=g.user.id, is_read=False).update(
        {"is_read": True}, synchronize_session=False
    )
    db.session.commit()

    return redirect("/notifications")


@app.route("/hashtags/trending")
def hashtags_trending():
    trending = (
        db.session.query(Hashtag, func.count(MessageHashtag.message_id).label("usage_count"))
        .join(MessageHashtag, MessageHashtag.hashtag_id == Hashtag.id)
        .group_by(Hashtag.id)
        .order_by(desc("usage_count"), Hashtag.name)
        .limit(20)
        .all()
    )

    return render_template("hashtags/trending.html", trending=trending)


@app.route("/hashtags/<string:tag_name>")
def hashtags_show(tag_name):
    normalized = (tag_name or "").strip().lower()
    hashtag = Hashtag.query.filter_by(name=normalized).first_or_404()
    messages = (
        Message.query.join(MessageHashtag, MessageHashtag.message_id == Message.id)
        .filter(MessageHashtag.hashtag_id == hashtag.id)
        .order_by(desc(Message.timestamp))
        .all()
    )

    return render_template("hashtags/show.html", hashtag=hashtag, messages=messages)


@app.route("/ai/assistant", methods=["GET", "POST"])
def ai_assistant():
    if not g.user:
        flash("You must be logged in to use AI assistant.", "danger")
        return redirect("/login")

    form = AIAssistantForm()
    result = None

    if form.validate_on_submit():
        result = _run_ai_assistant(form.task.data, form.input_text.data, form.tone.data)

    prefill = request.args.get("prefill")
    if prefill and request.method == "GET":
        form.input_text.data = prefill

    return render_template("ai/assistant.html", form=form, result=result)


@app.route("/", methods=["GET", "POST"])
def homepage():
    if not g.user:
        return render_template("home-anon.html")

    user_and_followers_ids = [user.id for user in g.user.following]
    user_and_followers_ids.append(g.user.id)

    messages = (
        Message.query.filter(Message.user_id.in_(user_and_followers_ids))
        .order_by(Message.timestamp.desc())
        .limit(100)
        .all()
    )

    quote_posts = (
        QuotePost.query.filter(QuotePost.user_id.in_(user_and_followers_ids))
        .order_by(desc(QuotePost.timestamp))
        .limit(25)
        .all()
    )

    return render_template("home.html", messages=messages, quote_posts=quote_posts)


@app.after_request
def add_header(response):
    """Add non-caching headers on every request."""

    response.cache_control.no_store = True
    return response
