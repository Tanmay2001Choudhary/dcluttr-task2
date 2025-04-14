import os
import csv
import json
import pandas as pd
from datetime import datetime

class BlinkitProcessor:
    def __init__(self, output_dir="blinkit_data"):
        """Initialize the processor with output directory"""
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Track unique products to avoid duplicates
        self.unique_products = {}
    
    def generate_product_hash(self, product):
        """Generate a unique hash for a product based on key attributes"""
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
        
        import hashlib
        return hashlib.md5(unique_attrs.encode('utf-8')).hexdigest()
    
    def process_api_data(self, api_data, category_info, lat, lng):
        """
        Process API response data and extract product details
        
        Args:
            api_data: List of API response JSON data
            category_info: Dictionary containing category details
            lat: Latitude for this data
            lng: Longitude for this data
            
        Returns:
            List of extracted product dictionaries
        """
        products = []
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        l1_category = category_info.get('l1_category', '')
        l1_category_id = category_info.get('l1_category_id', '')
        l2_category = category_info.get('l2_category', '')
        l2_category_id = category_info.get('l2_category_id', '')
        
        # Process each API response
        for response_data in api_data:
            # Parse products from widgets structure
            if "widgets" in response_data:
                for widget in response_data["widgets"]:
                    if "products" in widget:
                        for product in widget["products"]:
                            # Extract product details
                            selling_price = product.get("price", {}).get("selling_price", "")
                            mrp = product.get("price", {}).get("mrp", "")
                            
                            # Create product data
                            product_data = {
                                'date': date_str,
                                'lat': lat,
                                'lng': lng,
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
                            
                            # Check for offer
                            has_offer = False
                            if product.get("is_offer", False):
                                has_offer = True
                            elif mrp and selling_price and float(mrp) > float(selling_price):
                                has_offer = True
                            
                            product_data['is_offer'] = 'Yes' if has_offer else 'No'
                            
                            # Generate hash and check for duplicates
                            product_hash = self.generate_product_hash(product_data)
                            if product_hash not in self.unique_products:
                                self.unique_products[product_hash] = True
                                products.append(product_data)
            
            # Alternative structure (check for snippets format)
            elif 'response' in response_data and 'snippets' in response_data['response']:
                for snippet in response_data['response']['snippets']:
                    if 'data' in snippet:
                        product_data = snippet['data']
                        
                        # Combine variant and name for variant_name
                        variant_text = product_data.get('variant', {}).get('text', '')
                        name_text = product_data.get('name', {}).get('text', '')
                        variant_name = f"{name_text} {variant_text}".strip()
                        
                        # Handle price extraction
                        selling_price = product_data.get('normal_price', {}).get('text', '')
                        selling_price = selling_price.replace('₹', '').strip() if selling_price else ''
                        
                        # Handle MRP 
                        mrp = product_data.get('mrp', {}).get('text', '')
                        if not mrp:
                            mrp = selling_price
                        else:
                            mrp = mrp.replace('₹', '').strip()
                        
                        # Determine if product has an offer
                        has_offer = False
                        if product_data.get('offer_tag') is not None:
                            has_offer = True
                        elif mrp and selling_price and float(mrp) > float(selling_price):
                            has_offer = True
                        elif product_data.get('offer') is not None and product_data.get('offer') is not False:
                            if product_data.get('offer') or mrp != selling_price:
                                has_offer = True
                        
                        product = {
                            'date': date_str,
                            'lat': lat,
                            'lng': lng,
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
                            'brand_id': '',
                            'brand': product_data.get('brand_name', {}).get('text', '')
                        }
                        
                        # Generate hash and check for duplicates
                        product_hash = self.generate_product_hash(product)
                        if product_hash not in self.unique_products:
                            self.unique_products[product_hash] = True
                            products.append(product)
        
        print(f"Processed {len(products)} unique products from API data")
        return products
    
    def update_csv(self, products, output_csv_path):
        """
        Update the CSV file with new product data
        
        Args:
            products: List of product dictionaries to add
            output_csv_path: Path to the CSV file
        """
        fieldnames = [
            'date', 'lat', 'lng', 'l1_category', 'l1_category_id', 'l2_category', 'l2_category_id',
            'store_id', 'variant_id', 'variant_name', 'group_id', 'selling_price',
            'mrp', 'in_stock', 'inventory', 'is_offer', 'image_url', 'brand_id', 'brand'
        ]
        
        # Create file with headers if it doesn't exist
        file_exists = os.path.exists(output_csv_path)
        
        with open(output_csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # Write header only if the file doesn't exist yet
            if not file_exists:
                writer.writeheader()
            
            # Write all product rows
            for product in products:
                writer.writerow(product)
    
    def process_csv(self, input_csv=None):
        """
        Process the CSV file with all products
        If input_csv is None, uses the default blinkit_products.csv
        """
        if input_csv is None:
            input_csv = f"{self.output_dir}/blinkit_products.csv"
        
        if not os.path.exists(input_csv):
            print(f"CSV file not found: {input_csv}")
            return None
        
        try:
            # Load the CSV into pandas DataFrame
            df = pd.read_csv(input_csv)
            
            print(f"Loaded {len(df)} product records from {input_csv}")
            
            # Generate summary statistics
            summary = self.generate_summary(df)
            
            # Save summary to CSV
            summary_file = f"{self.output_dir}/blinkit_summary.csv"
            summary.to_csv(summary_file, index=False)
            print(f"Saved summary to {summary_file}")
            
            return {
                'records_processed': len(df),
                'summary_file': summary_file
            }
            
        except Exception as e:
            print(f"Error processing CSV file: {str(e)}")
            return None
    
    def generate_summary(self, df):
        """
        Generate summary statistics for the scraped data
        """
        # Group by location (lat, lng) and category
        location_summary = df.groupby(['lat', 'lng']).agg({
            'variant_id': 'nunique',
            'is_offer': lambda x: (x == 'Yes').sum()
        }).reset_index()
        
        location_summary.columns = ['latitude', 'longitude', 'unique_products', 'products_with_offers']
        
        # Calculate percentage of products with offers
        location_summary['offer_percentage'] = (location_summary['products_with_offers'] / location_summary['unique_products'] * 100).round(2)
        
        return location_summary
    
    def analyze_price_variations(self, input_csv=None):
        """
        Analyze price variations for the same product across different locations
        """
        if input_csv is None:
            input_csv = f"{self.output_dir}/blinkit_products.csv"
        
        if not os.path.exists(input_csv):
            print(f"CSV file not found: {input_csv}")
            return None
        
        try:
            # Load the CSV into pandas DataFrame
            df = pd.read_csv(input_csv)
            
            # Group by product ID and check for price variations
            price_variations = df.groupby('variant_id').agg({
                'variant_name': 'first',
                'selling_price': lambda x: x.nunique(),
                'lat': 'nunique'
            }).reset_index()
            
            # Filter to only products with price variations and multiple locations
            price_variations = price_variations[
                (price_variations['selling_price'] > 1) & 
                (price_variations['lat'] > 1)
            ]
            
            # Sort by number of price variations
            price_variations = price_variations.sort_values('selling_price', ascending=False)
            
            # Save to CSV
            if len(price_variations) > 0:
                variations_file = f"{self.output_dir}/price_variations.csv"
                price_variations.to_csv(variations_file, index=False)
                print(f"Saved price variations to {variations_file}")
                return variations_file
            else:
                print("No price variations found across locations")
                return None
            
        except Exception as e:
            print(f"Error analyzing price variations: {str(e)}")
            return None
    
    def analyze_offer_patterns(self, input_csv=None):
        """
        Analyze offer patterns across locations
        """
        if input_csv is None:
            input_csv = f"{self.output_dir}/blinkit_products.csv"
        
        if not os.path.exists(input_csv):
            print(f"CSV file not found: {input_csv}")
            return None
        
        try:
            # Load the CSV into pandas DataFrame
            df = pd.read_csv(input_csv)
            
            # Group by category and location
            offer_patterns = df.groupby(['l1_category', 'l2_category', 'lat', 'lng']).agg({
                'variant_id': 'count',
                'is_offer': lambda x: (x == 'Yes').sum()
            }).reset_index()
            
            # Calculate offer percentage
            offer_patterns['offer_percentage'] = (offer_patterns['is_offer'] / offer_patterns['variant_id'] * 100).round(2)
            offer_patterns.columns = ['l1_category', 'l2_category', 'lat', 'lng', 'product_count', 'offers_count', 'offer_percentage']
            
            # Save to CSV
            pattern_file = f"{self.output_dir}/offer_patterns.csv"
            offer_patterns.to_csv(pattern_file, index=False)
            print(f"Saved offer patterns to {pattern_file}")
            return pattern_file
            
        except Exception as e:
            print(f"Error analyzing offer patterns: {str(e)}")
            return None