import os
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

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
    users = db.Column(db.String(100))
    author = db.Column(db.String(100))
    text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

@app.route('/messages', methods=['POST'])
def send_message():
    data = request.json

    if not data or 'users' not in data or 'author' not in data or 'text' not in data:
        return jsonify({"status": "Invalid data"}), 400
    
    if session.get('user') != data['author']:
        return jsonify({"status": "Unauthorized"}), 401
    
    if session.get('user') not in data['users'].split("_"):
        return jsonify({"status": "Unauthorized"}), 401

    msg = Message(
        users=data['users'],
        author=data['author'],
        text=data['text']
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({"status": "ok"}) , 200


@app.route('/messages/<users>', methods=['GET'])
def get_messages(users):
    current_user = request.args.get('user')

    if not current_user:
        return jsonify({"error": "Non connecté"}), 401

    participants = users.split("_")
    if current_user not in participants:
        return jsonify({"error": "Accès refusé"}), 403

    messages = Message.query.filter_by(users=users)\
                            .order_by(Message.created_at.asc()).all()

    return jsonify([{"author": m.author, "text": m.text} for m in messages])

@app.route('/conversations', methods=['GET'])
def get_conversations():
    current_user = session.get('user')
    if not current_user:
        return jsonify({"error": "Non connecté"}), 401

    messages = Message.query.filter(
        Message.users.contains(current_user)
    ).all()

    contacts = set()
    for m in messages:
        if m.author == current_user:
            contacts.add(next(u for u in m.users.split("_") if u != current_user))
        else:
            contacts.add(m.author)

    return jsonify(list(contacts))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
