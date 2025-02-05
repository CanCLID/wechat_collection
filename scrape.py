from bs4 import BeautifulSoup
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def extract_content(url: str):
    """
    Extracts content from a WeChat article URL and returns it as Markdown.

    Args:
      url: The URL of the WeChat article.

    Returns:
      A string containing the article content in Markdown format, or None if
      an error occurs.
    """

    print("Starting new Chrome instance...")
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        print(f"Attempting to fetch URL with Chrome...")
        driver.get(url)

        # First check for verification button and click it if present
        print("Checking for verification button...")
        try:
            verify_button = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a#js_verify, a.weui-btn.weui-btn_primary"))
            )
            print("Verification button found, attempting to click...")

            # Try multiple click methods
            try:
                verify_button.click()
            except ElementClickInterceptedException:
                ActionChains(driver).move_to_element(verify_button).click().perform()
            except Exception as e:
                print(f"Failed to click button: {e}")
                driver.execute_script("arguments[0].click();", verify_button)

            print("Clicked verification button, waiting for content...")
            time.sleep(1)  # Wait for verification process
        except TimeoutException:
            print("No verification button found, proceeding...")
        except Exception as e:
            print(f"Error handling verification: {e}")

        # Wait for the content to load with multiple checks
        print("Waiting for content to load...")
        max_retries = 3
        retry_count = 0

        # Simple check for content presence
        time.sleep(2)  # Brief wait for initial load
        page_source = driver.page_source
        if "js_content" in page_source:
            print("Content found in page...")
        else:
            print("No content found in page, will retry...")
            retry_count = 0
            while retry_count < max_retries:
                try:
                    # Wait for content to be present and visible
                    content_present = WebDriverWait(driver, 5).until(
                        EC.visibility_of_element_located((By.ID, "js_content"))
                    )
                    break
                except TimeoutException:
                    retry_count += 1
                    print(f"Retry {retry_count}/{max_retries} for content loading...")
                    if retry_count == max_retries:
                        print("Max retries reached, failing...")
                        return None, None
                    time.sleep(1)

        # Get the page source after JavaScript has run
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

    except Exception as e:
        print(f"Error with Chrome browser: {e}")
        return None, None
    finally:
        try:
            driver.quit()
        except:
            pass

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

    # Extract main content
    content_div = soup.find('div', {'id': 'js_content'})
    if not content_div:
        print("No content div found in the page")
        print("Page content:", soup.prettify()[:500])  # Print first 500 chars of page
        return None, None

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
    links = open("links.txt", "r").readlines()
    wechat_url = "https://mp.weixin.qq.com/s?__biz=MzA5MDkxNTA4Ng==&amp;mid=2454912394&amp;idx=1&amp;sn=4250f2786cf472c0494078265913d5ec&amp;chksm=87a235ebb0d5bcfd3553c84fb9f045b475709dfcce025040b34f89b129dd9bb46808d6956c96&poc_token=HJ_Do2ejHyO-wNZGG8Q1S8FdPgy1YBBEob-nUEme"
    for link in links:
        wechat_url = link.strip()
        try:
            print(f"Extracting content from {wechat_url}...")
            markdown_output, filename = extract_content(wechat_url)
            if markdown_output:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(markdown_output)
                print(f"Markdown content saved to {filename}")
            else:
                print("Failed to extract content - no content returned")
        except TypeError as e:
            print(f"Failed to extract content - error: {e}")
