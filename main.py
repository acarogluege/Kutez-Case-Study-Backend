from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import requests
import json

app = FastAPI()

# Add CORS middleware 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

# CONFIGURATION 
PRODUCTS_JSON_PATH = "products.json"
PORT = 8080

METAL_PRICE_API_KEY = "502324f8597df9a275ce0a2d328e7bb2"
GOLD_PRICE_API_URL = "https://api.metalpriceapi.com/v1/latest"

# HELPER FUNCTIONS 
def get_real_time_gold_price() -> float:
    """
    Fetch the real-time gold price from Metal Price API.
    Returns price per gram of gold in USD.
    """
    try:
        params = {
            "api_key": METAL_PRICE_API_KEY,
            "base": "USD",
            "currencies": "XAU"
        }
        response = requests.get(GOLD_PRICE_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("success", False):
            raise Exception(f"API Error: {data.get('error', {}).get('message', 'Unknown error')}")
            
        gold_price_per_ounce = 1 / data["rates"]["XAU"]  # Convert from XAU/USD to USD/XAU
        gold_price_per_gram = gold_price_per_ounce / 31.1034768
        return gold_price_per_gram
    except Exception as e:
        print(f"Error fetching gold price: {e}")
        return 60.0  # fallback value


def calculate_price(popularity_score: float, weight: float, gold_price: float) -> float:
    return (popularity_score + 1) * weight * gold_price


def load_products():
    with open(PRODUCTS_JSON_PATH, "r") as f:
        return json.load(f)


# ROUTES 
@app.get("/products")
def get_products(
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    min_popularity: Optional[int] = Query(None, description="Minimum popularityScore"),
    max_popularity: Optional[int] = Query(None, description="Maximum popularityScore"),
) -> List[dict]:
    """
    Retrieves product data, calculates the price dynamically using a real-time gold price
    """
    products_data = load_products()
    gold_price = get_real_time_gold_price()

    # Calculate dynamic price for each product
    for product in products_data:
        product["price"] = calculate_price(
            popularity_score=product["popularityScore"],
            weight=product["weight"],
            gold_price=gold_price
        )

        # Convert popularityScore to a 5-star scale and round to nearest 0.5
        score_out_of_5 = round(product["popularityScore"] * 5 * 2) / 2
        product["popularityScoreFormatted"] = score_out_of_5
        print(score_out_of_5)

    # Filtering products based on optional query parameters
    filtered_products = []
    for product in products_data:
        # Price filter
        if min_price is not None and product["price"] < min_price:
            continue
        if max_price is not None and product["price"] > max_price:
            continue
        # Popularity filter
        if min_popularity is not None and product["popularityScore"] < min_popularity:
            continue
        if max_popularity is not None and product["popularityScore"] > max_popularity:
            continue

        filtered_products.append(product)

    return filtered_products


@app.get("/products/{product_name}")
def get_product_by_name(product_name: str) -> dict:
    """
    Retrieve a single product by its name.
    """
    products_data = load_products()
    gold_price = get_real_time_gold_price()

    for product in products_data:
        if product["name"].lower() == product_name.lower():
            product["price"] = calculate_price(
                popularity_score=product["popularityScore"],
                weight=product["weight"],
                gold_price=gold_price
            )
            score_out_of_5 = (product["popularityScore"] * 5 * 2) / 2
            product["popularityScoreFormatted"] = round(score_out_of_5, 1)
            return product

    raise HTTPException(status_code=404, detail="Product not found")


@app.get("/")
def root():
    return {"message": "Welcome to the Product API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
