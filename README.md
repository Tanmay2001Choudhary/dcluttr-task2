# Blinkit Category Scraper

This project is a web scraping tool designed to extract product data from Blinkit's website. Due to time constraints, the current implementation scrapes data for **only one random location** and **only one category**.

## Task Status

- **Task 1 (Scraping and CSV Generation)**: Fully completed
- **Limitations**: 
  - Scraping is currently limited to one category and one random location.
  - Due to the time crunch (assignment received at **11:00 AM**, and had to complete quickly), I’m actively working on expanding the code for multiple categories and dynamic location selection.
  - Web scraping itself took significant time, but the script successfully generates the output in CSV format.

## How to Run

Make sure you have Python installed and required dependencies (like `requests`, `bs4`, etc.)

Run the script using:

```bash
  pip install selenium
  python main.py --url "https://blinkit.com/cn/munchies/bhujia-mixtures/cid/1237/1178"
