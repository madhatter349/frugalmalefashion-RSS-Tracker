import requests
import sqlite3
from datetime import datetime
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import html

# RSS feed URL
RSS_URL = "https://old.reddit.com/r/frugalmalefashion/new/.rss"

# Database setup
DB_NAME = 'reddit_posts.db'

def log_debug(message):
    """Log debug messages to a file with timestamp."""
    with open('debug.log', 'a') as f:
        f.write(f"{datetime.now()}: {message}\n")

def get_user_agent():
    """Fetch a user agent or return a default."""
    try:
        user_agents = requests.get(
            "https://techfanetechnologies.github.io/latest-user-agent/user_agents.json"
        ).json()
        return user_agents[-2]
    except Exception as e:
        log_debug(f"Error fetching user agent: {e}")
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

def init_db():
    """Initialize the SQLite database with posts and runs tables."""
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

def extract_post_details(content_html):
    """
    Extract meaningful details from the post content.
    Handles different types of Reddit post formats.
    """
    try:
        soup = BeautifulSoup(content_html, 'html.parser')
        
        # Handle image/link posts with table
        if soup.find('table'):
            # Try to extract text from the table or get the full text
            table_text = soup.get_text(separator=' ', strip=True)
            return table_text[:500] if table_text else "Image/Link post"
        
        # Handle text posts with markdown div
        elif soup.find('div', class_='md'):
            return soup.find('div', class_='md').get_text(strip=True)
        
        # Fallback to plain text extraction
        else:
            return soup.get_text(separator=' ', strip=True)[:500]
    
    except Exception as e:
        log_debug(f"Error extracting post details: {e}")
        return "No content details available"

def fetch_posts():
    """Fetch posts from the RSS feed."""
    user_agent = get_user_agent()
    headers = {"user-agent": user_agent}
    log_debug(f"Fetching RSS feed from {RSS_URL}")
    
    try:
        response = requests.get(RSS_URL, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        log_debug(f"Error fetching RSS feed: {e}")
        return []

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        log_debug(f"XML parsing error: {e}")
        return []

    namespaces = {
        "atom": "http://www.w3.org/2005/Atom", 
        "media": "http://search.yahoo.com/mrss/"
    }

    posts = []
    for entry in root.findall("atom:entry", namespaces):
        try:
            post = {
                'id': entry.find("atom:id", namespaces).text,
                'title': html.unescape(entry.find("atom:title", namespaces).text),
                'link': entry.find("atom:link", namespaces).attrib['href'],
                'published': entry.find("atom:updated", namespaces).text,
                'author': entry.find("atom:author/atom:name", namespaces).text,
                'thumbnail': None
            }
            
            # Extract content and clean it up
            content_elem = entry.find("atom:content", namespaces)
            if content_elem is not None:
                post['content'] = extract_post_details(content_elem.text)
            else:
                post['content'] = "No content available"

            # Try to get thumbnail if available
            thumbnail = entry.find("media:thumbnail", namespaces)
            if thumbnail is not None:
                post['thumbnail'] = thumbnail.attrib.get('url')

            posts.append(post)
        
        except Exception as e:
            log_debug(f"Error processing entry: {e}")

    return posts

def update_database(posts):
    """Update the database with new and existing posts."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    current_time = datetime.now().isoformat()

    new_posts = []
    updated_posts = []

    for post in posts:
        cursor.execute('SELECT id, last_seen FROM posts WHERE id = ?', (post['id'],))
        result = cursor.fetchone()

        if result is None:
            # New post
            cursor.execute('''
            INSERT INTO posts (id, title, link, published, author, thumbnail, content, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (post['id'], post['title'], post['link'], post['published'], 
                  post['author'], post['thumbnail'], post['content'], 
                  current_time, current_time))
            new_posts.append(post)
        else:
            # Existing post
            cursor.execute('UPDATE posts SET last_seen = ?, content = ? WHERE id = ?', 
                           (current_time, post['content'], post['id']))
            updated_posts.append(post)

    cursor.execute('INSERT INTO runs (run_time) VALUES (?)', (current_time,))

    conn.commit()
    conn.close()

    return new_posts, updated_posts

def generate_email_html(post):
    """
    Generate a rich HTML email for a specific post.
    Handles different post types with a flexible template.
    """
    # Truncate content if too long
    content = post['content'][:500] + '...' if len(post['content']) > 500 else post['content']
    
    # Create a more detailed and visually appealing email template
    email_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 15px; line-height: 1.6;">
        <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px;">
            <h2 style="color: #333; border-bottom: 1px solid #ddd; padding-bottom: 10px;">
                <a href="{post['link']}" style="color: #1a73e8; text-decoration: none;">
                    {html.escape(post['title'])}
                </a>
            </h2>
            
            <div style="background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <p><strong>Author:</strong> {html.escape(post['author'])}</p>
                <p><strong>Published:</strong> {post['published']}</p>
                
                {f'<img src="{post["thumbnail"]}" style="max-width: 100%; height: auto; margin: 10px 0;" />' if post["thumbnail"] else ''}
                
                <p style="color: #555;">{html.escape(content)}</p>
            </div>
            
            <p style="text-align: center; margin-top: 15px;">
                <a href="{post['link']}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                    View Full Post
                </a>
            </p>
        </div>
        
        <p style="color: #888; font-size: 0.8em; text-align: center; margin-top: 15px;">
            Automated notification from Reddit Tracker
        </p>
    </body>
    </html>
    """
    return email_html

def send_email(new_posts):
    """Send email notifications for new posts."""
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    for post in new_posts:
        try:
            # Prepare email data
            subject_title = post['title'][:100] + '...' if len(post['title']) > 100 else post['title']
            email_html = generate_email_html(post)

            data = {
                'to': 'madhatter349@gmail.com',
                'subject': f"New FrugalMaleFashion Post: {subject_title}",
                'body': email_html,
                'type': 'text/html'
            }

            # Send email
            response = requests.post('https://www.cinotify.cc/api/notify', headers=headers, data=data)

            # Log email sending result
            if response.status_code == 200:
                log_debug(f"Email sent successfully for post: {post['title']}")
            else:
                log_debug(f"Failed to send email for post: {post['title']}. Status code: {response.status_code}")
                log_debug(f"Response text: {response.text}")

        except Exception as e:
            log_debug(f"Exception in sending email for post {post['title']}: {e}")

def main():
    """Main script execution."""
    log_debug("Script started")
    init_db()

    try:
        current_posts = fetch_posts()
        new_posts, updated_posts = update_database(current_posts)

        log_debug(f"Found {len(new_posts)} new posts")
        log_debug(f"Updated {len(updated_posts)} existing posts")

        if new_posts:
            send_email(new_posts)
            log_debug(f"Attempted to send {len(new_posts)} email(s) for new posts")
        else:
            log_debug("No new posts found. No emails sent.")

    except Exception as e:
        log_debug(f"Unexpected error in main execution: {e}")

    log_debug("Script finished")

if __name__ == "__main__":
    main()
