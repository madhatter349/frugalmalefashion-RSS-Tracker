import requests
import sqlite3
from datetime import datetime
import xml.etree.ElementTree as ET

# Database setup
DB_NAME = 'reddit_posts.db'
SUBREDDIT = "frugalmalefashion"
JSON_URL = f"https://www.reddit.com/r/{SUBREDDIT}/new.json"

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
    log_debug(f"Fetching JSON feed from {JSON_URL}")
    response = requests.get(JSON_URL, headers=headers)

    if response.status_code != 200:
        log_debug(f"Error: Received status code {response.status_code}")
        return []

    try:
        data = response.json()
        posts = []

        for child in data.get("data", {}).get("children", []):
            post_data = child.get("data", {})
            post = {
                'id': post_data.get("id"),
                'title': post_data.get("title"),
                'link': f"https://www.reddit.com{post_data.get('permalink')}",
                'published': datetime.utcfromtimestamp(post_data.get("created_utc")).isoformat(),
                'author': post_data.get("author"),
                'thumbnail': post_data.get("thumbnail"),
                'content': fetch_post_content(post_data.get("permalink"))
            }
            posts.append(post)

        return posts

    except Exception as e:
        log_debug(f"JSON parsing error: {e}")
        return []

def fetch_post_content(permalink):
    try:
        rss_url = f"https://rss.reddit.com{permalink}comments/"
        user_agent = get_user_agent()
        headers = {"user-agent": user_agent}
        response = requests.get(rss_url, headers=headers)

        if response.status_code != 200:
            log_debug(f"Error fetching RSS for comments: {response.status_code}")
            return "No comments available"

        try:
            root = ET.fromstring(response.content)
            comments = []

            for entry in root.findall("entry"):
                comment_author = entry.find("author/name").text if entry.find("author/name") is not None else "Unknown"
                comment_content = entry.find("content").text if entry.find("content") is not None else "No content"
                comments.append(f"{comment_author}: {comment_content}")

            return "\n".join(comments)

        except ET.ParseError as e:
            log_debug(f"Error parsing RSS for comments: {e}")
            return "No comments available"

    except Exception as e:
        log_debug(f"Error fetching post content for {permalink}: {e}")
        return "No comments available"

def update_database(posts):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    current_time = datetime.now().isoformat()

    new_posts = []
    updated_posts = []

    for post in posts:
        cursor.execute('SELECT id, last_seen FROM posts WHERE id = ?', (post['id'],))
        result = cursor.fetchone()

        if result is None:
            cursor.execute('''
            INSERT INTO posts (id, title, link, published, author, thumbnail, content, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (post['id'], post['title'], post['link'], post['published'], post['author'], post['thumbnail'], post['content'], current_time, current_time))
            new_posts.append(post)
        else:
            cursor.execute('UPDATE posts SET last_seen = ?, content = ? WHERE id = ?', (current_time, post['content'], post['id']))
            updated_posts.append(post)

    cursor.execute('INSERT INTO runs (run_time) VALUES (?)', (current_time,))

    conn.commit()
    conn.close()

    return new_posts, updated_posts

def main():
    log_debug("Script started")
    init_db()

    current_posts = fetch_posts()
    new_posts, updated_posts = update_database(current_posts)

    log_debug(f"Found {len(new_posts)} new posts")
    log_debug(f"Updated {len(updated_posts)} existing posts")

    log_debug("Script finished")

if __name__ == "__main__":
    main()
