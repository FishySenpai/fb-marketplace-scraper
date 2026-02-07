import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime

# Pricing reference from your image (Maximum 10,000 mileage)
BIKE_PRICE_REFERENCE = {
    "Yamaha YZF-R1": {
        2017: 10445, 2018: 11550, 2019: 12360, 2020: 12460, 2021: 12825,
        2022: 12960, 2023: 13435, 2024: 14745, 2025: 15360
    },
    "Honda CBR1000rr": {
        2017: 8390, 2018: 9540, 2019: 10175, 2020: 10500, 2021: 11030,
        2022: 11545, 2023: 12010, 2024: 12315, 2025: 12830
    },
    "Suzuki GSXR 1000r ABS": {
        2017: 10310, 2018: 10310, 2019: 10665, 2020: 11110, 2021: 11570,
        2022: 12000, 2023: 12630, 2024: 13300, 2025: 13845
    },
    "Suzuki GSXR 1000": {
        2017: 8110, 2018: 8885, 2019: 9570, 2020: 10240, 2021: 10515,
        2022: 10730, 2023: 11225, 2024: 11865, 2025: 12360
    },
    "Kawasaki Ninja ZX10R ABS": {
        2017: 8500, 2018: 8875, 2019: 9270, 2020: 10125, 2021: 11085,
        2022: 11680, 2023: 13435, 2024: 14010, 2025: 14750
    },
    "Kawasaki Ninja ZX10R": {
        2017: 7980, 2018: 8330, 2019: 8670, 2020: 9680, 2021: 10460,
        2022: 11680, 2023: 12700, 2024: 13450, 2025: 14750
    },
    "Kawasaki Ninja ZX6r ABS": {
        2017: 6640, 2018: 6925, 2019: 6755, 2020: 7340, 2021: 7400,
        2022: 8135, 2023: 8765, 2024: 9615, 2025: 10015
    },
    "Kawasaki Ninja ZX6r": {
        2017: 6120, 2018: 6390, 2019: 6150, 2020: 6675, 2021: 6900,
        2022: 7230, 2023: 8020, 2024: 8715, 2025: 9080
    },
    "BMW S1000rr": {
        2017: 11470, 2018: 11810, 2019: 12235, 2020: 12475, 2021: 13325,
        2022: 14260, 2023: 15190, 2024: 16280, 2025: 16825
    },
    "Suzuki Hayabusa 1300": {
        2017: 8590, 2018: 8870, 2019: 9300, 2020: 9705, 2021: 10600,
        2022: 11565, 2023: 13070, 2024: 13720, 2025: 14465
    },
    "Ducati Panigale V4S": {
        2017: 11000, 2018: 13855, 2019: 14400, 2020: 14780, 2021: 15450,
        2022: 17905, 2023: 19525, 2024: 20735, 2025: 22820
    },
    "Ducati Panigale V4": {
        2017: 9175, 2018: 9175, 2019: 10950, 2020: 11450, 2021: 12000,
        2022: 12375, 2023: 14770, 2024: 15740, 2025: 17170
    },
    "Ducati Panigale V2": {
        2020: 8585, 2021: 8960, 2022: 10150, 2023: 11425, 2024: 12235, 2025: 12480
    }
}

# Questions to ask sellers
SELLER_QUESTIONS = [
    "Is the bike Clean Title? Has it ever been in an accident?",
    "Has the bike ever been dropped on the ground?",
    "Is the title in your hand or with a bank?",
]

