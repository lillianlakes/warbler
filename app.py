import mimetypes
import os
import re
import secrets
import time
import uuid
from collections import Counter
from datetime import timedelta

from flask import Flask, flash, g, redirect, render_template, request, session
from flask import jsonify
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

try:
    from flask_migrate import Migrate
except ImportError:  # pragma: no cover
    Migrate = None

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
    Like,
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

STOPWORDS = {
    "about", "after", "again", "also", "been", "could", "from", "have",
    "into", "just", "more", "most", "need", "that", "this", "with",
    "your", "were", "what", "when", "where", "which", "will", "would",
    "there", "their", "them", "they", "than", "then", "some", "over",
    "very", "have", "having", "make", "made", "like", "want", "good",
    "great", "nice", "today", "tomorrow", "yesterday", "thread", "post",
}

mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")

app = Flask(__name__)

database_url = os.environ.get("DATABASE_URL", "postgresql:///warbler")
database_url = database_url.replace("postgres://", "postgresql://")

is_production = (
    os.environ.get("RENDER", "").lower() == "true"
    or os.environ.get("FLASK_ENV", "").lower() == "production"
)
secret_key = os.environ.get("SECRET_KEY")

if is_production and not secret_key:
    raise RuntimeError("SECRET_KEY must be set in production")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = False
