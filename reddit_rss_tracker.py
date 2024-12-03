import requests
import sqlite3
from datetime import datetime
import xml.etree.ElementTree as ET
import time
import random

# RSS feed URL
RSS_URL = f"https://old.reddit.com/r/frugalmalefashion/new/.rss"

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
        thumbnail TEXT,
        content TEXT,
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
    response = requests.get(RSS_URL, headers=headers)

    if response.status_code != 200:
        log_debug(f"Error: Received status code {response.status_code}")
        return []

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        log_debug(f"XML parsing error: {e}")
        return []

    namespaces = {"atom": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/"}

    posts = []
    for entry in root.findall("atom:entry", namespaces):
        post = {
            'id': entry.find("atom:id", namespaces).text,
            'title': entry.find("atom:title", namespaces).text,
            'link': entry.find("atom:link", namespaces).attrib['href'],
            'published': entry.find("atom:updated", namespaces).text,
            'author': entry.find("atom:author/atom:name", namespaces).text,
            'thumbnail': None,
            'content': None
        }
        posts.append(post)

    return posts

def fetch_post_content(link):
    try:
        rss_link = "/".join(link.split("/")[:6]) + "/.rss"
        response = requests.get(rss_link)

        if response.status_code == 200:
            return response.text

        log_debug(f"Failed to fetch content for {link}: Status Code {response.status_code}")
    except Exception as e:
        log_debug(f"Error fetching post content for {link}: {e}")

    return "No content available"

def update_database(posts):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    current_time = datetime.now().isoformat()

    new_posts = []

    for post in posts:
        cursor.execute('SELECT id FROM posts WHERE id = ?', (post['id'],))
        result = cursor.fetchone()

        if result is None:
            cursor.execute('''
            INSERT INTO posts (id, title, link, published, author, thumbnail, content, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (post['id'], post['title'], post['link'], post['published'], post['author'], post['thumbnail'], None, current_time, current_time))
            new_posts.append(post)

    cursor.execute('INSERT INTO runs (run_time) VALUES (?)', (current_time,))

    conn.commit()
    conn.close()

    return new_posts

def fetch_content_for_new_posts(new_posts):
    for post in new_posts:
        time.sleep(random.uniform(3, 5))
        post['content'] = fetch_post_content(post['link'])
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE posts SET content = ? WHERE id = ?', (post['content'], post['id']))
        conn.commit()
        conn.close()

def main():
    log_debug("Script started")
    init_db()

    current_posts = fetch_posts()
    new_posts = update_database(current_posts)

    log_debug(f"Found {len(new_posts)} new posts")

    if new_posts:
        fetch_content_for_new_posts(new_posts)
        log_debug(f"Fetched content for {len(new_posts)} new posts")
    else:
        log_debug("No new posts found. No content fetched.")

    log_debug("Script finished")

if __name__ == "__main__":
    main()
