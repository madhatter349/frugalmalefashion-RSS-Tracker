import requests
import sqlite3
from datetime import datetime
import time
import feedparser
from bs4 import BeautifulSoup

# RSS feed URL
RSS_URL = "https://old.reddit.com/r/frugalmalefashion/new/.rss"

# Database setup
DB_NAME = 'reddit_posts.db'

def log_debug(message):
    with open('debug.log', 'a') as f:
        f.write(f"{datetime.now()}: {message}\n")

def get_user_agent():
    try:
        user_agents = requests.get(
            "https://techfanetechnologies.github.io/latest-user-agent/user_agents.json"
        ).json()
        return user_agents[-2]
    except Exception as e:
        log_debug(f"Error fetching user agent: {e}")
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        id TEXT PRIMARY KEY,
        title TEXT,
        link TEXT,
        published TEXT,
        author TEXT,
        description TEXT,
        first_seen TEXT,
        last_seen TEXT
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_time TEXT
    )
    ''')
    conn.commit()
    conn.close()

def fetch_posts():
    user_agent = get_user_agent()
    headers = {"user-agent": user_agent}
    log_debug(f"Fetching RSS feed from {RSS_URL}")
    try:
        response = requests.get(RSS_URL, headers=headers)
        if response.status_code != 200:
            log_debug(f"Error: Received status code {response.status_code}")
            return []

        feed = feedparser.parse(response.content)
        if feed.bozo:  # Indicates an error while parsing
            log_debug(f"Error parsing RSS feed: {feed.bozo_exception}")
            return []

        return feed.entries
    except Exception as e:
        log_debug(f"Error fetching posts: {e}")
        return []

def clean_description(raw_html):
    try:
        soup = BeautifulSoup(raw_html, 'html.parser')
        # Extract and clean the text content
        return soup.get_text(separator=" ", strip=True)
    except Exception as e:
        log_debug(f"Error cleaning description: {e}")
        return raw_html

def update_database(posts):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    current_time = datetime.now().isoformat()
    new_posts = []

    for post in posts:
        post_id = post.get("id", post.get("link"))
        cursor.execute('SELECT id FROM posts WHERE id = ?', (post_id,))
        result = cursor.fetchone()

        cleaned_description = clean_description(post.get("summary", ""))

        if result is None:
            cursor.execute('''
            INSERT INTO posts (id, title, link, published, author, description, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                post_id,
                post.get("title"),
                post.get("link"),
                post.get("published", ""),
                post.get("author", ""),
                cleaned_description,
                current_time,
                current_time
            ))
            new_posts.append(post)
        else:
            cursor.execute('UPDATE posts SET last_seen = ? WHERE id = ?', (current_time, post_id))

    cursor.execute('INSERT INTO runs (run_time) VALUES (?)', (current_time,))
    conn.commit()
    conn.close()

    return new_posts

def main():
    log_debug("Script started")
    init_db()

    current_posts = fetch_posts()
    new_posts = update_database(current_posts)

    log_debug(f"Found {len(new_posts)} new posts")
    log_debug("Script finished")

if __name__ == "__main__":
    main()
