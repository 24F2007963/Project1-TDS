import requests
import datetime
import time
import json # Import the json module

def scrape_discourse_posts(base_url, category_id, start_date_str, end_date_str, cookies_str=None):
    """
    Scrapes Discourse forum posts from a specific category within a given date range.
    Uses cookies for authentication.

    Args:
        base_url (str): The base URL of the Discourse forum (e.g., "https://discourse.onlinedegree.iitm.ac.in").
        category_id (int): The ID of the category to scrape (e.g., 34 for 'tds-kb').
        start_date_str (str): The start date in 'YYYY-MM-DD' format (e.g., '2025-01-01').
        end_date_str (str): The end date in 'YYYY-MM-DD' format (e.g., '2025-04-14').
        cookies_str (str, optional): A string of cookies, typically copied from your browser's
                                     developer tools (e.g., "cookie1=value1; cookie2=value2").
                                     Defaults to None.

    Returns:
        list: A list of dictionaries, where each dictionary represents a post
              and contains 'topic_title', 'post_number', 'created_at', and 'content'.
    """
    # Convert date strings to datetime objects for comparison
    start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()

    all_scraped_posts = []
    page = 0
    per_page = 30  # Default number of topics/posts per API call

    # Parse the cookies string into a dictionary
    cookies = {}
    if cookies_str:
        for cookie_pair in cookies_str.split(';'):
            if '=' in cookie_pair:
                key, value = cookie_pair.strip().split('=', 1)
                cookies[key] = value
        print("Using cookies for authentication.")
    else:
        print("No cookies provided. This may lead to 403 Forbidden errors if authentication is required.")

    print(f"Starting to scrape posts from {base_url} in category ID {category_id} "
          f"between {start_date_str} and {end_date_str}...")

    while True:
        topics_url = f"{base_url}/latest.json?category={category_id}&page={page}"
        print(f"\nFetching topics from: {topics_url}")

        try:
            # Pass the cookies dictionary to the requests.get call
            response = requests.get(topics_url, cookies=cookies)
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            topics_data = response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 403:
                print(f"Error: Access Forbidden (403). This usually means the provided cookies "
                      f"are invalid, expired, or do not have permission to access this category. "
                      f"Please ensure your COOKIES_STRING is set correctly and is up-to-date.")
            else:
                print(f"Error fetching topics (HTTPError): {e}")
            break
        except requests.exceptions.RequestException as e:
            print(f"Error fetching topics (RequestException): {e}")
            break

        topics = topics_data.get('topic_list', {}).get('topics', [])
        if not topics:
            print("No more topics found or end of pagination.")
            break

        for topic in topics:
            topic_id = topic.get('id')
            topic_title = topic.get('title')
            topic_created_at_str = topic.get('created_at')
            try:
                topic_created_date = datetime.datetime.strptime(topic_created_at_str, '%Y-%m-%dT%H:%M:%S.%fZ').date()
            except (ValueError, TypeError):
                print(f"Warning: Could not parse topic creation date for topic ID {topic_id}: {topic_created_at_str}. Skipping topic.")
                continue

            # Check if the topic's creation date is within the desired range
            if start_date <= topic_created_date <= end_date:
                print(f"  Processing topic: '{topic_title}' (ID: {topic_id}, Created: {topic_created_date})")
                
                topic_posts_url = f"{base_url}/t/{topic_id}.json"
                try:
                    # Pass the cookies dictionary to the requests.get call
                    topic_response = requests.get(topic_posts_url, cookies=cookies)
                    topic_response.raise_for_status()
                    topic_full_data = topic_response.json()
                except requests.exceptions.HTTPError as e:
                    print(f"    Error: Access Forbidden (403) for topic {topic_id}. Check cookie permissions. Error: {e}")
                    continue
                except requests.exceptions.RequestException as e:
                    print(f"    Error fetching posts for topic {topic_id}: {e}")
                    continue

                posts = topic_full_data.get('post_stream', {}).get('posts', [])
                for post in posts:
                    post_created_at_str = post.get('created_at')
                    try:
                        post_created_date = datetime.datetime.strptime(post_created_at_str, '%Y-%m-%dT%H:%M:%S.%fZ').date()
                    except (ValueError, TypeError):
                        print(f"    Warning: Could not parse post creation date for post {post.get('post_number')} in topic {topic_id}: {post_created_at_str}. Skipping post.")
                        continue

                    # Check if the post's creation date is within the desired range
                    if start_date <= post_created_date <= end_date:
                        all_scraped_posts.append({
                            'topic_id': topic_id,
                            'topic_title': topic_title,
                            'post_number': post.get('post_number'),
                            'created_at': post_created_at_str,
                            'content': post.get('cooked') # 'cooked' contains the HTML content of the post
                        })
                    else:
                        pass
            else:
                pass

        if len(topics) < per_page:
            print("Reached the end of topics in this category.")
            break
        
        page += 1
        time.sleep(1) # Be polite and avoid hammering the server

    return all_scraped_posts

