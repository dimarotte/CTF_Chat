CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL,
  password VARCHAR(64) NOT NULL
);

INSERT INTO users (username, password) VALUES ('alice',  UUID());
INSERT INTO users (username, password) VALUES ('bob',  UUID());

CREATE TABLE messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    author_id INT NOT NULL,
    receiver_id INT NOT NULL,
    text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES users(id),
    FOREIGN KEY (receiver_id) REFERENCES users(id)
);