app.config["DEBUG_TB_INTERCEPT_REDIRECTS"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SECRET_KEY"] = secret_key or secrets.token_urlsafe(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = is_production
app.config["WTF_CSRF_TIME_LIMIT"] = 3600
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config["PREFERRED_URL_SCHEME"] = "https" if is_production else "http"

connect_db(app)
if Migrate:
    migrate = Migrate(app, db, compare_type=True)

with app.app_context():
    db.create_all()


def _extract_hashtag_names(text):
    return {tag.lower() for tag in re.findall(r"#([A-Za-z0-9_]+)", text or "")}


def _normalize_text(text, max_chars=2000):
    cleaned = " ".join((text or "").split())
    return cleaned[:max_chars]


def _trim_for_post(text, limit=140):
    normalized = _normalize_text(text, max_chars=limit + 20)
    if len(normalized) <= limit:
        return normalized

    clipped = normalized[:limit].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped


def _tokenize_keywords(*texts):
    words = []

    for text in texts:
        if not text:
            continue

        words.extend(
            word.lower()
            for word in re.findall(r"\b[\w']+\b", text)
            if len(word) > 3 and word.lower() not in STOPWORDS
        )

    return words


def _top_keywords(*texts, limit=5):
    counts = Counter(_tokenize_keywords(*texts))
    return [word for word, _ in counts.most_common(limit)]


def _format_tags(words):
    return [f"#{word}" for word in words[:4]]


def _load_message_thread(message):
    replies = (
        Message.query.join(Reply, Reply.child_message_id == Message.id)
        .options(selectinload(Message.user))
        .filter(Reply.parent_message_id == message.id)
        .order_by(Message.timestamp.asc())
        .all()
    )
    quote_posts = (
        QuotePost.query.filter_by(message_id=message.id)
        .options(
            selectinload(QuotePost.author),
            selectinload(QuotePost.quoted_message),
        )
        .order_by(desc(QuotePost.timestamp))
        .all()
    )
    return replies, quote_posts


def _build_thread_summary(message, replies, quote_posts):
    keywords = _top_keywords(
        message.text,
        *[reply.text for reply in replies],
        *[quote.text for quote in quote_posts],
    )
    hashtags = sorted(
        {hashtag.name for hashtag in message.hashtags}
        | set(_format_tags(keywords))
    )
    reply_snippets = [
        f"@{reply.user.username}: {reply.text[:90]}"
        for reply in replies[:3]
    ]

    return {
        "title": "Thread summary",
        "stats": {
            "reply_count": len(replies),
            "quote_count": len(quote_posts),
            "like_count": len(message.users_who_like),
            "keyword_count": len(keywords),
        },
        "main_points": [
            f"Original post from @{message.user.username}: {message.text}",
            f"The thread has {len(replies)} replies and {len(quote_posts)} quote posts.",
            f"Main keywords: {', '.join(keywords[:5]) if keywords else 'none detected'}.",
        ],
        "reply_snippets": reply_snippets,
        "hashtags": hashtags,
    }


def _build_text_summary(text):
    cleaned = _normalize_text(text)
    keywords = _top_keywords(cleaned, limit=5)
    sentences = [chunk.strip() for chunk in re.split(r"[.!?]", cleaned) if chunk.strip()]

    if not cleaned:
        return {
            "title": "Thread summary",
            "stats": {
                "reply_count": 0,
                "quote_count": 0,
                "like_count": 0,
                "keyword_count": 0,
            },
            "main_points": ["No text was provided to summarize."],
            "reply_snippets": [],
            "hashtags": [],
        }

    return {
        "title": "Thread summary",
        "stats": {
            "reply_count": 0,
            "quote_count": 0,
            "like_count": 0,
            "keyword_count": len(keywords),
        },
        "main_points": [
            f"Summary of the text: {sentences[0] if sentences else cleaned}",
            f"Main keywords: {', '.join(keywords[:5]) if keywords else 'none detected'}.",
            f"Length: {len(cleaned.split())} words.",
        ],
        "reply_snippets": [],
        "hashtags": _format_tags(keywords),
    }


def _build_reply_drafts(message, replies):
    keywords = _top_keywords(message.text, *[reply.text for reply in replies], limit=3)
    topic = keywords[0] if keywords else "that point"

    return [
        f"Thanks for sharing — {topic} is a useful reminder.",
        f"Great thread. I’d add that {topic} often pairs well with consistency.",
        f"Curious what you think the next step is for {topic}?",
    ]


def _build_compose_help(text, message=None, replies=None):
    replies = replies or []
    keywords = _top_keywords(text, *(reply.text for reply in replies), limit=4)
    hashtags = _format_tags(keywords)
    lead = _normalize_text(text) or (message.text if message else "")
    shortened = _trim_for_post(lead)

    if message:
        context = f"Replying to @{message.user.username}: {message.text}"
    else:
        context = "General draft mode."

    return {
        "title": "Compose help",
        "context": context,
        "draft": shortened,
        "reply_drafts": _build_reply_drafts(message, replies) if message else [
            f"{shortened} — thoughts?",
            f"{shortened} #warbler",
            f"Quick take: {shortened}",
        ],
        "hashtags": hashtags,
        "notes": [
            "Keep it under 140 characters.",
            "Lead with the key point.",
            "Use one or two hashtags max.",
        ],
    }


def _build_tone_rewrite(text, tone, message=None):
    source = _normalize_text(text) or (message.text if message else "")
    tone = (tone or "friendly").strip().lower()
    if tone not in {"professional", "witty", "concise", "friendly"}:
        tone = "friendly"

    theme = _trim_for_post(source)

    presets = {
        "professional": [
            f"Thanks for the update. {theme}",
            f"Appreciate the insight — {theme}",
        ],
        "witty": [
            f"Plot twist: {theme}",
            f"Tiny bug, big lesson: {theme}",
        ],
        "concise": [
            f"TL;DR: {theme}",
            f"Quick take: {theme}",
        ],
        "friendly": [
            f"Nice one — {theme}",
            f"Love this: {theme}",
        ],
    }

    options = [
        _trim_for_post(option)
        for option in presets.get(tone, [
            f"{theme}",
            f"{theme} #warbler",
        ])
    ]

    deduped_options = []
    seen = set()
    for option in options:
        if option and option not in seen:
            deduped_options.append(option)
            seen.add(option)

    return {
        "title": f"Tone rewrite ({tone})",
        "original": source,
        "options": deduped_options,
        "hashtags": _format_tags(_top_keywords(source, limit=3)),
    }


def _build_assistant_payload(task, input_text, tone, message=None, replies=None, quote_posts=None):
    replies = replies or []
    quote_posts = quote_posts or []

    if task == "summary" and message:
        return _build_thread_summary(message, replies, quote_posts)

    if task == "summary":
        return _build_text_summary(input_text)

    if task == "rewrite":
        return _build_tone_rewrite(input_text, tone, message=message)

    return _build_compose_help(input_text, message=message, replies=replies)


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

    existing_notification = Notification.query.filter_by(
        recipient_user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        message_id=message_id,
        quote_post_id=quote_post_id,
        category=category,
        is_read=False,
    ).first()

    if existing_notification:
        existing_notification.timestamp = func.now()
        return

    notification = Notification(
        recipient_user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        message_id=message_id,
        quote_post_id=quote_post_id,
        category=category,
    )
    db.session.add(notification)


def _build_ranked_feed_query(user_ids):
    engagement_subquery = (
        db.session.query(
            Message.id.label("message_id"),
            (
                (func.count(func.distinct(Like.users_id)) * 3)
                + (func.count(func.distinct(Repost.id)) * 4)
                + (func.count(func.distinct(Reply.id)) * 2)
            ).label("engagement_score"),
        )
        .outerjoin(Like, Like.message_id == Message.id)
        .outerjoin(Repost, Repost.message_id == Message.id)
        .outerjoin(Reply, Reply.parent_message_id == Message.id)
        .filter(Message.user_id.in_(user_ids))
        .group_by(Message.id)
        .subquery()
    )

    ranked_feed_query = (
        db.session.query(Message, engagement_subquery.c.engagement_score)
        .join(engagement_subquery, engagement_subquery.c.message_id == Message.id)
        .filter(
            (engagement_subquery.c.engagement_score > 0)
            | (func.length(Message.text) >= 20)
        )
    )

    return ranked_feed_query, engagement_subquery


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

    g.request_id = uuid.uuid4().hex[:12]
    g.request_start = time.perf_counter()

    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])
        if g.user:
            g.unread_notifications_count = Notification.query.filter_by(
                recipient_user_id=g.user.id,
                is_read=False,
            ).count()
        else:
            session.pop(CURR_USER_KEY, None)
            g.unread_notifications_count = 0
    else:
        g.user = None
        g.unread_notifications_count = 0


