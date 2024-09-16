import csv
import os
import uuid
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time
import tldextract  # Import tldextract for accurate domain extraction
from concurrent.futures import ThreadPoolExecutor, as_completed


# Path to the chromedriver executable
CHROMEDRIVER_PATH = 'chromedriver-win64\chromedriver.exe'

def download_image(image_url, file_extension):
    try:
        # Generate a unique filename using uuid
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join('logos', unique_filename)
        
        # Download the image
        response = requests.get(image_url, stream=True)
        if response.status_code == 200:
            # Save the image
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            return unique_filename  # Return the saved filename
        else:
            print(f"Failed to download image from {image_url}")
            return None
    except Exception as e:
        print(f"Error downloading image from {image_url}: {e}")
        return None

def fetch_logo_image_urls(url):
    # Initialize the Selenium WebDriver (Chrome in this case)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Runs Chrome in headless mode (no UI)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Initialize the browser driver
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    try:
        # Open the website
        driver.get(url)
        
        # Wait for the page to load (this is a basic wait, you can enhance it to wait for specific elements)
        time.sleep(3)  # Give time for the page to fully load
        
        # Once the SPA has loaded, we get the page source
        html = driver.page_source
        
        # Parse the page source with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract the domain name from the URL using tldextract
        extracted = tldextract.extract(url)
        domain = extracted.domain  # This will extract 'yave' from 'dev.yave.mx', 'stage.dev.yave.mx', etc.
        
        # Search for all <nav> elements and <div> elements with "nav" in class or attributes
        nav_elements = soup.find_all('nav')  # Get all <nav> elements regardless of class
        nav_elements += soup.find_all('header')  # Get all <nav> elements regardless of class
     
        all_images = soup.find_all('img')[::-1]
        
        logo_url = ""
        nav_logo_url = ""
        nav_svg_logo = ""

        for img in all_images:
            img_url = img.get('src')
            img_class = img.get('class', [])
            img_alt = img.get('alt', '').lower()

            # Check if 'logo' or the domain name is in the class name, alt text, or URL
            if img_url and ('logo' in img_url.lower() and domain.lower() in img_url.lower()):
                logo_url = img_url

        # Look for <img> tags inside the found <nav> or <div> elements
        for nav in nav_elements:
            images = nav.find_all('img')[::-1]  # Reverse the image list

            for img in images:
                img_url = img.get('src')
                img_class = img.get('class', [])
                img_alt = img.get('alt', '').lower()

                # Check if 'logo' or the domain name is in the class name, alt text, or URL
                if img_url and ('logo' in img_url.lower() and domain.lower() in img_url.lower()):
                    nav_logo_url = img_url
                elif any('logo' in cls.lower() for cls in img_class):
                    nav_logo_url = img_url
                elif 'logo' in img_alt:
                    nav_logo_url = img_url

            # Check for SVG with the domain name in class or attributes
            svgs = nav.find_all('svg')
            for svg in svgs:
                svg_class = svg.get('class', [])
                svg_attrs = " ".join(f"{k}={v}" for k, v in svg.attrs.items()).lower()

                # Check if the domain name is in the class or attributes of the SVG
                if domain.lower() in svg_attrs or any(domain.lower() in cls.lower() for cls in svg_class):
                    nav_svg_logo = str(svg)  # Store the SVG as a string representation

        # Determine which image to download (if any)
        image_to_save = None
        if nav_logo_url:
            image_to_save = nav_logo_url
        elif nav_svg_logo:
            image_to_save = nav_svg_logo
        elif logo_url:
            image_to_save = logo_url

        image_filename = None

        if image_to_save and not nav_svg_logo:
            file_extension = os.path.splitext(image_to_save.lower())[-1]  # Get the file extension (e.g., .png, .jpg)
            if not file_extension:  # Handle cases without extension
                file_extension = '.png'
            if file_extension in ('.png', '.gif', '.jpg', '.jpeg', '.jfif', '.pjpeg', '.pjp', '.webp', '.svg', '.tiff', '.tif', '.apng', '.avif', '.bmp', '.ico'):
                image_filename = download_image(image_to_save, file_extension)
        elif nav_svg_logo:  # If it's an SVG
            svg_filename = f"{uuid.uuid4()}.svg"
            svg_file_path = os.path.join('logos', svg_filename)
            with open(svg_file_path, 'w', encoding='utf-8') as file:
                file.write(nav_svg_logo)
            image_filename = svg_filename

        # Return the URLs and the saved image filename
        return {url: {"nav_logo_url": nav_logo_url, "nav_svg_logo": nav_svg_logo, "logo_url": logo_url, "image_file_name": image_filename}}

    except Exception as e:
        print(f"Error for {url}: {e}")
        return {url: None}

    finally:
        # Close the browser after scraping
        driver.quit()

# Function to handle parallel fetching
def fetch_multiple_urls(urls, max_workers=8, output_file='logo_results.csv'):
    results = []
    
    # Using ThreadPoolExecutor to fetch URLs in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit each URL to be processed by the fetch_logo_image_urls function
        future_to_url = {executor.submit(fetch_logo_image_urls, url): url for url in urls}
        
        # As each task completes, store its result
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                results.append(result)
                append_results_to_csv([result], output_file)
            except Exception as e:
                print(f"Error fetching {url}: {e}")

    return results


def read_urls_from_file(file_path):
    try:
        with open(file_path, 'r') as file:
            # Read each line, strip any leading/trailing spaces, and ignore empty lines
            urls = [line.strip() for line in file.readlines() if line.strip()]
        return urls
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        return []


def append_results_to_csv(results, output_file):
    try:
        # Open the CSV file in append mode ('a')
        with open(output_file, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            
            # Append the data without headers
            for result in results:
                if result:
                    for url, data in result.items():
                        if data:
                            writer.writerow([
                                url, 
                                data.get('nav_logo_url', ''), 
                                data.get('nav_svg_logo', ''), 
                                data.get('logo_url', ''),
                                data.get('image_file_name', '')
                            ])
        print(f"Results appended to {output_file}")
    except Exception as e:
        print(f"Error appending results to CSV: {e}")


# Example usage
urls = read_urls_from_file('urls.txt')


if urls:
    # Fetch the logo images and SVG logos from all URLs in parallel
    results = fetch_multiple_urls(urls, max_workers=8)

    for result in results:
      print(result)

    # Save the results to a CSV file
    # append_results_to_csv(results, 'logo_results.csv')