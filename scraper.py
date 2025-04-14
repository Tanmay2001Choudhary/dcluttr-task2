import time
import json
import random
import os
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from geopy.geocoders import Nominatim

class BlinkitAPIScraper:
    def __init__(self, initial_url, lat=None, lng=None, output_dir="blinkit_data", driver=None):
        self.output_dir = output_dir
        self.api_responses = []
        self.current_lat = lat
        self.current_lng = lng
        self.current_category_name = None
        self.current_category_url = initial_url
        self.driver = driver
        
        # Initialize geolocator for address lookup
        self.geolocator = Nominatim(user_agent="blinkit_api_scraper")
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def start_session(self):
        """Initialize the session by navigating to the initial URL"""
        print(f"Starting session with URL: {self.current_category_url}")
        self.driver.get(self.current_category_url)
        
        # Wait for the page to load
        time.sleep(10)
        
        # Set location if coordinates were provided
        if self.current_lat and self.current_lng:
            self.set_location(self.current_lat, self.current_lng)
    
    def extract_category_name(self, url):
        pattern = r"/cn/([^/]+)/([^/]+)/cid/(\d+)/(\d+)"
        match = re.search(pattern, url)
        
        if match:
            l1_category = match.group(1)
            l2_category = match.group(2)
            l1_category_id = match.group(3)
            l2_category_id = match.group(4)
            
            return {
                "name": f"{l1_category}_{l2_category}_{l1_category_id}_{l2_category_id}",
                "l1_category": l1_category,
                "l2_category": l2_category,
                "l1_category_id": l1_category_id,
                "l2_category_id": l2_category_id
            }
        
        # Fallback if pattern doesn't match
        parts = url.split("/")
        parts = [p for p in parts if p]
        
        if len(parts) >= 2:
            return {
                "name": f"{parts[-2]}_{parts[-1]}",
                "l1_category": parts[-2],
                "l2_category": parts[-1],
                "l1_category_id": "",
                "l2_category_id": ""
            }
        
        return {
            "name": "category",
            "l1_category": "",
            "l2_category": "",
            "l1_category_id": "",
            "l2_category_id": ""
        }
        
    def get_address_from_coordinates(self, lat, lon):
        """Get address from coordinates using geopy"""
        try:
            location = self.geolocator.reverse(f"{lat}, {lon}")
            return location.address
        except Exception as e:
            print(f"Error getting address from coordinates: {str(e)}")
            return "Unknown location"

    def set_location(self, lat, lng):
        """Set location using latitude and longitude"""
        # Skip if location is already set to these coordinates
        if self.current_lat == lat and self.current_lng == lng:
            print(f"Location already set to {lat}, {lng}")
            return True
            
        print(f"Setting location to coordinates: {lat}, {lng}")
        self.current_lat = lat
        self.current_lng = lng
        
        # Get address to search
        address = self.get_address_from_coordinates(lat, lng)
        print(f"Searching for address: {address}")
        
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
                    break
            except:
                continue
        
        if not location_button:
            # Fallback: Try to find any element that looks like a location button
            elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Deliver') or contains(text(), 'Location')]")
            for element in elements:
                if ("deliver" in element.text.lower() or "location" in element.text.lower()):
                    location_button = element
                    break
        
        if not location_button:
            print("Could not find location button")
            return False
        
        # Click location button
        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", location_button)
        time.sleep(0.5)
        self.driver.execute_script("arguments[0].click();", location_button)
        time.sleep(2)
        
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
                if selector.startswith("//"):
                    search_input = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    search_input = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                if search_input:
                    break
            except:
                continue
        
        if not search_input:
            print("Could not find search input")
            return False
        
        # Clear and enter address
        search_input.clear()
        time.sleep(0.3)
        
        # Type search query
        query_text = address.split(',')[0].strip()
        print(f"Typing search query: {query_text}")
        search_input.send_keys(query_text)
        
        # Wait for search results to appear
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
                if selector.startswith("//"):
                    search_results = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_all_elements_located((By.XPATH, selector))
                    )
                else:
                    search_results = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                    )
                
                if search_results and len(search_results) > 0:
                    # Click the first result
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", search_results[0])
                    time.sleep(0.5)
                    self.driver.execute_script("arguments[0].click();", search_results[0])
                    results_found = True
                    break
            except:
                continue
        
        if not results_found:
            # Last resort: Try to send Enter key
            try:
                search_input.send_keys("\n")
                time.sleep(5)
            except:
                pass
        
        # Wait for page to reload with new location
        time.sleep(10)
        
        # Verify location was set by checking URL parameters
        if "?latitude=" in self.driver.current_url or "visibility?latitude=" in self.driver.current_url:
            print("Location set successfully")
            return True
        else:
            print("Could not confirm location was set")
            return False

    def update_location(self, lat, lng):
        """Update location for an existing session"""
        return self.set_location(lat, lng)

    def extract_api_responses(self):
        """Extract API responses from browser logs"""
        api_data = []
        
        try:
            # Get network logs
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
                            
                            # Get response body
                            response_body = self.driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
                            
                            if response_body and "body" in response_body:
                                # Parse the JSON response
                                json_data = json.loads(response_body["body"])
                                api_data.append(json_data)
                except:
                    continue
                    
        except Exception as e:
            print(f"Error extracting API responses: {str(e)}")
            
        return api_data
    
    def scroll_page(self, max_scrolls=25):
        """Scroll the page to trigger API requests and return the API responses"""
        print("Starting to scroll page to trigger API requests...")
        
        # Extract initial responses (important for pages with few products)
        initial_api_data = self.extract_api_responses()
        print(f"Initially found {len(initial_api_data)} API responses")
        
        # Use a dictionary to track unique API responses by URL to avoid duplicates
        api_responses_by_url = {}
        for response in initial_api_data:
            # Create a unique key for this response based on available data
            response_key = self._create_response_key(response)
            if response_key not in api_responses_by_url:
                api_responses_by_url[response_key] = response
        
        # Initialize pagination tracking
        more_pages_exist = True
        total_pagination_items = None
        last_pagination_url = None
        
        # Check if we have pagination info already
        for response in initial_api_data:
            if 'response' in response and 'pagination' in response['response']:
                if 'next_url' in response['response']['pagination']:
                    more_pages_exist = True
                    last_pagination_url = response['response']['pagination']['next_url']
                else:
                    # No next_url means we're on the last page already
                    more_pages_exist = False
                    print("No pagination URL found in initial response - might be single page")
                
            # Look for total_pagination_items in the response
            if 'response' in response and 'pagination' in response['response'] and 'next_url' in response['response']['pagination']:
                pagination_url = response['response']['pagination']['next_url']
                # Extract total_pagination_items from URL if present
                match = re.search(r'total_pagination_items=(\d+)', pagination_url)
                if match:
                    total_pagination_items = int(match.group(1))
                    print(f"Found total_pagination_items: {total_pagination_items}")
        
        # Find the container to verify it exists
        container_exists = False
        try:
            container = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "plpContainer"))
            )
            print("Found product container for scrolling")
            container_exists = True
        except TimeoutException:
            print("Warning: Product container not found. Will use window scrolling.")
        
        # Scroll several times with pauses
        scroll_count = 0
        consecutive_no_new = 0
        max_consecutive_no_new = 5
        last_response_count = len(api_responses_by_url)
        
        while more_pages_exist and scroll_count < max_scrolls and consecutive_no_new < max_consecutive_no_new:
            try:
                # If we know for sure there's no more pages, exit immediately
                if not more_pages_exist:
                    print("Stopped scrolling: No more pagination URLs found")
                    break
               # Calculate scroll distance that increases with each iteration
                base_scroll = 800
                scroll_distance = base_scroll + (scroll_count * 800)  # Increases by 200px each scroll

                # Apply to both container and window scrolling
                if container_exists:
                    self.driver.execute_script(f"""
                        var container = document.getElementById('plpContainer');
                        if (container) {{
                            container.scrollTop += {scroll_distance};
                            return true;
                        }} else {{
                            return false;
                        }}
                    """)
                else:
                    # Fall back to window scrolling
                    self.driver.execute_script(f"window.scrollBy(0, {scroll_distance});")
                
                # Wait after scrolling - slightly longer wait for better page loading
                wait_time = 4 + random.uniform(0, 1.5)
                time.sleep(wait_time)
                                
                # Wait for network to become idle before continuing
                try:
                    self.driver.execute_script("""
                        return new Promise(resolve => {
                            const checkNetworkIdle = () => {
                                const pending = performance.getEntriesByType('resource')
                                    .filter(r => !r.responseEnd && r.name.includes('listing_widgets'));
                                if (pending.length === 0) {
                                    resolve(true);
                                } else {
                                    setTimeout(checkNetworkIdle, 500);
                                }
                            };
                            checkNetworkIdle();
                        });
                    """)
                except:
                    # Fallback - just wait additional time
                    time.sleep(3)
                    
                # Extract API responses after scrolling
                new_api_data = self.extract_api_responses()
                
                # Process and deduplicate new responses
                for response in new_api_data:
                    response_key = self._create_response_key(response)
                    if response_key not in api_responses_by_url:
                        api_responses_by_url[response_key] = response
                
                # Check for pagination info in all responses
                more_pages_exist = False  # Reset flag, will set to True if we find valid next_url
                for response in api_responses_by_url.values():
                    if 'response' in response and 'pagination' in response['response']:
                        # Case 1: No next_url means we're on the last page
                        if 'next_url' not in response['response']['pagination']:
                            continue
                            
                        # Case 2: We have a next_url to check
                        new_pagination_url = response['response']['pagination']['next_url']
                        
                        # Only count as a new pagination if URL is different
                        if new_pagination_url != last_pagination_url:
                            # Check if we've already processed all items
                            entities_match = re.search(r'total_entities_processed=(\d+)', new_pagination_url)
                            total_match = re.search(r'total_pagination_items=(\d+)', new_pagination_url)
                            page_index_match = re.search(r'page_index=(\d+)', new_pagination_url)
                            
                            if entities_match and total_match:
                                entities = int(entities_match.group(1))
                                total = int(total_match.group(1))
                                
                                if entities >= total:
                                    print(f"Reached all products: {entities}/{total}")
                                    more_pages_exist = False
                                    break
                            
                            if page_index_match and total_match:
                                page_index = int(page_index_match.group(1))
                                total_items = int(total_match.group(1))
                                items_per_page = 15  # Based on limit=15 in URL
                                
                                total_pages = (total_items + items_per_page - 1) // items_per_page
                                if page_index >= total_pages - 1:
                                    print(f"Detected last pagination page: {page_index+1} of {total_pages}")
                                    more_pages_exist = False
                                    break
                            
                            # If we got here, we have a valid new pagination URL
                            more_pages_exist = True
                            last_pagination_url = new_pagination_url
                            
                            # Update total_pagination_items if available
                            if total_match:
                                new_total = int(total_match.group(1))
                                if total_pagination_items is None or new_total > total_pagination_items:
                                    total_pagination_items = new_total
                                    print(f"Updated total_pagination_items: {total_pagination_items}")
                        else:
                            # If we see the same pagination URL repeatedly, it's likely we're at the end
                            pass
                
                # Check if we've found new API responses
                current_response_count = len(api_responses_by_url)
                if current_response_count > last_response_count:
                    new_responses = current_response_count - last_response_count
                    print(f"Scroll {scroll_count+1}: Found {new_responses} new API responses, total: {current_response_count}")
                    last_response_count = current_response_count
                    consecutive_no_new = 0
                else:
                    consecutive_no_new += 1
                    print(f"Scroll {scroll_count+1}: No new responses ({consecutive_no_new}/{max_consecutive_no_new} consecutive)")
                
                # Occasional random product movement (helps trigger lazy loading)
                if random.random() > 0.7:
                    try:
                        products = self.driver.find_elements(By.CSS_SELECTOR, "div > div > div[style*='grid-column: span']")
                        if products and len(products) > 0:
                            random_product = random.choice(products)
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", random_product)
                            time.sleep(2)
                    except Exception as e:
                        print(f"Error selecting random product: {str(e)}")
                        pass
                        
                scroll_count += 1
                
            except Exception as e:
                print(f"Error during scrolling: {str(e)}")
                time.sleep(1)
        
        # Final check for reason we stopped scrolling
        if not more_pages_exist:
            print("Stopped scrolling: No more pagination URLs found")
        elif consecutive_no_new >= max_consecutive_no_new:
            print(f"Stopped scrolling: No new data after {max_consecutive_no_new} consecutive attempts")
        else:
            print(f"Stopped scrolling: Reached maximum scroll limit ({max_scrolls})")
            
        print(f"Scrolling complete after {scroll_count} scrolls. Captured {len(api_responses_by_url)} unique API responses")
        return list(api_responses_by_url.values())

    def _create_response_key(self, response):
        """Create a unique key for an API response to avoid duplicates"""
        # If response has a pagination URL, use that as it's unique
        if 'response' in response and 'pagination' in response['response'] and 'next_url' in response['response']['pagination']:
            return response['response']['pagination']['next_url']
        
        # If response has postback params with shown_product_count, use that
        if 'postback_params' in response and 'shown_product_count' in response['postback_params']:
            return f"products_{response['postback_params']['shown_product_count']}"
        
        # If we have tracking data with an ID, use that
        if 'response' in response and 'tracking' in response['response'] and 'le_meta' in response['response']['tracking']:
            if 'id' in response['response']['tracking']['le_meta']:
                return f"tracking_{response['response']['tracking']['le_meta']['id']}"
        
        # Last resort, use string representation of the response
        import hashlib
        return hashlib.md5(str(response).encode()).hexdigest()

    def navigate_to_category(self, category_url):
        """Navigate to a category URL"""
        print(f"Navigating to category URL: {category_url}")
        self.current_category_url = category_url
        self.current_category_name = self.extract_category_name(category_url)["name"]
        self.driver.get(category_url)
        
        # Wait for the page to load
        time.sleep(10)
        
        # Check if products loaded
        try:
            container = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "plpContainer"))
            )
            product_cards = container.find_elements(By.CSS_SELECTOR, "div > div > div[style*='grid-column: span']")
            print(f"Page loaded successfully. Found {len(product_cards)} product cards")
            return True
        except:
            print("Warning: Could not confirm page loaded successfully, but continuing anyway")
            return True
    
    def scrape_category(self, scroll_count=25):
        """Scrape the current category"""
        # Scroll to trigger API requests
        api_data = self.scroll_page(max_scrolls=scroll_count)
        return True, api_data