def do_login(user):
    """Log in user."""

    session.clear()
    session.permanent = True
    session[CURR_USER_KEY] = user.id


def do_logout():
    """Logout user."""

    session.clear()


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

    user = User.query.options(
        selectinload(User.messages).selectinload(Message.hashtags),
        selectinload(User.messages).selectinload(Message.users_who_like),
        selectinload(User.messages).selectinload(Message.reposts),
        selectinload(User.messages).selectinload(Message.reply_parent_links),
        selectinload(User.followers),
        selectinload(User.following),
    ).get_or_404(user_id)
    quote_posts = (
        QuotePost.query.filter_by(user_id=user.id)
        .options(
            selectinload(QuotePost.author),
            selectinload(QuotePost.quoted_message),
        )
        .order_by(desc(QuotePost.timestamp))
        .limit(20)
        .all()
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
    msg = Message.query.options(
        selectinload(Message.user),
        selectinload(Message.hashtags),
        selectinload(Message.users_who_like),
        selectinload(Message.reposts),
    ).get_or_404(message_id)

    replies = (
        Message.query.join(Reply, Reply.child_message_id == Message.id)
        .options(selectinload(Message.user))
        .filter(Reply.parent_message_id == msg.id)
        .order_by(Message.timestamp.asc())
        .all()
    )
    quote_posts = (
        QuotePost.query.filter_by(message_id=msg.id)
        .options(
            selectinload(QuotePost.author),
            selectinload(QuotePost.quoted_message),
        )
        .order_by(desc(QuotePost.timestamp))
        .all()
    )

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
        .options(
            selectinload(Notification.actor),
            selectinload(Notification.message),
            selectinload(Notification.quote_post),
        )
        .order_by(desc(Notification.timestamp))
        .limit(100)
        .all()
    )

    return render_template("notifications/index.html", notifications=notifications)


