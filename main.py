import time
import argparse
import re
import csv
import os
from scraper import BlinkitAPIScraper
from processor import BlinkitProcessor

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

def main():
    parser = argparse.ArgumentParser(description="Blinkit Scraper and Processor")
    parser.add_argument("--input_dir", default="input", help="Directory containing input CSV files")
    parser.add_argument("--locations_file", default="blinkit_locations.csv", help="CSV file with location coordinates")
    parser.add_argument("--categories_file", default="blinkit_categories.csv", help="CSV file with categories to scrape")
    parser.add_argument("--scroll", type=int, default=15, help="Number of scroll actions to perform")
    parser.add_argument("--output_dir", default="blinkit_data", help="Directory to store the scraped data")
    parser.add_argument("--scrape_only", action="store_true", help="Only scrape the data, don't process")
    parser.add_argument("--process_only", action="store_true", help="Only process previously scraped data")
    
    args = parser.parse_args()
    
    # Construct full paths
    locations_path = os.path.join(args.input_dir, args.locations_file)
    categories_path = os.path.join(args.input_dir, args.categories_file)
    
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
    
    # Iterate through each location
    for location_idx, location in enumerate(locations, 1):
        try:
            lat = float(location.get("latitude", "").strip())
            lng = float(location.get("longitude", "").strip())
            
            print(f"\n--- Processing location {location_idx}/{len(locations)}: {lat}, {lng} ---")
            
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
                print(f"Category pattern: {category_pattern}")
                
                # Skip scraping if process_only flag is set
                if not args.process_only:
                    # Create a location-specific folder
                    location_dir = f"{args.output_dir}/lat_{lat}_lng_{lng}"
                    os.makedirs(location_dir, exist_ok=True)
                    
                    print(f"Starting scraper at location: {lat}, {lng}")
                    
                    # Initialize and run the scraper
                    scraper = BlinkitAPIScraper(url, lat=lat, lng=lng, output_dir=location_dir)
                    success = scraper.run(scroll_count=args.scroll)
                    
                    if not success:
                        print("Scraping failed. Check the logs for details.")
                        if not args.scrape_only:
                            print("Attempting to process any available data anyway...")
                    else:
                        print(f"Scraping completed successfully for this category.")
                        # Give some time for files to be fully written
                        time.sleep(2)
                
                # Skip processing if scrape_only flag is set
                if not args.scrape_only:
                    location_dir = f"{args.output_dir}/lat_{lat}_lng_{lng}"
                    processor = BlinkitProcessor(location_dir)
                    
                    print(f"Processing data for category: {category_pattern}")
                    csv_file = processor.process_category(category_pattern)
                    
                    if csv_file:
                        print(f"Processing completed. CSV file created: {csv_file}")
                    else:
                        print("Processing failed or no data found for the specified category.")
            
            # Optional: Add a delay between locations to prevent overloading the server
            if not args.process_only and location_idx < len(locations):
                print("Waiting 30 seconds before moving to the next location...")
                time.sleep(30)
                
        except ValueError as e:
            print(f"Invalid coordinates in location {location}: {str(e)}")
            continue
        except Exception as e:
            print(f"Error processing location {location}: {str(e)}")
            continue

if __name__ == "__main__":
    main()