if __name__ == "__main__":
    # --- Configuration ---
    DISCOURSE_BASE_URL = "https://discourse.onlinedegree.iitm.ac.in"
    CATEGORY_ID = 34  # Corresponds to '/c/courses/tds-kb/34'
    START_DATE = "2025-01-01"
    END_DATE = "2025-04-14"

    # --- IMPORTANT: Cookie String for Authentication ---
    # To get your cookies:
    # 1. Log in to your Discourse account in your web browser.
    # 2. Open your browser's Developer Tools (usually F12 or Right-click -> Inspect).
    # 3. Go to the "Network" tab.
    # 4. Refresh the page.
    # 5. Click on any request (e.g., the main document request or an XHR request).
    # 6. In the "Headers" tab, look for "Request Headers" and find the "Cookie" header.
    # 7. Copy the entire string of cookies (e.g., "cookie1=value1; cookie2=value2; ...").
    #    This string should be provided below.
    #
    # Keep in mind that cookies can expire, so you might need to update this string
    # periodically if you run the script over a long duration or after your browser session ends.
    COOKIES_STRING = "_fbp=fb.2.1717551638654.974185809426571018; _ga_MXPR4XHYG9=GS1.1.1739471950.2.1.1739471970.0.0.0; _gcl_au=1.1.1061918401.1749145195; _ga_QHXRKWW9HH=GS2.3.s1749185253$o2$g0$t1749185253$j60$l0$h0; _ga=GA1.1.459870486.1717551638; _ga_5HTJMW67XK=GS2.1.s1749881122$o180$g1$t1749881153$j29$l0$h0; _bypass_cache=true; _ga_08NPRH5L4M=GS2.1.s1750193205$o357$g0$t1750193205$j60$l0$h0; _t=ci%2BUvbleYY8Cx7Yt852vj%2BFX%2FCEfRIQTeeo7pxls4kRNeM9eh%2FXAHtla%2F%2F0otOr422IJ6I9BK7YcxmUNON2sbjKPJBlZ7NDoOmmJ7k9fRuUx%2Fv3Z1DL3VpLk%2FyT0L2k7TOe8srPIospzmEUZk0y5b6onrTmOTTG8Yba8wVHe1tFgToRNI2U1FCRNVKs8WsqBJ6NlAu0Z3Np%2BVVrVg%2Bl2lhT8l91qnpXodKZTVqmfqp0rAPEJZIv%2Fzmw1mWKNdZFVG6ik8Gz71Jann7Bt7bxgoVTgTNh5uK%2Bn93hQ0AfzigfBzshAd40FipnGRPGMBnhV--o1%2BMNDs6bFA3rMvJ--S3etnSKW3Rk751%2Buh01BIQ%3D%3D; _forum_session=g1GbZ3GrCBOlGFCdwKoBx9snAbBC5Z5PgLG9Hl%2Bu2tUychKqU2kjX3ZfUshenhlNzV%2FHcsrIXcFO5t8l4Odhs%2F6179vVt9sUexkuQKtpgKXcpgxbIjEz%2FArF%2BusciQDZiJEyG6TcBbYWIsVMJgffXXpPHd1B3oglzH%2BimbhGOaVxdjUZm1%2B2jratQNkIKo3xyGjWybFHAiz8Oi2%2FCgihUopgKzGuXHpqOa%2BkfAY7gq4EbrNtURLpzi%2BK112bHyzbLciUuDE99FEdnetaTzPEELRX8dC83DYjGHiCwGUqQmbDh3ym4QK14M5Ql9617yF6GZcTNz9jMXUWPI0SOzIyOOzTT%2BlYt4njtufZWdHno%2Ffoj5rwHlthj3gqX1pMhw%3D%3D--XQBR7pyKK%2Fj61HVq--Y7JGFLrxt5UZTeHp5T%2BPiw%3D%3D" # <-- REPLACE THIS with your actual cookie string

    scraped_data = scrape_discourse_posts(
        DISCOURSE_BASE_URL,
        CATEGORY_ID,
        START_DATE,
        END_DATE,
        COOKIES_STRING
    )

    if scraped_data:
        print(f"\n--- Scraping Complete ---")
        print(f"Successfully scraped {len(scraped_data)} posts.")
        print("First 5 scraped posts (content truncated):")
        for i, post in enumerate(scraped_data[:5]): # Print first 5 posts as an example
            print(f"\n--- Post {i+1} ---")
            print(f"Topic: {post['topic_title']}")
            print(f"Post Number: {post['post_number']}")
            print(f"Created At: {post['created_at']}")
            print(f"Content (first 200 chars): {post['content'][:200]}...")

        # --- Save scraped data to a JSON file ---
        output_filename = "tds_discourse_posts.json"
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(scraped_data, f, ensure_ascii=False, indent=4)
            print(f"\nScraped data successfully saved to {output_filename}")
        except IOError as e:
            print(f"Error saving data to JSON file: {e}")

    else:
        print("\n--- Scraping Complete ---")
        print("No posts found or scraped within the specified criteria.")
        print("Please check the following:")
        print("  1. Ensure the COOKIES_STRING is correct and not expired.")
        print("  2. Verify that the category ID (34) is correct.")
        print("  3. Confirm that there are actual posts within the date range (2025-01-01 to 2025-04-14) in the forum.")
        print("  (Note: The specified dates are in the future, so no real posts will be found yet.)")
