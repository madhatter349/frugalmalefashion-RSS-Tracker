import requests
import sqlite3
from datetime import datetime
import xml.etree.ElementTree as ET

# Database setup
DB_NAME = 'reddit_posts.db'
SUBREDDIT = "frugalmalefashion"
RSS_URL = f"https://old.reddit.com/r/{SUBREDDIT}/new/.rss"

# Debug logging
def log_debug(message):
    with open('debug.log', 'a') as f:
        f.write(f"{datetime.now()}: {message}\n")

# Get user-agent
def get_user_agent():
    try:
        user_agents = requests.get(
            "https://techfanetechnologies.github.io/latest-user-agent/user_agents.json"
        ).json()
        return user_agents[-2]
    except Exception as e:
        log_debug(f"Error fetching user agent: {e}")
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        id TEXT PRIMARY KEY,
        title TEXT,
        link TEXT,
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

# Fetch detailed content for a post
def fetch_post_details(post_id):
    detailed_url = f"https://old.reddit.com/r/{SUBREDDIT}/comments/{post_id}/.rss"
    log_debug(f"Fetching detailed RSS feed from {detailed_url}")
    headers = {"User-Agent": get_user_agent()}
    response = requests.get(detailed_url, headers=headers)

    if response.status_code != 200:
        log_debug(f"Error fetching detailed RSS: {response.status_code}")
        return ""

    try:
        root = ET.fromstring(response.content)
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}
        entry = root.find('atom:entry', namespace)
        if entry is not None:
            content = entry.find('atom:content', namespace).text
            return content
    except Exception as e:
        log_debug(f"Error parsing detailed RSS: {e}")
    return ""

# Fetch posts from RSS feed
def fetch_posts():
    log_debug(f"Fetching RSS feed from {RSS_URL}")
    headers = {"User-Agent": get_user_agent()}
    response = requests.get(RSS_URL, headers=headers)

    if response.status_code != 200:
        log_debug(f"Error: Received status code {response.status_code}")
        return []

    try:
        # Fix XML namespace handling
        root = ET.fromstring(response.content)
        namespace = {'atom': 'http://www.w3.org/2005/Atom', 
                     'media': 'http://search.yahoo.com/mrss/'}
        
        posts = []

        for entry in root.findall('atom:entry', namespace):
            post_id = entry.find('atom:id', namespace).text.split('/')[-2]
            title = entry.find('atom:title', namespace).text
            link = entry.find("atom:link[@rel='alternate']", namespace).attrib['href']
            author = entry.find('atom:author/atom:name', namespace).text
            thumbnail_elem = entry.find('media:thumbnail', namespace)
            thumbnail = thumbnail_elem.attrib['url'] if thumbnail_elem is not None else None

            # Fetch detailed content for the post
            content = fetch_post_details(post_id)

            posts.append({
                'id': post_id,
                'title': title,
                'link': link,
                'author': author,
                'thumbnail': thumbnail,
                'content': content
            })

        return posts

    except Exception as e:
        log_debug(f"RSS parsing error: {e}")
        return []
        
# Update database with fetched posts
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
            INSERT INTO posts (id, title, link, author, thumbnail, content, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (post['id'], post['title'], post['link'], post['author'], post['thumbnail'], post['content'], current_time, current_time))
            new_posts.append(post)
        else:
            cursor.execute('UPDATE posts SET last_seen = ?, content = ? WHERE id = ?', (current_time, post['content'], post['id']))
            updated_posts.append(post)

    cursor.execute('INSERT INTO runs (run_time) VALUES (?)', (current_time,))

    conn.commit()
    conn.close()

    return new_posts, updated_posts

# Notify via email (optional functionality remains the same)
def send_email(new_posts):
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    for post in new_posts:
        body_content = f"""
        <html>
            <body>
                <h2>New Post from Reddit Tracker</h2>
                <p>A new post has been found on <strong>{SUBREDDIT}</strong>:</p>
                <ul>
                    <li><strong>Title:</strong> <a href='{post['link']}'>{post['title']}</a></li>
                    <li><strong>Author:</strong> {post['author']}</li>
                    <li><strong>Content:</strong> {post['content']}</li>
                </ul>
                <p>Click the title to view the full post.</p>
            </body>
        </html>
        """

        subject_title = post['title'] if len(post['title']) <= 100 else post['title'][:97] + '...'

        data = {
            'to': 'madhatter349@gmail.com',
            'subject': f"New Post: {subject_title}",
            'body': body_content,
            'type': 'text/html'
        }

        response = requests.post('https://www.cinotify.cc/api/notify', headers=headers, data=data)

        log_debug(f"Email sending status code: {response.status_code}")
        log_debug(f"Email sending response: {response.text}")

        if response.status_code != 200:
            log_debug(f"Failed to send email for post: {post['title']}. Status code: {response.status_code}")
        else:
            log_debug(f"Email sent successfully for post: {post['title']}")

# Main script
def main():
    log_debug("Script started")
    init_db()

    current_posts = fetch_posts()
    new_posts, updated_posts = update_database(current_posts)

    log_debug(f"Found {len(new_posts)} new posts")
    log_debug(f"Updated {len(updated_posts)} existing posts")

    if new_posts:
        send_email(new_posts)
        log_debug(f"Attempted to send {len(new_posts)} email(s) for new posts")
    else:
        log_debug("No new posts found. No emails sent.")

    log_debug("Script finished")

if __name__ == "__main__":
    main()
