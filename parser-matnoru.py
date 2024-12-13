import requests
from bs4 import BeautifulSoup
import time

def fetch_html_from_url(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to fetch HTML from {url}, status code: {response.status_code}")

def parse_html_blocks(html):
    soup = BeautifulSoup(html, 'html.parser')

    # Find all blocks with a specific ID pattern or class
    blocks = soup.find_all('div', id=lambda x: x and x.startswith('entryID'))

    parsed_blocks = []

    for block in blocks:
        # Extract the title and link from the eTitle div
        title_div = block.find('div', class_='eTitle')
        title = title_div.a.text if title_div and title_div.a else None
        link = title_div.a['href'] if title_div and title_div.a and 'href' in title_div.a.attrs else None

        # Extract the main message
        message_div = block.find('div', class_='eMessage')
        main_message = message_div.text.strip() if message_div else None

        # Remove "Пример употребления" and "Примечание" sections from the main message
        if main_message:
            main_message = main_message.split("Пример употребления:")[0]
            main_message = main_message.split("Примечание:")[0].strip()

        # Split the main message into separate strings if it exists
        main_message_parts = None
        if main_message:
            main_message_parts = [part.strip() for part in main_message.split('|')]

        # Extract additional details like rating, date, author, views, and language
        details_div = block.find('div', class_='eDetails')

        # Extract date
        date_span = details_div.find('span', title=True) if details_div else None
        date = date_span['title'] if date_span and 'title' in date_span.attrs else None

        # Extract author
        author = details_div.find('u').text if details_div and details_div.find('u') else None

        # Extract views
        views = None
        if details_div:
            views_text = details_div.text
            views_start = views_text.find("Прочитали:")
            if views_start != -1:
                views = views_text[views_start:].split('|')[0].replace("Прочитали:", "").strip()

        # Extract rating
        rating_span = details_div.find('span', id=lambda x: x and x.startswith('entRating')) if details_div else None
        rating = rating_span.text if rating_span else None

        # Extract language
        language_link = details_div.find('a', href=lambda x: x and 'mat' in x) if details_div else None
        language = language_link.text if language_link else None

        # Append parsed block to the list
        parsed_blocks.append({
            "title": title,
            "link": link,
            "main_message": main_message,
            "main_message_parts": main_message_parts,
            "date": date,
            "author": author,
            "views": views,
            "rating": rating,
            "language": language,
        })

    return parsed_blocks

def fetch_and_parse_pages(base_url, page_count):
    all_parsed_data = []
    for page in range(1, page_count + 1):
        url = f"{base_url}?page{page}"
        print(f"Fetching URL: {url}")
        time.sleep(2)  # Wait 2 seconds between requests to reduce suspicion
        html_page = fetch_html_from_url(url)
        parsed_data = parse_html_blocks(html_page)
        all_parsed_data.extend(parsed_data)
    return all_parsed_data

def format_blocks_to_strings(parsed_data):
    formatted_strings = []
    for block in parsed_data:
        main_message_parts = block.get("main_message_parts", [None, None, None])
        language = block.get("language", "Unknown language")

        if len(main_message_parts) >= 3:
            formatted_string = (
                f"{main_message_parts[0]} (произносится {main_message_parts[1]}) – {main_message_parts[2]}. {language}"
            )
            formatted_strings.append(formatted_string)
    return formatted_strings

def save_strings_to_file(strings, filename):
    with open(filename, "w", encoding="utf-8") as file:
        for string in strings:
            file.write(string + "\n")

# Example usage with URL
base_url = 'https://matno.ru/board/'
parsed_data = fetch_and_parse_pages(base_url, 79)

# Format parsed data to strings
formatted_strings = format_blocks_to_strings(parsed_data)

# Save formatted strings to a text file
save_strings_to_file(formatted_strings, "output.txt")

print("Formatted strings have been saved to output.txt")

