import os
import time
import threading
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)
app.secret_key = os.urandom(24)

db_host = os.environ.get("DB_HOST", "localhost")
db_pass = os.environ.get("DB_PASSWORD", "root")
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+mysqlconnector://root:{db_pass}@{db_host}/ctf_chat"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    password = db.Column(db.String(64), nullable=False)


@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("chat"))
    return redirect(url_for("login"))


@app.route("/chat")
def chat():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("chat.html", user=session["user"])


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session["user"] = user.username
            return redirect(url_for("chat"))
        else:
            error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if password != confirm:
            error = "Passwords do not match."
        elif User.query.filter_by(username=username).first():
            error = "Username already taken."
        else:
            db.session.add(User(username=username, password=password))
            db.session.commit()
            session["user"] = username
            return redirect(url_for("chat"))

    return render_template("register.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    author = db.relationship('User', foreign_keys=[author_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

@app.route('/messages', methods=['POST'])
def send_message():
    current_user = session.get('user')
    if not current_user:
        return jsonify({"error": "Non connecté"}), 401

    data = request.json
    receiver = User.query.filter_by(username=data['receiver']).first()
    if not receiver:
        return jsonify({"error": "Utilisateur introuvable"}), 404

    author = User.query.filter_by(username=current_user).first()

    msg = Message(
        author_id=author.id,
        receiver_id=receiver.id,
        text=data['text']
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({"status": "ok"}) , 200


@app.route('/messages/<other_username>', methods=['GET'])
def get_messages(other_username):
    current_user = session.get('user')
    if not current_user:
        return jsonify({"error": "Non connecté"}), 401

    me = User.query.filter_by(username=current_user).first()
    other = User.query.filter_by(username=other_username).first()
    if not other:
        return jsonify({"error": "Utilisateur introuvable"}), 404

    messages = Message.query.filter(
        db.or_(
            db.and_(Message.author_id == me.id, Message.receiver_id == other.id),
            db.and_(Message.author_id == other.id, Message.receiver_id == me.id)
        )
    ).order_by(Message.id.asc()).all()

    return jsonify([{"author": m.author.username, "text": m.text} for m in messages])

@app.route('/conversations', methods=['GET'])
def get_conversations():
    current_user = session.get('user')
    if not current_user:
        return jsonify({"error": "Non connecté"}), 401

    me = User.query.filter_by(username=current_user).first()

    messages = Message.query.filter(
        db.or_(
            Message.author_id == me.id,
            Message.receiver_id == me.id
        )
    ).all()

    contacts = set()
    for m in messages:
        if m.author_id == me.id:
            contacts.add(m.receiver.username)
        else:
            contacts.add(m.author.username)

    return jsonify(list(contacts))

def loop_message_flag():
    with app.app_context():
        Flag = os.getenv("FLAG")
        author = User.query.filter_by(username="alice").first()
        receiver = User.query.filter_by(username="bob").first()

        while True:
            msg = Message(
                author_id=author.id,
                receiver_id=receiver.id,
                text="Hello Bob, the flag is " + Flag
            )
            db.session.add(msg)
            db.session.commit()
            time.sleep(1)

def wait_for_db():
    with app.app_context():
        while True:
            try:
                db.session.execute(text("SELECT 1"))
                break
            except Exception as e:
                time.sleep(2)

if __name__ == "__main__":
    wait_for_db()
    threading.Thread(target=loop_message_flag, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
