import base64
import hashlib
import os
import threading
import time
from enum import StrEnum

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.sql import quoted_name

app = Flask(__name__)
app.secret_key = os.urandom(24)

db_host = os.environ.get("DB_HOST", "localhost")
db_pass = os.environ.get("DB_PASSWORD", "root")
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+mysqlconnector://root:{db_pass}@{db_host}/ctf_chat"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

P = int(os.environ["DH_P"], 16)
G = int(os.environ.get("DH_G", "2"))

DH_PRIV = {
    "alice": 18797048554179765514424088363596800848600662970873301026280649101500043221613096924117654797438998700658373436816981958779414671330464114302193804576083606272688710169402185141949411988872778548619331047751610135196908682248816664032263931437395863955965966012845520850431208976858104856730690332849542242395204158503708533271482902015387223377673827169283653948597885998125237729899651505408186915067746619782273736971184450600723788706417869181789659057031703715068511137399036107748369102762745205950221538555113060233288810478587571568035245900417679123036864649831267414327026979523245274731839524536971340900475,
    "bob": 27087908375857312774523514272782976738359320365396222911526421732499519324047956376367195841880279748544964834890891413506063415452590751014413394750635880798822341362826430374703796718111344614304945434520015769477390897733605483900164595545242810461565400460740616094028351262002119777836272379579958325927422992435639798990718388504944113815786980427421851907804518485965216046942021989597814375533947190726524933637039491207536677892203020894484286785332598701986752438371471992667827541521574085911109801608407723361302067462936002661317487180447036886925072046263471312499710888673014880623478798946101038252859,
}


class Err(StrEnum):
    NOT_CONNECTED = "Not connected"
    USER_NOT_FOUND = "User not found"
    PASSWORDS_MISMATCH = "Passwords do not match."
    USERNAME_TAKEN = "Username already taken."
    INVALID_CREDENTIALS = "Invalid username or password."


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    password = db.Column(db.String(64), nullable=False)


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    author = db.relationship("User", foreign_keys=[author_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])


class Key(db.Model):
    __tablename__ = quoted_name("keys", True)
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    public_key = db.Column(db.Text, nullable=False)


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
            error = Err.INVALID_CREDENTIALS

    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if password != confirm:
            error = Err.PASSWORDS_MISMATCH
        elif User.query.filter_by(username=username).first():
            error = Err.USERNAME_TAKEN
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


@app.route("/messages", methods=["POST"])
def send_message():
    current_user = session.get("user")
    if not current_user:
        return jsonify({"error": Err.NOT_CONNECTED}), 401

    data = request.json
    receiver = User.query.filter_by(username=data["receiver"]).first()
    if not receiver:
        return jsonify({"error": Err.USER_NOT_FOUND}), 404

    author = User.query.filter_by(username=current_user).first()

    msg = Message(author_id=author.id, receiver_id=receiver.id, text=data["text"])
    db.session.add(msg)
    db.session.commit()
    return jsonify({"status": "ok"}), 200


@app.route("/messages/<other_username>", methods=["GET"])
def get_messages(other_username):
    current_user = session.get("user")
    if not current_user:
        return jsonify({"error": Err.NOT_CONNECTED}), 401

    me = User.query.filter_by(username=current_user).first()
    other = User.query.filter_by(username=other_username).first()
    if not other:
        return jsonify({"error": Err.USER_NOT_FOUND}), 404

    messages = (
        Message.query.filter(
            db.or_(
                db.and_(Message.author_id == me.id, Message.receiver_id == other.id),
                db.and_(Message.author_id == other.id, Message.receiver_id == me.id),
            )
        )
        .order_by(Message.id.asc())
        .all()
    )

    return jsonify([{"author": m.author.username, "text": m.text} for m in messages])


@app.route("/conversations", methods=["GET"])
def get_conversations():
    current_user = session.get("user")
    if not current_user:
        return jsonify({"error": Err.NOT_CONNECTED}), 401

    me = User.query.filter_by(username=current_user).first()

    messages = Message.query.filter(
        db.or_(Message.author_id == me.id, Message.receiver_id == me.id)
    ).all()

    contacts = set()
    for m in messages:
        if m.author_id == me.id:
            contacts.add(m.receiver.username)
        else:
            contacts.add(m.author.username)

    return jsonify(list(contacts))


@app.route("/users/<username>", methods=["GET"])
def check_user(username):
    if not session.get("user"):
        return jsonify({"error": Err.NOT_CONNECTED}), 401
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": Err.USER_NOT_FOUND}), 404
    return jsonify({"username": user.username}), 200


def derive_key(shared_secret):
    length = (shared_secret.bit_length() + 7) // 8
    shared_bytes = shared_secret.to_bytes(length)
    return hashlib.sha256(shared_bytes).digest()[:16]


def AES_encrypt(plain_text, key):
    cipher = AES.new(key, AES.MODE_CBC)
    b = pad(plain_text.encode("UTF-8", "ignore"), AES.block_size)
    return base64.b64encode(cipher.iv + cipher.encrypt(b)).decode("utf-8")


@app.route("/keys", methods=["GET", "POST"])
def keys():
    if request.method == "POST":
        data = request.json
        username = data.get("username")
        public_key = data.get("public_key")

        row = Key.query.filter_by(username=username).first()
        if row:
            row.public_key = str(public_key)
        else:
            db.session.add(Key(username=username, public_key=str(public_key)))
        db.session.commit()
        return jsonify({"status": "ok"}), 200

    rows = Key.query.all()
    return jsonify(
        {
            "keys": {r.username: r.public_key for r in rows},
            "p": str(P),
            "g": str(G),
        }
    )


@app.route("/admin", methods=["GET"])
def all_messages():
    alice = User.query.filter_by(username="alice").first()
    bob = User.query.filter_by(username="bob").first()
    messages = (
        Message.query.filter(
            Message.author_id == alice.id, Message.receiver_id == bob.id
        )
        .order_by(Message.id.desc())
        .limit(10)
        .all()
    )
    return jsonify([{"author": m.author.username, "text": m.text} for m in messages])


@app.route("/flag", methods=["POST"])
def submit_flag():
    with app.app_context():
        Flag = os.getenv("FLAG")
        data = request.json
        if data.get("flag") == Flag:
            return jsonify({"status": "correct"})
        else:
            return jsonify({"status": "incorrect"})


def loop_message_flag():
    with app.app_context():
        Flag = os.getenv("FLAG")
        alice = User.query.filter_by(username="alice").first()
        bob = User.query.filter_by(username="bob").first()

        while True:
            bob_row = Key.query.filter_by(username="bob").first()
            bob_pub = int(bob_row.public_key)
            shared = pow(bob_pub, DH_PRIV["alice"], P)
            key = derive_key(shared)

            ciphertext = AES_encrypt("Hello Bob, the flag is " + Flag, key)
            msg = Message(author_id=alice.id, receiver_id=bob.id, text=ciphertext)
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
