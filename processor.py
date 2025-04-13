import os
import json
import csv
import datetime
import re
import hashlib
from pathlib import Path

class BlinkitProcessor:
    def __init__(self, directory="blinkit_data"):
        self.directory = directory
        if not os.path.exists(directory):
            os.makedirs(directory)
    
    def find_category_files(self, category_pattern=None):
        """
        Find all category directories or response files in the data directory
        If category_pattern is provided, will only return files matching that pattern
        """
        all_files = list(Path(self.directory).glob("*_response_*.json"))
        
        if category_pattern:
            # Filter by category pattern
            matching_files = []
            pattern = re.compile(f"^{category_pattern}_response_")
            
            for file_path in all_files:
                if pattern.match(file_path.name):
                    matching_files.append(file_path)
            
            return matching_files
        
        # Group by category
        category_files = {}
        for file_path in all_files:
            parts = file_path.name.split("_response_")
            if len(parts) > 1:
                category = parts[0]
                if category not in category_files:
                    category_files[category] = []
                category_files[category].append(file_path)
        
        return category_files

    def generate_product_hash(self, product):
        """
        Generate a unique hash for a product based on its key attributes
        """
        # Create a string containing the key attributes that determine uniqueness
        unique_attrs = (
            f"{product.get('l1_category', '')}"
            f"{product.get('l2_category', '')}"
            f"{product.get('variant_id', '')}"
            f"{product.get('variant_name', '')}"
            f"{product.get('group_id', '')}"
            f"{product.get('selling_price', '')}"
            f"{product.get('mrp', '')}"
            f"{product.get('brand', '')}"
        )
        
        # Generate a hash of this string
        return hashlib.md5(unique_attrs.encode('utf-8')).hexdigest()

    def check_for_offer(self, product):
        """
        Determines if a product has an offer by checking multiple possible indicators
        """
        # For the "widgets" structure
        if product.get("is_offer", False):
            return True
        
        # Check price discount
        selling_price = str(product.get("selling_price", "0")).replace('₹', '').strip()
        mrp = str(product.get("mrp", "0")).replace('₹', '').strip()
        
        try:
            selling_price = float(selling_price) if selling_price else 0
            mrp = float(mrp) if mrp else 0
            if mrp > 0 and selling_price > 0 and selling_price < mrp:
                return True
        except ValueError:
            pass
        
        # For the "snippets" structure 
        if product.get("offer_tag") is not None:
            return True
            
        return False

    def parse_blinkit_json_files(self, files):
        """
        Parses specified JSON files and extracts product data.
        """
        unique_products = {}  # Dictionary to store unique products with hash as key
        processed_files = 0
        duplicates_found = 0
        
        print(f"Processing {len(files)} JSON files")
        
        for json_file in files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract timestamp from filename
                try:
                    file_name = os.path.basename(json_file)
                    timestamp_part = file_name.split('_response_')[1].split('_')[0]
                    date = datetime.datetime.fromtimestamp(int(timestamp_part))
                    date_str = date.strftime('%Y-%m-%d')
                except:
                    # Fallback to file creation time
                    date_str = datetime.datetime.fromtimestamp(os.path.getctime(json_file)).strftime('%Y-%m-%d')
                
                # Extract category information from filename
                file_name = os.path.basename(json_file)
                category_name = file_name.split("_response_")[0]
                
                # Default values for category information
                l1_category = ""
                l1_category_id = ""
                l2_category = ""
                l2_category_id = ""
                
                # Where munchies is l1_category, 1237 is l1_category_id, bhujia-mixtures is l2_category, 1178 is l2_category_id
                parts = category_name.split("_")
                if len(parts) >= 4:
                    l1_category = parts[0]
                    l1_category_id = parts[2]
                    l2_category = parts[1] 
                    l2_category_id = parts[3]
                elif len(parts) >= 2:
                    # Handle case where only main category is present
                    l1_category = parts[0]
                    l1_category_id = parts[1]
                
                # Parse products from widgets structure
                if "widgets" in data:
                    for widget in data["widgets"]:
                        if "products" in widget:
                            for product in widget["products"]:
                                # Extract product data
                                try:
                                    # Extract product details
                                    selling_price = product.get("price", {}).get("selling_price", "")
                                    mrp = product.get("price", {}).get("mrp", "")
                                    
                                    # Create basic product data
                                    product_data = {
                                        'date': date_str,
                                        'l1_category': l1_category,
                                        'l1_category_id': l1_category_id,
                                        'l2_category': l2_category,
                                        'l2_category_id': l2_category_id,
                                        'store_id': product.get("store_id", ""),
                                        'variant_id': product.get("id", ""),
                                        'variant_name': f"{product.get('name', '')} {product.get('variant', '')}".strip(),
                                        'group_id': product.get("group_id", ""),
                                        'selling_price': selling_price,
                                        'mrp': mrp,
                                        'in_stock': 'Yes' if product.get("is_in_stock", False) else 'No',
                                        'inventory': product.get("inventory", 0),
                                        'image_url': product.get("image_url", ""),
                                        'brand_id': product.get("brand_id", ""),
                                        'brand': product.get("brand", "")
                                    }
                                    
                                    # Check for offer - enhanced logic
                                    has_offer = False
                                    if product.get("is_offer", False):
                                        has_offer = True
                                    elif mrp and selling_price and float(mrp) > float(selling_price):
                                        has_offer = True
                                    
                                    product_data['is_offer'] = 'Yes' if has_offer else 'No'
                                    
                                    # Generate hash and check for duplicates
                                    product_hash = self.generate_product_hash(product_data)
                                    if product_hash not in unique_products:
                                        unique_products[product_hash] = product_data
                                    else:
                                        duplicates_found += 1
                                except Exception as e:
                                    print(f"Error processing product: {str(e)}")
                
                # Alternative structure (check for snippets format)
                elif 'response' in data and 'snippets' in data['response']:
                    for snippet in data['response']['snippets']:
                        if 'data' in snippet:
                            product_data = snippet['data']
                            
                            # Try to get category from common_attributes first
                            tracking_data = snippet.get('tracking', {}).get('common_attributes', {})
                            
                            # Keep original category info from filename
                            # Only replace if empty and there's data in the tracking info
                            if not l2_category and tracking_data.get('l2_category'):
                                l2_category = tracking_data.get('l2_category', '')
                            
                            if not l2_category_id and tracking_data.get('type_id'):
                                l2_category_id = str(tracking_data.get('type_id', ''))
                            
                            # Combine variant and name for variant_name
                            variant_text = product_data.get('variant', {}).get('text', '')
                            name_text = product_data.get('name', {}).get('text', '')
                            variant_name = f"{name_text} {variant_text}".strip()
                            
                            # Handle price extraction - properly extract numeric values
                            selling_price = product_data.get('normal_price', {}).get('text', '')
                            selling_price = selling_price.replace('₹', '').strip() if selling_price else ''
                            
                            # Handle MRP - some products might not have an MRP if not discounted
                            mrp = product_data.get('mrp', {}).get('text', '')
                            if not mrp:
                                # If MRP is not present, use the selling price as MRP
                                mrp = selling_price
                            else:
                                mrp = mrp.replace('₹', '').strip()
                            
                            # Determine if product has an offer
                            has_offer = False
                            
                            # Check for offer_tag
                            if product_data.get('offer_tag') is not None:
                                has_offer = True
                            # Check for price difference
                            elif mrp and selling_price and float(mrp) > float(selling_price):
                                has_offer = True
                            # Check direct offer property (even if null, we check other indicators)
                            elif product_data.get('offer') is not None and product_data.get('offer') is not False:
                                # The presence of 'offer' field might indicate an offer even if it's null
                                if product_data.get('offer') or mrp != selling_price:
                                    has_offer = True
                            
                            product = {
                                'date': date_str,
                                'l1_category': l1_category,
                                'l1_category_id': l1_category_id,
                                'l2_category': l2_category,
                                'l2_category_id': l2_category_id,
                                'store_id': product_data.get('merchant_id', ''),
                                'variant_id': product_data.get('product_id', ''),
                                'variant_name': variant_name,
                                'group_id': product_data.get('group_id', ''),
                                'selling_price': selling_price,
                                'mrp': mrp,
                                'in_stock': 'Yes' if not product_data.get('is_sold_out', True) else 'No',
                                'inventory': product_data.get('inventory', 0),
                                'is_offer': 'Yes' if has_offer else 'No',
                                'image_url': product_data.get('image', {}).get('url', ''),
                                'brand_id': '',  # Not directly available in the sample
                                'brand': product_data.get('brand_name', {}).get('text', '')
                            }
                            
                            # Generate hash and check for duplicates
                            product_hash = self.generate_product_hash(product)
                            if product_hash not in unique_products:
                                unique_products[product_hash] = product
                            else:
                                duplicates_found += 1
                
                processed_files += 1
                if processed_files % 10 == 0:
                    print(f"Processed {processed_files} files, found {duplicates_found} duplicates so far")
                    
            except Exception as e:
                print(f"Error processing file {json_file}: {str(e)}")
        
        # Convert dictionary values back to a list
        all_products = list(unique_products.values())
        
        print(f"Extracted {len(all_products)} unique products from {processed_files} files")
        print(f"Filtered out {duplicates_found} duplicate products")
        
        return all_products

    def save_to_csv(self, products, category_name=None):
        """
        Saves the extracted product data to a CSV file.
        """
        if not products:
            print("No products to save")
            return None
        
        # Create output filename
        if category_name:
            output_file = f"{self.directory}/{category_name}_products.csv"
        else:
            output_file = f"{self.directory}/blinkit_products_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Define field names for the CSV
        fieldnames = [
            'date', 'l1_category', 'l1_category_id', 'l2_category', 'l2_category_id',
            'store_id', 'variant_id', 'variant_name', 'group_id', 'selling_price',
            'mrp', 'in_stock', 'inventory', 'is_offer', 'image_url', 'brand_id', 'brand'
        ]
        
        # Write to CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(products)
        
        print(f"Saved {len(products)} unique products to {output_file}")
        return output_file
    
    def process_category(self, category_pattern=None):
        """
        Process a specific category or all categories if none specified
        """
        if category_pattern:
            # Process a specific category
            files = self.find_category_files(category_pattern)
            if not files:
                print(f"No files found for category pattern: {category_pattern}")
                return None
            
            print(f"Found {len(files)} files for category pattern: {category_pattern}")
            products = self.parse_blinkit_json_files(files)
            return self.save_to_csv(products, category_pattern)
        else:
            # Process all categories
            categories = self.find_category_files()
            results = {}
            
            for category, files in categories.items():
                print(f"\nProcessing category: {category} ({len(files)} files)")
                products = self.parse_blinkit_json_files(files)
                csv_file = self.save_to_csv(products, category)
                results[category] = {
                    'files_processed': len(files),
                    'products_extracted': len(products),
                    'csv_file': csv_file
                }
            
            return results
    
    def list_categories(self):
        """
        List all available categories in the data directory
        """
        categories = self.find_category_files()
        
        print(f"Found {len(categories)} categories:")
        for category, files in categories.items():
            print(f"- {category}: {len(files)} files")
        
        return list(categories.keys())