async def save_login_session():
    """Run once to login and save session"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto('https://www.facebook.com/login')
        print("Please login manually...")
        await page.wait_for_timeout(60000)
        
        await context.storage_state(path='fb_session.json')
        print("Session saved!")
        await browser.close()

def extract_year_from_title(title):
    """Extract year from listing title"""
    import re
    years = re.findall(r'\b(20\d{2}|19\d{2})\b', title)
    if years:
        year = int(years[0])
        if 2010 <= year <= 2025:
            return year
    return None

def extract_price_value(price_text):
    """Convert price text to integer"""
    try:
        return int(price_text.replace('$', '').replace(',', '').split()[0])
    except:
        return None

def is_good_deal(bike_model, year, asking_price, price_tolerance=0.8):
    """
    Check if the price is a good deal based on reference prices
    price_tolerance: 0.8 means asking price should be <= 80% of reference price
    """
    if bike_model not in BIKE_PRICE_REFERENCE:
        return False, None, "Model not in reference table"
    
    if year not in BIKE_PRICE_REFERENCE[bike_model]:
        return False, None, f"Year {year} not in reference table"
    
    reference_price = BIKE_PRICE_REFERENCE[bike_model][year]
    max_acceptable_price = reference_price * price_tolerance
    
    if asking_price <= max_acceptable_price:
        savings = reference_price - asking_price
        return True, reference_price, f"Good deal! ${savings:,} below reference (${reference_price:,})"
    else:
        difference = asking_price - max_acceptable_price
        return False, reference_price, f"Overpriced by ${difference:,.0f} (Ref: ${reference_price:,})"

async def scrape_bike_prices(bike_models, filters=None):
    """
    Scrape motorcycle prices with filters
    filters = {
        'min_year': 2020,
        'max_year': 2024,
        'max_price': 12000,
        'price_tolerance': 0.8,  # 80% of reference price
        'max_results_per_bike': 10
    }
    """
    if filters is None:
        filters = {
            'min_year': 2017,
            'max_year': 2025,
            'max_price': 20000,
            'price_tolerance': 0.8,
            'max_results_per_bike': 10
        }
    
    results = []
    good_deals = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state='fb_session.json')
        page = await context.new_page()
        
        for bike in bike_models:
            print(f"\n{'='*60}")
            print(f"Searching for: {bike}")
            print(f"{'='*60}")
            
            search_url = f"https://www.facebook.com/marketplace/seattle/search?query={bike.replace(' ', '%20')}"
            await page.goto(search_url)
            await page.wait_for_timeout(3000)
            
            # Scroll to load results
            for _ in range(3):
                await page.evaluate('window.scrollBy(0, 1000)')
                await page.wait_for_timeout(2000)
            
            listings = await page.locator('a[href*="/marketplace/item/"]').all()
            
            for i, listing in enumerate(listings[:filters['max_results_per_bike']]):
                try:
                    # Get link first
                    link = await listing.get_attribute('href')
                    full_link = f"https://www.facebook.com{link}"
                    
                    # Get all text content from the listing
                    all_spans = await listing.locator('span').all()
                    texts = []
                    for span in all_spans[:5]:  # Check first 5 spans
                        text = await span.inner_text()
                        texts.append(text)
                    
                    # Find title (longest non-price text) and price
                    title = None
                    price_text = "N/A"
                    
                    for text in texts:
                        if '$' in text and not title:
                            price_text = text
                        elif len(text) > 10 and not text.startswith('$'):
                            title = text
                            break
                    
                    if not title:
                        title = texts[0] if texts else "Unknown"
                    
                    # Extract year and price
                    year = extract_year_from_title(title)
                    price_value = extract_price_value(price_text)
 
                    
                    # Apply filters
                    if year and (year < filters['min_year'] or year > filters['max_year']):
                        continue
                    
                    if price_value and price_value > filters['max_price']:
                        continue
                    
                    # Check if it's a good deal
                    is_deal = False
                    deal_info = "N/A"
                    reference_price = None
                    
                    if year and price_value:
                        is_deal, reference_price, deal_info = is_good_deal(
                            bike, year, price_value, filters['price_tolerance']
                        )
                    
                    listing_data = {
                        'bike_model': bike,
                        'year': year,
                        'title': title,
                        'asking_price': price_text,
                        'asking_price_value': price_value,
                        'reference_price': reference_price,
                        'is_good_deal': is_deal,
                        'deal_analysis': deal_info,
                        'link': full_link,
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    results.append(listing_data)
                    
                    # Print result with color coding
                    status = "✓ GOOD DEAL" if is_deal else "× Pass"
                    print(f"\n  {status}")
                    print(f"  Title: {title}")
                    print(f"  Year: {year if year else 'Unknown'}")
                    print(f"  Price: {price_text}")
                    print(f"  Analysis: {deal_info}")
                    
                    if is_deal:
                        good_deals.append(listing_data)
                    
                except Exception as e:
                    print(f"  Error extracting listing: {e}")
                    continue
            
            await page.wait_for_timeout(2000)
        
        await browser.close()
    
    return results, good_deals

async def main():
    # First time: uncomment to login and save session
    # await save_login_session()
    
    # Define your filters
    filters = {
        'min_year': 2017,           # Bikes from 2017 or newer (matches your pricing table)
        'max_year': 2025,           # Up to 2025 (matches your pricing table)
        'max_price': 15000,         # Maximum asking price
        'price_tolerance': 0.80,    # Only show bikes at 80% or less of reference price
        'max_results_per_bike': 10  # Max listings per bike model
    }
    
    bike_models = [
        # "Yamaha YZF-R1",
        "Honda CBR1000rr",
        # "Suzuki GSXR 1000r ABS",
        # "Kawasaki Ninja ZX10R ABS",
        # "Kawasaki Ninja ZX6r ABS",
    ]
    
    print(f"\n{'='*60}")
    print(f"FILTER SETTINGS:")
    print(f"  Year Range: {filters['min_year']}-{filters['max_year']}")
    print(f"  Max Price: ${filters['max_price']:,}")
    print(f"  Price Tolerance: {filters['price_tolerance']*100}% of reference")
    print(f"{'='*60}\n")
    
    results, good_deals = await scrape_bike_prices(bike_models, filters)
    
    # Save all results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f'all_bikes_{timestamp}.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Save only good deals
    with open(f'good_deals_{timestamp}.json', 'w') as f:
        json.dump(good_deals, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"SUMMARY:")
    print(f"  Total listings scraped: {len(results)}")
    print(f"  Good deals found: {len(good_deals)}")
    print(f"\n  Questions to ask sellers:")
    for i, q in enumerate(SELLER_QUESTIONS, 1):
        print(f"  {i}) {q}")
    print(f"{'='*60}\n")
    
    # Display good deals
    if good_deals:
        print("\nGOOD DEALS TO CONTACT:\n")
        for deal in good_deals:
            print(f"  {deal['bike_model']} ({deal['year']})")
            print(f"  Price: {deal['asking_price']} (Ref: ${deal['reference_price']:,})")
            print(f"  {deal['deal_analysis']}")
            print(f"  Link: {deal['link']}\n")

if __name__ == "__main__":
    asyncio.run(main())