from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("FLASK_KEY")
ckeditor = CKEditor(app)
Bootstrap5(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.id != 1:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DB_URL")
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))

    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="author")

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")

    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

    comments = relationship("Comment", back_populates="blog")

class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="comments")

    blog_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))
    blog = relationship("BlogPost", back_populates="comments")

    text: Mapped[str] = mapped_column(Text, nullable=False)


with app.app_context():
    db.create_all()

@app.route('/register', methods=["GET", "POST"])
def register():
    r_form=RegisterForm()
    if r_form.validate_on_submit():
        email_data = r_form.email.data
        user = db.session.execute(db.select(User).where(User.email == email_data)).scalar()
        if user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
        new_user = User(
            email = email_data,
            name = r_form.name.data,
            password = generate_password_hash(r_form.password.data, method="pbkdf2:sha256", salt_length=8)
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=r_form, logged_in=current_user.is_authenticated)

@app.route('/login', methods=["GET", "POST"])
def login():
    l_form=LoginForm()
    if l_form.validate_on_submit():
        email=l_form.email.data
        password=l_form.password.data
        try:
            user_to_login=db.session.execute(db.select(User).where(User.email==email)).scalar()
            if user_to_login is None:
                raise AttributeError()
        except AttributeError:
            flash("This email does not exist.")
            return render_template("login.html", form=l_form, logged_in=current_user.is_authenticated)
        if check_password_hash(user_to_login.password, password):
            login_user(user_to_login)
            return redirect(url_for("get_all_posts"))
        flash("Password is not correct.")
    return render_template("login.html", form=l_form, logged_in=current_user.is_authenticated)

@login_required
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))

@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    print(1)
    if current_user.is_authenticated:
        print(2)
        is_admin = current_user.id == 1
    else:
        print(3)
        is_admin = False
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated, admin=is_admin)


@login_required
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    result = db.session.execute(db.select(Comment).where(Comment.blog_id==post_id))
    comments = result.scalars().all()
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        new_comm = Comment(
            text=comment_form.body.data,
            author=current_user,
            blog=db.get_or_404(BlogPost, post_id),
        )
        db.session.add(new_comm)
        db.session.commit()
        return redirect(url_for("show_post", post_id=post_id))
    else:
        requested_post = db.get_or_404(BlogPost, post_id)
        if current_user.is_authenticated:
            is_admin = current_user.id == 1
        else:
            is_admin = False

        return render_template("post.html", post=requested_post, logged_in=current_user.is_authenticated, admin=is_admin, form=comment_form, comments=comments)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logged_in=current_user.is_authenticated)

@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, logged_in=current_user.is_authenticated)


@admin_only
@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html", logged_in=current_user.is_authenticated)


@app.route("/contact")
def contact():
    return render_template("contact.html", logged_in=current_user.is_authenticated)


if __name__ == "__main__":
    app.run(debug=False, port=5002)
