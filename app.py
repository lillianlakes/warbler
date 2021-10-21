import os
import pdb

from flask import Flask, render_template, request, flash, redirect, session, g
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.exc import IntegrityError
from forms import UserAddForm, LoginForm, MessageForm, UserEditForm
from models import db, connect_db, User, Message

CURR_USER_KEY = "curr_user"

app = Flask(__name__)

# Get DB_URI from environ variable (useful for production/testing) or,
# if not set there, use development local db.
app.config['SQLALCHEMY_DATABASE_URI'] = (
   os.environ.get('DATABASE_URL', 'postgresql:///warbler'))

database_url = os.environ.get('DATABASE_URL', 'postgresql:///warbler')
database_url = database_url.replace('postgres://', 'postgresql://')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "it's a secret")
# added line below
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
# toolbar = DebugToolbarExtension(app)

connect_db(app)

##############################################################################
# User signup/login/logout


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


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """

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
            flash("Username already taken", 'danger')
            return render_template('users/signup.html', form=form)

        do_login(user)

        return redirect("/")

    else:
        return render_template('users/signup.html', form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login."""

    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(form.username.data,
                                 form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.username}!", "success")
            return redirect("/")

        flash("Invalid credentials.", 'danger')

    return render_template('users/login.html', form=form)


@app.route('/logout')
def logout():
    """Handle logout of user."""

    do_logout()
    flash("You have been logged out.")
    return redirect('/login')


##############################################################################
# General user routes:

@app.route('/users')
def list_users():
    """Page with listing of users.

    Can take a 'q' param in querystring to search by that username.
    """

    search = request.args.get('q')

    if not search:
        users = User.query.all()
    else:
        users = User.query.filter(User.username.like(f"%{search}%")).all()

    return render_template('users/index.html', users=users)


@app.route('/users/<int:user_id>')
def users_show(user_id):
    """Show user profile."""

    user = User.query.get_or_404(user_id)

    return render_template('users/show.html', user=user)


@app.route('/users/<int:user_id>/following')
def show_following(user_id):
    """Show list of people this user is following."""
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/following.html', user=user)


@app.route('/users/<int:user_id>/followers')
def users_followers(user_id):
    """Show list of followers of this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/followers.html', user=user)


@app.route('/users/follow/<int:follow_id>', methods=['POST'])
def add_follow(follow_id):
    """Add a follow for the currently-logged-in user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get_or_404(follow_id)
    g.user.following.append(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/stop-following/<int:follow_id>', methods=['POST'])
def stop_following(follow_id):
    """Have currently-logged-in-user stop following this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get(follow_id)
    g.user.following.remove(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/profile', methods=["GET", "POST"])
def profile():
    """Update profile for current user."""

    form = UserEditForm()
  
    # validate if user is logged in
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")
    

    if form.validate_on_submit():
        is_valid_pw = User.authenticate(g.user.username, form.password.data)
        
        # validate if user making change knows password
        if not is_valid_pw:
            flash("Access unauthorized.", "danger")
            return redirect('/')
        
        g.user.username = form.username.data or g.user.username
        g.user.email = form.email.data or g.user.email
        g.user.image_url = form.image_url.data or g.user.image_url
        g.user.header_image_url = (form.header_image_url.data 
                            or g.user.header_image_url)
        g.user.bio = form.bio.data or g.user.bio

        db.session.commit()

        return redirect(f'/users/{g.user.id}')

    return render_template('users/edit.html', form=form)


@app.route('/users/delete', methods=["POST"])
def delete_user():
    """Delete user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    do_logout()

    db.session.delete(g.user)
    db.session.commit()

    return redirect("/signup")


##############################################################################
# Messages routes:

@app.route('/messages/new', methods=["GET", "POST"])
def messages_add():
    """Add a message:

    Show form if GET. If valid, update message and redirect to user page.
    """

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = MessageForm()

    if form.validate_on_submit():
        msg = Message(text=form.text.data)
        g.user.messages.append(msg)
        db.session.commit()

        return redirect(f"/users/{g.user.id}")

    return render_template('messages/new.html', form=form)


@app.route('/messages/<int:message_id>', methods=["GET"])
def messages_show(message_id):
    """Show a message."""

    msg = Message.query.get(message_id)
    return render_template('messages/show.html', message=msg)


@app.route('/messages/<int:message_id>/delete', methods=["POST"])
def messages_destroy(message_id):
    """Delete a message."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    msg = Message.query.get(message_id)
    db.session.delete(msg)
    db.session.commit()

    return redirect(f"/users/{g.user.id}")



##############################################################################
# Likes 


@app.route('/messages/<int:message_id>/like', methods=['POST'])
def messages_like(message_id):
    """Add a like to this message for the currently-logged-in user."""

    if not g.user:
        flash("You must be logged in to like a message.", "danger")
        return redirect("/")

    liked_message = Message.query.get_or_404(message_id)
    
    g.user.liked_messages.append(liked_message)
    db.session.commit()

    return redirect("/")

    # use a .referrer on the request object to redirect back to the page that referred e.g.
    # either the favorites page or the home page....


@app.route('/messages/<int:message_id>/unlike', methods=['POST'])
def messages_unlike(message_id):
    """Have currently-logged-in-user unlike this message."""

    if not g.user:
        flash("You must be logged in to unlike a message.", "danger")
        return redirect("/")
        # would be better if we could go to liked_messages if coming from liked_messages
        # or home if coming from home... instead of default home

    unliked_message = Message.query.get_or_404(message_id)

    g.user.liked_messages.remove(unliked_message)
    db.session.commit()

    return redirect("/")


@app.route('/users/<int:user_id>/liked_messages')
def show_liked_messages(user_id):
    """Show list of messages this user has liked."""
    
    if not g.user:
        flash("You must be logged in to see messages liked.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/liked_messages.html', user=user)


# # nice to have for later
# @app.route('/messages/<int:message_id>/users_who_like')
# def users_who_like_message(message_id):
#     """Show list of users who like this message."""

#     if not g.user:
#         flash("Access unauthorized.", "danger")
#         return redirect("/")

#     message = Message.query.get_or_404(message_id)
#     # message.user

#     return render_template("messages/users_who_like.html", user=message.user, message=message)


##############################################################################
# Homepage and error pages


@app.route('/', methods=['GET','POST'])
def homepage():
    """Show homepage:

    - anon users: no messages
    - logged in: 100 most recent messages of followed_users
    """

    if not g.user:
        return render_template('home-anon.html')
    
    # TODO: set forms to have likes populated 
   
    # gets followers ids
    user_and_followers_ids = [user.id for user in g.user.following]

    # adds user's id
    user_and_followers_ids.append(g.user.id)

    messages = (Message
                .query
                .filter(Message.user_id.in_(user_and_followers_ids))
                .order_by(Message.timestamp.desc())
                .limit(100)
                .all())

    return render_template('home.html', messages=messages)


##############################################################################
# Turn off all caching in Flask
#   (useful for dev; in production, this kind of stuff is typically
#   handled elsewhere)
#
# https://stackoverflow.com/questions/34066804/disabling-caching-in-flask

@app.after_request
def add_header(response):
    """Add non-caching headers on every request."""

    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control
    response.cache_control.no_store = True
    return response
