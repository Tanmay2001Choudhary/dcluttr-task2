import time
import argparse
import re
import csv
import os
from scraper import BlinkitAPIScraper
from processor import BlinkitProcessor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def extract_category_name(url):
    """
    Extract category information from URL
    Format: l1_category_l2_category_l1_id_l2_id (e.g., munchies_bhujia-mixtures_1237_1178)
    """
    # Parse URL to extract category information
    pattern = r"/cn/([^/]+)/([^/]+)/cid/(\d+)/(\d+)"
    match = re.search(pattern, url)
    
    if match:
        l1_category = match.group(1)
        l2_category = match.group(2)
        l1_category_id = match.group(3)
        l2_category_id = match.group(4)
        
        return f"{l1_category}_{l2_category}_{l1_category_id}_{l2_category_id}"
    
    # Fallback if pattern doesn't match
    parts = url.split("/")
    parts = [p for p in parts if p]
    
    if len(parts) >= 2:
        return f"{parts[-2]}_{parts[-1]}"
    
    return "category"

def build_category_url(l1_category, l1_category_id, l2_category, l2_category_id):
    """
    Build the category URL from category components
    """
    l1_slug = l1_category.lower().replace(" ", "-")
    l2_slug = l2_category.lower().replace(" ", "-")
    return f"https://blinkit.com/cn/{l1_slug}/{l2_slug}/cid/{l1_category_id}/{l2_category_id}"

def read_csv_file(file_path):
    """Read data from a CSV file and return as a list of dictionaries"""
    if not os.path.exists(file_path):
        print(f"Error: File not found - {file_path}")
        return []
    
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                data.append(row)
        return data
    except Exception as e:
        print(f"Error reading {file_path}: {str(e)}")
        return []

def setup_driver():
    """Setup the Chrome driver with proper options for network monitoring"""
    options = Options()
    
    # Enable performance logging
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    
    # Make the browser less detectable
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--window-size=1920,1080")
    
    # Additional options for stability
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    
    # Uncomment to hide the browser
    options.add_argument("--headless")
    
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
        """
    })
    
    return driver

def main():
    parser = argparse.ArgumentParser(description="Blinkit Scraper and Processor")
    parser.add_argument("--input_dir", default="input", help="Directory containing input CSV files")
    parser.add_argument("--locations_file", default="blinkit_locations.csv", help="CSV file with location coordinates")
    parser.add_argument("--categories_file", default="blinkit_categories.csv", help="CSV file with categories to scrape")
    parser.add_argument("--scroll", type=int, default=15, help="Number of scroll actions to perform")
    parser.add_argument("--output_dir", default="blinkit_data", help="Directory to store the scraped data")
    parser.add_argument("--output_csv", default="blinkit_products.csv", help="Name of the CSV file to store all products")
    
    args = parser.parse_args()
    
    # Construct full paths
    locations_path = os.path.join(args.input_dir, args.locations_file)
    categories_path = os.path.join(args.input_dir, args.categories_file)
    output_csv_path = os.path.join(args.output_dir, args.output_csv)
    
    # Read locations and categories from CSV files
    locations = read_csv_file(locations_path)
    categories = read_csv_file(categories_path)
    
    if not locations:
        print(f"No locations found in {locations_path}. Exiting.")
        return
    
    if not categories:
        print(f"No categories found in {categories_path}. Exiting.")
        return
    
    print(f"Loaded {len(locations)} locations and {len(categories)} categories")
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Initialize a single browser session outside the loop
    driver = setup_driver()
    print("Browser session initialized")
    
    # Initialize a single processor for all data
    processor = BlinkitProcessor(args.output_dir)
    
    # Create or prepare the output CSV file with headers
    all_products_found = 0
    
    try:
        # Iterate through each location
        current_lat = None
        current_lng = None
        
        for location_idx, location in enumerate(locations, 1):
            try:
                lat = float(location.get("latitude", "").strip())
                lng = float(location.get("longitude", "").strip())
                
                print(f"\n--- Processing location {location_idx}/{len(locations)}: {lat}, {lng} ---")
                location_changed = (current_lat != lat or current_lng != lng)
                
                # Initialize the scraper only once, with the browser session
                if location_idx == 1:
                    # For first location, we need a URL to start with
                    initial_category = categories[0]
                    initial_url = build_category_url(
                        initial_category.get("l1_category", "").strip(),
                        initial_category.get("l1_category_id", "").strip(),
                        initial_category.get("l2_category", "").strip(),
                        initial_category.get("l2_category_id", "").strip()
                    )
                    scraper = BlinkitAPIScraper(initial_url, lat=lat, lng=lng, output_dir=args.output_dir, driver=driver)
                    # Navigate to the URL and set location
                    scraper.start_session()
                    location_changed = True
                elif location_changed:
                    # Update the scraper with new location
                    scraper.update_location(lat, lng)
                
                current_lat = lat
                current_lng = lng
                
                # Iterate through each category for this location
                for cat_idx, category in enumerate(categories, 1):
                    l1_category = category.get("l1_category", "").strip()
                    l1_category_id = category.get("l1_category_id", "").strip()
                    l2_category = category.get("l2_category", "").strip()
                    l2_category_id = category.get("l2_category_id", "").strip()
                    
                    if not all([l1_category, l1_category_id, l2_category, l2_category_id]):
                        print(f"Skipping incomplete category entry: {category}")
                        continue
                    
                    # Build the URL for this category
                    url = build_category_url(l1_category, l1_category_id, l2_category, l2_category_id)
                    category_pattern = f"{l1_category.lower().replace(' ', '_')}_{l2_category.lower().replace(' ', '_')}_{l1_category_id}_{l2_category_id}"
                    
                    print(f"\nCategory {cat_idx}/{len(categories)}: {l1_category} > {l2_category}")
                    print(f"URL: {url}")
                    
                    # Navigate to new category URL (doesn't change location)
                    scraper.navigate_to_category(url)
                    
                    # Scrape data for this category
                    success, api_data = scraper.scrape_category(scroll_count=args.scroll)
                    
                    if not success or not api_data:
                        print("Scraping failed or no data found. Check the logs for details.")
                        continue
                        
                    print(f"Scraped {len(api_data)} API responses for this category")
                    
                    # Process the data and update the CSV
                    category_info = {
                        'l1_category': l1_category,
                        'l1_category_id': l1_category_id,
                        'l2_category': l2_category,
                        'l2_category_id': l2_category_id
                    }
                    
                    products = processor.process_api_data(api_data, category_info, lat, lng)
                    all_products_found += len(products)
                    
                    if products:
                        processor.update_csv(products, output_csv_path)
                        print(f"Added {len(products)} products to {output_csv_path}")
                    else:
                        print("No products found for this category")
                
                # Optional: Add a delay between locations
                if location_idx < len(locations):
                    print("Waiting 5 seconds before moving to the next location...")
                    time.sleep(5)
                    
            except ValueError as e:
                print(f"Invalid coordinates in location {location}: {str(e)}")
                continue
            except Exception as e:
                print(f"Error processing location {location}: {str(e)}")
                import traceback
                print(traceback.format_exc())
                continue
        
        print(f"\nScraping completed! Total products found: {all_products_found}")
        print(f"All data has been saved to: {output_csv_path}")
        
    finally:
        # Ensure the browser is closed when done
        try:
            driver.quit()
            print("Browser session closed")
        except:
            pass

if __name__ == "__main__":
    main()