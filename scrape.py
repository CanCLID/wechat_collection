import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote
import os
import re


def extract_content(url):
    """
    Extracts content from a WeChat article URL and returns it as Markdown.

    Args:
      url: The URL of the WeChat article.

    Returns:
      A string containing the article content in Markdown format, or None if
      an error occurs.
    """

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract title
    title_tag = soup.find('h1', {'id': 'activity-name'})
    title = title_tag.text.strip() if title_tag else "No Title Found"

    # Sanitize the title for use as a filename
    filename = re.sub(r'[\\/*?:"<>|]', "", title) + ".md"  # Remove invalid characters

    # Extract author
    author_tag = soup.find('span', {'id': 'js_author_name'})
    author = author_tag.text.strip() if author_tag else "No Author Found"

    # Extract publication time (CORRECTED)
    time_tag = soup.find('span', {'id': 'meta_content_hide_info'})
    publish_time_tag = time_tag.find('em', {'id': 'publish_time'}) if time_tag else None
    publish_time = publish_time_tag.text.strip() if publish_time_tag else "No Publish Time Found"
    print(publish_time_tag)

    # Extract main content
    content_div = soup.find('div', {'id': 'js_content'})
    if not content_div:
        return "No Content Found"

    markdown_content = ""

    # Add Markdown metadata
    markdown_content += "---\n"
    markdown_content += f"title: {title}\n"
    markdown_content += f"author: {author}\n"
    markdown_content += f"source: {url}\n"
    markdown_content += "---\n\n"

    # Add title, author, and publication time as metadata
    markdown_content += f"# {title}\n\n"
    markdown_content += f"**Author:** {author}\n\n"
    markdown_content += f"**Published:** {publish_time}\n\n"

    # Iterate through content elements and convert to Markdown
    for element in content_div.children:
        if element.name == 'p':
            # Handle text within paragraphs
            paragraph_text = ""
            for child in element.children:
                if child.name == 'span' or child.name == None:
                    paragraph_text += child.get_text(strip=False)
                elif child.name == 'br':
                    paragraph_text += "\n\n"
                elif child.name == 'img':
                    img_src = child.get('data-src')
                    if img_src:
                        paragraph_text += f"![]({img_src})\n\n"  # Add image in its original position

            # Remove leading/trailing whitespace and add to Markdown
            paragraph_text = paragraph_text.strip()
            if paragraph_text:
                markdown_content += paragraph_text + "\n\n"
        elif element.name == 'section':
            section_text = ""
            # Find all images within the section, regardless of depth
            all_images_in_section = element.find_all('img')
            img_index = 0  # Keep track of the current image

            for child in element.children:
                if child.name == 'img':
                    # Skip individual <img> tags, as they'll be handled by all_images_in_section
                    continue
                elif child.name == 'section':
                    # Handle text and images within sections recursively
                    section_output, img_index = handle_section(child, all_images_in_section, img_index)
                    section_text += section_output
                elif child.name == 'p' and child.get('style') and 'font-size: 0px' in child.get('style'):
                    continue
                else:
                    # Get text content, preserving spaces
                    text_content = child.get_text(strip=False)
                    section_text += text_content

            # Add images that are not part of nested sections
            while img_index < len(all_images_in_section):
                img = all_images_in_section[img_index]
                img_src = img.get('data-src')
                if img_src:
                    section_text += f"![]({img_src})\n\n"
                img_index += 1

            if section_text.strip():
                markdown_content += section_text + "\n\n"

    return markdown_content, filename


def handle_section(section_element, all_images, img_index):
    """
    Recursively handles nested sections, extracting text and images in order.

    Args:
      section_element: The BeautifulSoup element representing a section.
      all_images: A list of all img elements within the parent section
      img_index: The index of the current image being processed

    Returns:
      A string containing the section content in Markdown format.
    """
    section_text = ""
    for child in section_element.children:
        if child.name == 'img':
            # Handle images using the all_images list and img_index
            if img_index < len(all_images):
                img = all_images[img_index]
                img_src = img.get('data-src')
                if img_src:
                    section_text += f"![]({img_src})\n\n"
                img_index += 1
        elif child.name == 'section':
            # Recursively handle nested sections
            nested_section_output, img_index = handle_section(child, all_images, img_index)
            section_text += nested_section_output
        elif child.name == 'p' and child.get('style') and 'font-size: 0px' in child.get('style'):
            continue
        else:
            # Get text content, preserving spaces
            text_content = child.get_text(strip=False)
            section_text += text_content

    return section_text, img_index


if __name__ == "__main__":
    # Example usage:
    wechat_url = "https://mp.weixin.qq.com/s?__biz=MzA5MDkxNTA4Ng%3D%3D&mid=2454908782&idx=1&sn=389bb4d0cf40715ec4a32cf855a30bc6&scene=45#wechat_redirect"
    markdown_output, filename = extract_content(wechat_url)

    if markdown_output:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(markdown_output)
        print(f"Markdown content saved to {filename}")
    else:
        print("Failed to extract content.")
