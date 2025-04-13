import time
import json
import random
import os
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.support.expected_conditions import staleness_of
from geopy.geocoders import Nominatim

class BlinkitAPIScraper:
    def __init__(self, category_url, lat=None, lng=None, output_dir="blinkit_data"):
        """
        Initialize the scraper with the category URL and location coordinates
        
        Args:
            category_url (str): URL of the category to scrape
            lat (float): Latitude for location setting
            lng (float): Longitude for location setting
            output_dir (str): Directory to save output files
        """
        self.category_url = category_url
        self.lat = lat
        self.lng = lng
        self.api_responses = []
        self.output_dir = output_dir
        self.category_name = self.extract_category_name(category_url)
        
        # Initialize geolocator for address lookup
        self.geolocator = Nominatim(user_agent="blinkit_api_scraper")
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Create a log file
        self.log_file = f"{self.output_dir}/scraping_log_{self.category_name}.txt"
        with open(self.log_file, "w") as f:
            f.write(f"Scraping started for {category_url} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            if lat and lng:
                f.write(f"Using location coordinates: {lat}, {lng}\n")
            
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
        
        # Additional options for stability
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        
        # Uncomment to hide the browser
        options.add_argument("--headless")
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
            """
        })
        self.log("WebDriver initialized with performance logging enabled")
        
    def get_address_from_coordinates(self, lat, lon):
        """Get address from coordinates using geopy"""
        try:
            location = self.geolocator.reverse(f"{lat}, {lon}")
            return location.address
        except Exception as e:
            self.log(f"Error getting address from coordinates: {str(e)}")
            return "Unknown location"

    def set_location(self):
        """Set location using latitude and longitude with retry mechanism"""
        if not self.lat or not self.lng:
            self.log("No location coordinates provided. Skipping location setting.")
            return True
            
        self.log(f"Setting location to coordinates: {self.lat}, {self.lng}")
        
        # Get address to search
        address = self.get_address_from_coordinates(self.lat, self.lng)
        self.log(f"Searching for address: {address}")
        
        # Add retry mechanism
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Wait for page to load fully
                time.sleep(5)
                
                # Try different possible selectors for the location button
                location_button = None
                possible_button_selectors = [
                    ".LocationBar__Container-sc-x8ezho-6",
                    ".LocationBar__Container",
                    "[data-testid='location-button']",
                    "//div[contains(text(), 'Deliver to')]",
                    "//button[contains(@class, 'LocationBar')]"
                ]
                
                for selector in possible_button_selectors:
                    try:
                        self.log(f"Trying selector: {selector}")
                        if selector.startswith("//"):
                            # XPath selector
                            location_button = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                        else:
                            # CSS selector
                            location_button = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                        if location_button:
                            self.log(f"Found location button with selector: {selector}")
                            break
                    except:
                        continue
                
                if not location_button:
                    # Fallback: Try to find any element that looks like a location button
                    self.log("Trying to find location button by text content...")
                    elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Deliver') or contains(text(), 'Location')]")
                    for element in elements:
                        self.log(f"Potential location element found: {element.text}")
                        if ("deliver" in element.text.lower() or "location" in element.text.lower()):
                            location_button = element
                            break
                
                if not location_button:
                    # Last resort: take a screenshot to debug
                    screenshot_path = f"{self.output_dir}/debug_screenshot_{int(time.time())}.png"
                    self.driver.save_screenshot(screenshot_path)
                    self.log(f"Could not find location button. Screenshot saved as {screenshot_path}")
                    
                    if attempt < max_retries - 1:
                        self.log(f"Retrying location setting (attempt {attempt+1}/{max_retries})...")
                        continue
                    return False
                
                # Click location button with better handling
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", location_button)
                time.sleep(0.5)  # Small pause before clicking
                self.driver.execute_script("arguments[0].click();", location_button)
                time.sleep(2)  # Wait for modal to appear
                
                # Wait for search input with various possible selectors
                search_input = None
                possible_input_selectors = [
                    "input[name='select-locality']",
                    "input[placeholder*='search delivery location']",
                    "input[placeholder*='location']",
                    ".LocationSearchBox__InputSelect",
                    "//input[contains(@placeholder, 'location')]"
                ]
                
                for selector in possible_input_selectors:
                    try:
                        self.log(f"Trying input selector: {selector}")
                        if selector.startswith("//"):
                            # XPath selector
                            search_input = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                        else:
                            # CSS selector
                            search_input = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                        if search_input:
                            self.log(f"Found search input with selector: {selector}")
                            break
                    except:
                        continue
                
                if not search_input:
                    screenshot_path = f"{self.output_dir}/location_modal_{int(time.time())}.png"
                    self.driver.save_screenshot(screenshot_path)
                    self.log(f"Could not find search input. Screenshot saved as {screenshot_path}")
                    
                    if attempt < max_retries - 1:
                        self.log(f"Retrying location setting (attempt {attempt+1}/{max_retries})...")
                        continue
                    return False
                
                # Clear and enter address with improved handling
                search_input.clear()
                time.sleep(0.3)
                
                # Type slowly and wait for elements to respond
                query_text = address.split(',')[0].strip()
                self.log(f"Typing search query: {query_text}")
                
                for char in query_text:
                    try:
                        search_input.send_keys(char)
                        time.sleep(0.1)
                    except StaleElementReferenceException:
                        self.log("Search input became stale, trying to find it again...")
                        # Try to find the input element again
                        for selector in possible_input_selectors:
                            try:
                                if selector.startswith("//"):
                                    search_input = WebDriverWait(self.driver, 5).until(
                                        EC.element_to_be_clickable((By.XPATH, selector))
                                    )
                                else:
                                    search_input = WebDriverWait(self.driver, 5).until(
                                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                                    )
                                if search_input:
                                    search_input.clear()
                                    search_input.send_keys(query_text)  # Send the full query at once
                                    break
                            except:
                                continue
                        break  # Break out of the character loop
                
                # Wait longer for search results to appear
                time.sleep(3)
                
                # Try different possible selectors for search results
                results_found = False
                possible_results_selectors = [
                    ".LocationSearchList__LocationDetailContainer-sc-93rfr7-1",
                    ".LocationSearchList__LocationDetailContainer",
                    "[data-testid='location-search-result']",
                    "//div[contains(@class, 'LocationSearch')]",
                    "//div[contains(text(), 'Delhi') or contains(text(), 'New Delhi')]"
                ]
                
                for selector in possible_results_selectors:
                    try:
                        self.log(f"Trying results selector: {selector}")
                        if selector.startswith("//"):
                            # XPath selector
                            search_results = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_all_elements_located((By.XPATH, selector))
                            )
                        else:
                            # CSS selector
                            search_results = WebDriverWait(self.driver, 5).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                            )
                        
                        if search_results and len(search_results) > 0:
                            self.log(f"Found {len(search_results)} search results with selector: {selector}")
                            # Click the first result with better handling
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", search_results[0])
                            time.sleep(0.5)  # Pause before clicking
                            self.driver.execute_script("arguments[0].click();", search_results[0])
                            results_found = True
                            break
                    except Exception as e:
                        self.log(f"Error with selector {selector}: {str(e)}")
                        continue
                
                if not results_found:
                    screenshot_path = f"{self.output_dir}/search_results_{int(time.time())}.png"
                    self.driver.save_screenshot(screenshot_path)
                    self.log(f"No location results found or could not click. Screenshot saved as {screenshot_path}")
                    
                    # Last resort: Try to send Enter key to select the first result
                    try:
                        search_input.send_keys("\n")
                        time.sleep(5)
                        
                        # Check if page changed (location might have been set)
                        if "?latitude=" in self.driver.current_url or "visibility?latitude=" in self.driver.current_url:
                            self.log("Location might have been set via Enter key")
                            return True
                    except:
                        self.log("Enter key approach failed")
                    
                    if attempt < max_retries - 1:
                        self.log(f"Retrying location setting (attempt {attempt+1}/{max_retries})...")
                        continue
                    return False
                
                # Wait for page to reload with new location
                # Use longer wait time and check for page change
                wait_start = time.time()
                max_wait = 10  # seconds
                location_set = False
                
                while time.time() - wait_start < max_wait:
                    if "?latitude=" in self.driver.current_url or "visibility?latitude=" in self.driver.current_url:
                        location_set = True
                        break
                    time.sleep(1)
                
                if location_set:
                    self.log("Location set successfully - confirmed via URL parameters")
                else:
                    self.log("Waiting for page reload after location selection...")
                    time.sleep(5)
                
                return True
            
            except StaleElementReferenceException as e:
                self.log(f"Stale element encountered during location setting: {str(e)}")
                if attempt < max_retries - 1:
                    self.log(f"Retrying location setting (attempt {attempt+1}/{max_retries})...")
                    time.sleep(2)  # Wait before retrying
                else:
                    screenshot_path = f"{self.output_dir}/error_screenshot_{int(time.time())}.png"
                    self.driver.save_screenshot(screenshot_path)
                    self.log(f"Max retries reached with stale elements. Screenshot saved as {screenshot_path}")
                    return False
                    
            except Exception as e:
                screenshot_path = f"{self.output_dir}/error_screenshot_{int(time.time())}.png"
                self.driver.save_screenshot(screenshot_path)
                self.log(f"Error setting location: {str(e)}")
                self.log(f"Error screenshot saved as {screenshot_path}")
                
                if attempt < max_retries - 1:
                    self.log(f"Retrying location setting (attempt {attempt+1}/{max_retries})...")
                    time.sleep(2)  # Wait before retrying
                else:
                    return False
        
        return False  # Should not reach here but just in case

    def extract_api_responses(self):
        """Extract API responses from browser logs with immediate processing"""
        try:
            # Process logs immediately to avoid missing data
            logs = self.driver.get_log("performance")
            
            # Track which requests we've already processed
            processed_request_ids = set()
            
            for log_entry in logs:
                try:
                    log_data = json.loads(log_entry["message"])["message"]
                    
                    # Check if this is a Network response
                    if "Network.responseReceived" in log_data["method"]:
                        response_url = log_data["params"]["response"]["url"]
                        
                        # Check if this is the API we're interested in
                        if "v1/layout/listing_widgets" in response_url:
                            request_id = log_data["params"]["requestId"]
                            
                            # Skip if we've already processed this request
                            if request_id in processed_request_ids:
                                continue
                                
                            processed_request_ids.add(request_id)
                            self.log(f"Found API response: {response_url}")
                            
                            # Immediate response processing
                            try:
                                # Don't wait too long - process immediately
                                response_body = self.driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
                                
                                if response_body and "body" in response_body:
                                    # Parse the JSON response
                                    try:
                                        json_data = json.loads(response_body["body"])
                                        
                                        # Create a minimal response object to save memory
                                        api_response = {
                                            "url": response_url,
                                            "request_id": request_id,
                                            "timestamp": int(time.time()),
                                            "location": {"lat": self.lat, "lng": self.lng} if self.lat and self.lng else None
                                        }
                                        
                                        self.api_responses.append(api_response)
                                        self.log(f"Successfully captured API response data ({len(response_body['body'])} bytes)")
                                        
                                        # Save the response to a file immediately
                                        self.save_response(json_data, request_id)
                                        
                                    except json.JSONDecodeError:
                                        self.log(f"Error: Could not parse JSON response")
                            except Exception as e:
                                self.log(f"Error getting response body: {str(e)}")
                                # Continue to the next log entry instead of breaking
                except Exception as e:
                    # Silently ignore errors in processing log entries
                    pass
        except Exception as e:
            self.log(f"Error in extract_api_responses: {str(e)}")
    
    def save_response(self, response_data, request_id):
        """Save a single API response to a file with improved organization"""
        timestamp = int(time.time())
        
        # Create category directory if it doesn't exist
        category_dir = f"{self.output_dir}/{self.category_name}"
        if not os.path.exists(category_dir):
            os.makedirs(category_dir)
            self.log(f"Created category directory: {category_dir}")
        
        # Format location for filename if available
        loc_part = f"lat{self.lat}_lng{self.lng}" if self.lat and self.lng else "default_location"
        
        # Create a cleaner filename
        filename = f"{category_dir}/{loc_part}_{timestamp}.json"
        
        # Add location data to the response
        if self.lat and self.lng:
            if not isinstance(response_data, dict):
                response_data = {"original_data": response_data}
            response_data["_meta"] = {
                "latitude": self.lat,
                "longitude": self.lng,
                "timestamp": timestamp,
                "address": self.get_address_from_coordinates(self.lat, self.lng),
                "category_url": self.category_url,
                "category_name": self.category_name
            }
        
        try:
            with open(filename, "w") as f:
                json.dump(response_data, f, indent=2)
            self.log(f"Saved response to {filename}")
        except Exception as e:
            self.log(f"Error saving response to file: {str(e)}")
    
    def scroll_page(self, max_scrolls=15):
        """Scroll the page to trigger API requests with better error handling"""
        self.log("Starting to scroll page to trigger API requests...")
        
        # Clear logs before starting to prevent capturing old responses
        try:
            self.driver.get_log("performance")
        except:
            pass
            
        # Extract initial responses
        self.extract_api_responses()
        initial_response_count = len(self.api_responses)
        self.log(f"Initially found {initial_response_count} API responses")
        
        # Find the container once to verify it exists
        try:
            container = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "plpContainer"))
            )
            self.log("Found product container for scrolling")
        except TimeoutException:
            self.log("Warning: Product container not found. Will use window scrolling.")
            
        # Scroll several times with pauses
        scroll_count = 0
        consecutive_no_new = 0
        last_response_count = initial_response_count
        
        while scroll_count < max_scrolls and consecutive_no_new < 3:
            try:
                # Take screenshot every few scrolls for debugging
                if scroll_count % 3 == 0:
                    self.driver.save_screenshot(f"{self.output_dir}/scroll_{scroll_count}.png")
                
                # First try container scrolling with better handling
                try:
                    self.driver.execute_script("""
                        var container = document.getElementById('plpContainer');
                        if (container) {
                            // Save current scroll position
                            var oldScroll = container.scrollTop;
                            
                            // Scroll by 500px each time
                            container.scrollTop += 500;
                            
                            // Return whether we actually scrolled
                            return container.scrollTop > oldScroll;
                        } else {
                            return false;
                        }
                    """)
                except Exception:
                    # Fall back to window scrolling
                    self.driver.execute_script("window.scrollBy(0, 500);")
                
                # Add random wait time to appear more human-like
                wait_time = 3 + random.uniform(0, 1)  # Increased minimum wait time
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
                
                # Add some random movements to appear more human-like, but less frequently
                if random.random() > 0.8:  # Reduced frequency
                    # Move to a random product to simulate browsing
                    try:
                        # Use the updated product card selector
                        products = self.driver.find_elements(By.CSS_SELECTOR, "div > div > div[style*='grid-column: span']")
                        if products and len(products) > 0:
                            random_product = random.choice(products)
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", random_product)
                            self.log("Moved to a random product")
                            time.sleep(2)  # Reduced wait time
                    except Exception as e:
                        self.log(f"Error with random movement: {str(e)}")
                
            except Exception as e:
                self.log(f"Error during scrolling: {str(e)}")
                # Don't break the loop on error - continue to next scroll attempt
                time.sleep(1)
        
        self.log(f"Scrolling complete after {scroll_count} scrolls. Captured {len(self.api_responses)} API responses")
    
    def run(self, scroll_count=15):
        """Main method to run the scraper with improved error handling"""
        try:
            self.log(f"Opening URL: {self.category_url}")
            self.driver.get(self.category_url)
            
            # Set location if coordinates are provided - with retry mechanism
            if self.lat and self.lng:
                location_success = self.set_location()
                if not location_success:
                    self.log("Warning: Failed to set location. Continuing with default location.")
                else:
                    self.log("Successfully set location. Page should be refreshed with products for this location.")
                    # Add additional wait after location change
                    time.sleep(5)
            else:
                self.log("No location coordinates provided. Using default location.")
            
            # Wait for the page to load with improved error handling
            container_found = False
            try:
                # First find the container with all products
                container = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.ID, "plpContainer"))
                )
                container_found = True
                
                # Then find all product cards within the container
                product_cards = container.find_elements(By.CSS_SELECTOR, "div > div > div[style*='grid-column: span']")
                self.log(f"Page loaded successfully. Found {len(product_cards)} product cards")
                
                # Take screenshot to verify page loaded correctly
                screenshot_path = f"{self.output_dir}/page_loaded_{int(time.time())}.png"
                self.driver.save_screenshot(screenshot_path)
                self.log(f"Page screenshot saved as {screenshot_path}")
                
                if len(product_cards) == 0:
                    self.log("No product cards found in the container, but continuing anyway")
            except TimeoutException:
                self.log("Product container not found on initial load, trying alternative approaches")
                
                # Try alternative ways to check if page loaded
                try:
                    # Check for any products or content
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div[style*='grid-column: span']"))
                    )
                    self.log("Found product elements using alternative selector")
                    container_found = True
                except:
                    self.log("Could not find products with alternative selector")
            
            if not container_found:
                self.log("Warning: Could not confirm page loaded successfully, but continuing anyway")
                self.driver.save_screenshot(f"{self.output_dir}/no_container_{int(time.time())}.png")
            
            # Allow more time for initial API calls to complete
            self.log("Waiting for initial API calls to complete...")
            time.sleep(10)
            
            # Clear performance logs before scrolling to ensure we only get new responses
            try:
                self.driver.get_log("performance")
            except:
                pass
            
            # Scroll to trigger API requests
            self.scroll_page(max_scrolls=scroll_count)
            
            # Check if we captured any responses
            if not self.api_responses:
                self.log("Warning: No API responses were captured!")
                
                # Try to force a page refresh and try again
                self.log("Refreshing page to attempt capture again...")
                self.driver.refresh()
                time.sleep(10)
                self.scroll_page(max_scrolls=5)  # Shorter scroll session
                
                if not self.api_responses:
                    self.log("Error: Still no API responses after refresh")
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