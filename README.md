# Blinkit Category Scraper

📝 **Note**  
*First time trying web scraping with a **hybrid approach** (merged two techniques). Updated on **14th April 2025***  

---

### 🔄 Update Log:

- ✅ **Completed** automated data scraping for all **locations** and **categories** one-by-one.
- Faced 403 Forbidden errors when trying direct API calling despite correct headers.
- Selenium-only scraping was incomplete and more complex.
- ✅ **Chose hybrid approach**:
  - Used **Selenium** to simulate user interaction.
  - Monitored network tab for specific **API hit**, captured JSON response.
  - Parsed JSON and saved important fields to `.csv` files.

---

### 📁 Second Update:
- Generated **separate `.csv` files** for each category-location combination.

---

### ✅ Final Status:
- All combinations scraped and organized.
- Merged all data into **one single `blinkit_data.csv`** for easy access and analysis.

---

## Project Description

This is a web scraping tool to extract product data from Blinkit's website across multiple categories and locations using a hybrid Selenium + API approach.

## Task Status

- ✅ **Scraping and CSV Generation**: Fully completed  
- ✅ All category-location combinations handled  
- ✅ Final merged output file generated  

## How to Run

Install dependencies and run the script:

```bash
pip install selenium
python main.py --url "https://blinkit.com/cn/munchies/bhujia-mixtures/cid/1237/1178"
