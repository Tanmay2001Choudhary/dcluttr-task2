import time
import json
import random
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

class BlinkitAPIScraper:
    def __init__(self, category_url, output_dir="blinkit_data"):
        """Initialize the scraper with the category URL"""
        self.category_url = category_url
        self.api_responses = []
        self.output_dir = output_dir
        self.category_name = self.extract_category_name(category_url)
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Create a log file
        self.log_file = f"{self.output_dir}/scraping_log_{self.category_name}.txt"
        with open(self.log_file, "w") as f:
            f.write(f"Scraping started for {category_url} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            
        self.setup_driver()
        
    def log(self, message):
        """Log a message to both console and log file"""
        print(message)
        with open(self.log_file, "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} - {message}\n")
    
    def extract_category_name(self, url):
        """
        Extract category information from URL
        Example: https://blinkit.com/cn/munchies/bhujia-mixtures/cid/1237/1178
        Format: l1_category_l2_category_l1_id_l2_id (e.g., munchies_bhujia-mixtures_1237_1178)
        """
        # Parse URL to extract category information
        pattern = r"/cn/([^/]+)/([^/]+)/cid/(\d+)/(\d+)"
        match = re.search(pattern, url)
        
        if match:
            l1_category = match.group(1)         # e.g., munchies
            l2_category = match.group(2)         # e.g., bhujia-mixtures
            l1_category_id = match.group(3)      # e.g., 1237
            l2_category_id = match.group(4)      # e.g., 1178
            
            # Create a category name with all components in desired format
            return f"{l1_category}_{l2_category}_{l1_category_id}_{l2_category_id}"
        
        # Fallback if pattern doesn't match
        parts = url.split("/")
        parts = [p for p in parts if p]  # Remove empty parts
        
        if len(parts) >= 2:
            return f"{parts[-2]}_{parts[-1]}"
        
        return "category"
        
    def setup_driver(self):
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
        
        # Uncomment to hide the browser
        # options.add_argument("--headless")
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
            """
        })
        self.log("WebDriver initialized with performance logging enabled")

    def extract_api_responses(self):
        """Extract API responses from browser logs"""
        logs = self.driver.get_log("performance")
        for log_entry in logs:
            try:
                log_data = json.loads(log_entry["message"])["message"]
                
                # Check if this is a Network response
                if "Network.responseReceived" in log_data["method"]:
                    response_url = log_data["params"]["response"]["url"]
                    
                    # Check if this is the API we're interested in
                    if "v1/layout/listing_widgets" in response_url:
                        request_id = log_data["params"]["requestId"]
                        self.log(f"Found API response: {response_url}")
                        
                        # Get the response body
                        try:
                            response_body = self.driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
                            if response_body and "body" in response_body:
                                # Parse the JSON response
                                try:
                                    json_data = json.loads(response_body["body"])
                                    self.api_responses.append({
                                        "url": response_url,
                                        "data": json_data,
                                        "request_id": request_id
                                    })
                                    self.log(f"Successfully captured API response data ({len(response_body['body'])} bytes)")
                                    
                                    # Save the response to a file
                                    self.save_response(json_data, request_id)
                                except json.JSONDecodeError:
                                    self.log(f"Error: Could not parse JSON response")
                        except Exception as e:
                            self.log(f"Error getting response body: {str(e)}")
            except Exception:
                # Silently ignore errors in processing log entries
                pass
    
    def save_response(self, response_data, request_id):
        """Save a single API response to a file"""
        timestamp = int(time.time())
        filename = f"{self.output_dir}/{self.category_name}_response_{timestamp}_{request_id[:8]}.json"
        with open(filename, "w") as f:
            json.dump(response_data, f, indent=2)
        self.log(f"Saved response to {filename}")
    
    def scroll_page(self, max_scrolls=15):
        """Scroll the page to trigger API requests"""
        self.log("Starting to scroll page to trigger API requests...")
        
        # Extract initial responses
        self.extract_api_responses()
        initial_response_count = len(self.api_responses)
        self.log(f"Initially found {initial_response_count} API responses")
        
        # Scroll several times with pauses
        scroll_count = 0
        consecutive_no_new = 0
        last_response_count = initial_response_count
        
        while scroll_count < max_scrolls and consecutive_no_new < 3:
            try:
                # First try to scroll specific container
                try:
                    self.driver.execute_script("""
                        var container = document.getElementById('plpContainer');
                        if (container) {
                            container.scrollTop += 800;
                        } else {
                            window.scrollBy(0, 800);
                        }
                    """)
                except Exception:
                    # Fall back to window scrolling
                    self.driver.execute_script("window.scrollBy(0, 800);")
                
                # Add random wait time to appear more human-like
                wait_time = 2 + random.uniform(0, 2)
                self.log(f"Scrolled and waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                
                # Extract API responses after scrolling
                self.extract_api_responses()
                current_response_count = len(self.api_responses)
                
                # Check if we've found new responses
                if current_response_count > last_response_count:
                    new_responses = current_response_count - last_response_count
                    self.log(f"Scroll {scroll_count+1}: Found {new_responses} new API responses")
                    last_response_count = current_response_count
                    consecutive_no_new = 0
                else:
                    consecutive_no_new += 1
                    self.log(f"Scroll {scroll_count+1}: No new responses ({consecutive_no_new}/3 consecutive)")
                
                scroll_count += 1
                
                # Add some random movements to appear more human-like
                if random.random() > 0.7:
                    # Move to a random product to simulate browsing
                    try:
                        # Use the updated product card selector
                        products = self.driver.find_elements(By.CSS_SELECTOR, "div > div > div[style*='grid-column: span']")
                        if products:
                            random_product = random.choice(products)
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", random_product)
                            self.log("Moved to a random product")
                            time.sleep(3)
                    except Exception as e:
                        self.log(f"Error with random movement: {str(e)}")
                
            except Exception as e:
                self.log(f"Error during scrolling: {str(e)}")
                break
        
        self.log(f"Scrolling complete after {scroll_count} scrolls. Captured {len(self.api_responses)} API responses")
    
    def run(self, scroll_count=15):
        """Main method to run the scraper"""
        try:
            self.log(f"Opening URL: {self.category_url}")
            self.driver.get(self.category_url)
            
            # Wait for the page to load using the container approach
            try:
                # First find the container with all products
                container = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.ID, "plpContainer"))
                )
                
                # Then find all product cards within the container
                product_cards = container.find_elements(By.CSS_SELECTOR, "div > div > div[style*='grid-column: span']")
                self.log(f"Page loaded successfully. Found {len(product_cards)} product cards")
                
                if len(product_cards) == 0:
                    self.log("No product cards found in the container, but continuing anyway")
            except TimeoutException:
                self.log("Product container not found on initial load, but continuing anyway")
            
            # Allow some time for initial API calls to complete
            time.sleep(10)
            
            # Scroll to trigger API requests
            self.scroll_page(max_scrolls=scroll_count)
            
            # Check if we captured any responses
            if not self.api_responses:
                self.log("Error: No API responses were captured!")
                return False
            
            self.log(f"Successfully collected {len(self.api_responses)} API response files")
            return True
            
        except Exception as e:
            self.log(f"Critical error occurred: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            return False
        finally:
            self.log("Closing WebDriver")
            self.driver.quit()