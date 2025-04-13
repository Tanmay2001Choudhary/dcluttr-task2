import time
import argparse
import re
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

def main():
    parser = argparse.ArgumentParser(description="Blinkit Scraper and Processor")
    parser.add_argument("--url", help="URL of the category to scrape", required=True)
    parser.add_argument("--scroll", type=int, default=15, help="Number of scroll actions to perform")
    parser.add_argument("--output_dir", default="blinkit_data", help="Directory to store the scraped data")
    parser.add_argument("--scrape_only", action="store_true", help="Only scrape the data, don't process")
    parser.add_argument("--process_only", action="store_true", help="Only process previously scraped data")
    
    args = parser.parse_args()
    
    # Extract category name from URL
    category_pattern = extract_category_name(args.url)
    print(f"Using category pattern: {category_pattern}")
    
    # Run scraper if not process_only
    if not args.process_only:
        print(f"Starting scraper for URL: {args.url}")
        scraper = BlinkitAPIScraper(args.url, output_dir=args.output_dir)
        success = scraper.run(scroll_count=args.scroll)
        
        if not success:
            print("Scraping failed. Check the logs for details.")
            if not args.scrape_only:
                print("Attempting to process any available data anyway...")
        else:
            print(f"Scraping completed successfully.")
            # Give some time for files to be fully written
            time.sleep(2)
    
    # Run processor if not scrape_only
    if not args.scrape_only:
        processor = BlinkitProcessor(args.output_dir)
        
        if category_pattern:
            print(f"Processing data for category pattern: {category_pattern}")
            csv_file = processor.process_category(category_pattern)
            
            if csv_file:
                print(f"Processing completed. CSV file created: {csv_file}")
            else:
                print("Processing failed or no data found for the specified category.")
        else:
            print("Processing all available categories...")
            results = processor.process_category()
            if results:
                print("Processing completed for all categories.")
                for category, result in results.items():
                    print(f"- {category}: {result['products_extracted']} products, CSV: {result['csv_file']}")
            else:
                print("No categories found to process.")

if __name__ == "__main__":
    main()