@app.route("/notifications/<int:notification_id>/view")
def notifications_view(notification_id):
    if not g.user:
        flash("You must be logged in to view notifications.", "danger")
        return redirect("/")

    notification = Notification.query.filter_by(
        id=notification_id,
        recipient_user_id=g.user.id,
    ).first_or_404()

    if not notification.is_read:
        notification.is_read = True
        db.session.commit()

    if notification.message_id:
        return redirect(f"/messages/{notification.message_id}")

    if notification.quote_post_id and notification.quote_post:
        return redirect(f"/messages/{notification.quote_post.message_id}")

    if notification.actor_user_id:
        return redirect(f"/users/{notification.actor_user_id}")

    return redirect("/notifications")


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
        .options(
            selectinload(Message.user),
            selectinload(Message.hashtags),
            selectinload(Message.users_who_like),
            selectinload(Message.reposts),
            selectinload(Message.reply_parent_links),
        )
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
    assistant_message = None
    thread_replies = []
    thread_quote_posts = []

    source_message_id = request.args.get("message_id") or form.source_message_id.data
    if source_message_id:
        assistant_message = Message.query.get(source_message_id)
        if assistant_message:
            thread_replies, thread_quote_posts = _load_message_thread(assistant_message)
            if request.method == "GET" and not form.input_text.data:
                form.input_text.data = assistant_message.text
            form.source_message_id.data = str(assistant_message.id)

    if form.validate_on_submit():
        assistant_message = None
        if form.source_message_id.data:
            assistant_message = Message.query.get(form.source_message_id.data)
            if assistant_message:
                thread_replies, thread_quote_posts = _load_message_thread(assistant_message)

        result = _build_assistant_payload(
            form.task.data,
            form.input_text.data,
            form.tone.data,
            message=assistant_message,
            replies=thread_replies,
            quote_posts=thread_quote_posts,
        )

    prefill = request.args.get("prefill")
    if prefill and request.method == "GET" and not form.input_text.data:
        form.input_text.data = prefill

    task = request.args.get("task")
    if task in {"compose", "summary", "rewrite"} and request.method == "GET":
        form.task.data = task

    if assistant_message and request.method == "GET" and form.task.data == "compose":
        result = _build_assistant_payload(
            "compose",
            form.input_text.data,
            form.tone.data,
            message=assistant_message,
            replies=thread_replies,
            quote_posts=thread_quote_posts,
        )

    return render_template(
        "ai/assistant.html",
        form=form,
        result=result,
        assistant_message=assistant_message,
        thread_replies=thread_replies,
        thread_quote_posts=thread_quote_posts,
    )


@app.route("/", methods=["GET", "POST"])
def homepage():
    if not g.user:
        return render_template("home-anon.html")

    user_and_followers_ids = [user.id for user in g.user.following]
    user_and_followers_ids.append(g.user.id)

    page = max(request.args.get("page", 1, type=int), 1)
    per_page = 30
    ranked_feed_query, engagement_subquery = _build_ranked_feed_query(
        user_and_followers_ids
    )

    total_messages = ranked_feed_query.count()

    ranked_message_rows = (
        ranked_feed_query
        .options(
            selectinload(Message.user),
            selectinload(Message.hashtags),
            selectinload(Message.users_who_like),
            selectinload(Message.reposts),
            selectinload(Message.reply_parent_links),
        )
        .order_by(
            desc(engagement_subquery.c.engagement_score),
            Message.timestamp.desc(),
        )
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    messages = [message for message, _ in ranked_message_rows]

    quote_posts = (
        QuotePost.query.filter(QuotePost.user_id.in_(user_and_followers_ids))
        .options(
            selectinload(QuotePost.author),
            selectinload(QuotePost.quoted_message),
        )
        .order_by(desc(QuotePost.timestamp))
        .limit(25)
        .all()
    )

    has_next_page = page * per_page < total_messages

    return render_template(
        "home.html",
        messages=messages,
        quote_posts=quote_posts,
        page=page,
        has_next_page=has_next_page,
    )


@app.route("/healthz")
def healthcheck():
    return jsonify({"status": "ok"}), 200


@app.after_request
def add_header(response):
    """Add non-caching headers on every request."""

    response.cache_control.no_store = True
    response.headers["X-Request-ID"] = getattr(g, "request_id", "")

    elapsed_ms = (time.perf_counter() - getattr(g, "request_start", time.perf_counter())) * 1000
    user_id = getattr(getattr(g, "user", None), "id", None)
    app.logger.info(
        "request_id=%s method=%s path=%s status=%s user_id=%s duration_ms=%.2f",
        getattr(g, "request_id", ""),
        request.method,
        request.path,
        response.status_code,
        user_id,
        elapsed_ms,
    )

    return response


@app.errorhandler(404)
def page_not_found(error):
    app.logger.warning(
        "request_id=%s method=%s path=%s status=404",
        getattr(g, "request_id", ""),
        request.method,
        request.path,
    )
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(error):
    db.session.rollback()
    app.logger.exception(
        "request_id=%s method=%s path=%s status=500",
        getattr(g, "request_id", ""),
        request.method,
        request.path,
    )
    return render_template("500.html"), 500
