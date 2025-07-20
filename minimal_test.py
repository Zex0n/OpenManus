#!/usr/bin/env python3
"""
Minimal test of universal marketplace analyzer
Shows concept without real dependencies
"""

import json
from typing import Dict, Optional


def simulate_llm_analysis(url: str, html: str) -> dict:
    """Simulates LLM analysis of marketplace structure"""

    # Simulate different responses for different sites
    if "ozon.ru" in url:
        return {
            "success": True,
            "confidence": 0.95,
            "page_type": "search",
            "marketplace_structure": {
                "marketplace_name": "OZON",
                "base_url": "https://www.ozon.ru",
                "search": {
                    "search_input_selector": "input[placeholder*='Search']",
                    "search_button_selector": "button[type='submit']",
                    "search_form_selector": "form.search",
                },
                "product": {
                    "container_selector": "[data-widget='searchResultsV2'] > div",
                    "title_selector": "span.tsBody500Medium",
                    "price_selector": "span.c35_3_1-a1.tsHeadline500Medium",
                    "link_selector": "a[href*='/product/']",
                    "image_selector": "img[alt]",
                    "rating_selector": "div[data-widget*='webRating']",
                    "discount_selector": ".discount",
                },
                "product_page": {
                    "title_selector": "h1",
                    "price_selector": "span[data-widget*='webPrice']",
                    "description_selector": "div[data-widget*='webDescription']",
                    "specifications_selector": "div[data-widget*='webCharacteristics']",
                    "images_selector": ".product-images img",
                    "availability_selector": ".availability",
                    "buy_button_selector": ".buy-button",
                },
                "filters": [],
                "navigation": {
                    "pagination_selector": ".pagination",
                    "next_page_selector": ".pagination .next",
                    "prev_page_selector": ".pagination .prev",
                },
                "reviews": {
                    "reviews_container_selector": ".reviews",
                    "review_item_selector": "div[data-widget*='webReview']",
                    "review_text_selector": ".review-text",
                    "review_rating_selector": "div[data-widget*='Rating']",
                    "review_author_selector": "span[data-widget*='Author']",
                    "review_date_selector": ".review-date",
                    "reviews_link_selector": "a[href*='/reviews/']",
                },
                "special_notes": "Uses data-widget attributes for structure",
            },
        }

    elif "wildberries.ru" in url:
        return {
            "success": True,
            "confidence": 0.92,
            "page_type": "search",
            "marketplace_structure": {
                "marketplace_name": "Wildberries",
                "base_url": "https://www.wildberries.ru",
                "search": {
                    "search_input_selector": "input#searchInput",
                    "search_button_selector": "button.search-btn",
                    "search_form_selector": "form.search-form",
                },
                "product": {
                    "container_selector": ".product-card",
                    "title_selector": ".product-card__name",
                    "price_selector": ".price",
                    "link_selector": ".product-card__link",
                    "image_selector": ".product-card__img",
                    "rating_selector": ".product-card__rating",
                    "discount_selector": ".product-card__discount",
                },
                "product_page": {
                    "title_selector": "h1.product-page__title",
                    "price_selector": ".price-block__final-price",
                    "description_selector": ".product-page__description",
                    "specifications_selector": ".product-page__specs",
                    "images_selector": ".product-page__gallery img",
                    "availability_selector": ".product-page__availability",
                    "buy_button_selector": ".btn-main",
                },
                "filters": [],
                "navigation": {
                    "pagination_selector": ".pagination",
                    "next_page_selector": ".pagination__next",
                    "prev_page_selector": ".pagination__prev",
                },
                "reviews": {
                    "reviews_container_selector": ".reviews-list",
                    "review_item_selector": ".review-item",
                    "review_text_selector": ".review-text",
                    "review_rating_selector": ".review-rating",
                    "review_author_selector": ".review-author",
                    "review_date_selector": ".review-date",
                    "reviews_link_selector": "a[href*='reviews']",
                },
                "special_notes": "Uses BEM methodology for CSS classes",
            },
        }

    else:
        return {
            "success": True,
            "confidence": 0.85,
            "page_type": "main",
            "marketplace_structure": {
                "marketplace_name": "Universal Marketplace",
                "base_url": url,
                "search": {
                    "search_input_selector": "input[type='search'], input[name*='search'], input[placeholder*='search']",
                    "search_button_selector": "button[type='submit'], .search-btn",
                    "search_form_selector": "form",
                },
                "product": {
                    "container_selector": ".product, .item, [class*='product'], [class*='item']",
                    "title_selector": ".title, .name, h3, h4, [class*='title'], [class*='name']",
                    "price_selector": ".price, [class*='price'], [class*='cost']",
                    "link_selector": "a",
                    "image_selector": "img",
                    "rating_selector": "[class*='rating'], [class*='star']",
                    "discount_selector": "[class*='discount'], [class*='sale']",
                },
                "product_page": {
                    "title_selector": "h1",
                    "price_selector": ".price, [class*='price']",
                    "description_selector": "[class*='description'], .desc",
                    "specifications_selector": "[class*='spec'], .specs",
                    "images_selector": ".gallery img, .images img",
                    "availability_selector": "[class*='availability'], [class*='stock']",
                    "buy_button_selector": "[class*='buy'], [class*='cart'], .btn-primary",
                },
                "filters": [],
                "navigation": {
                    "pagination_selector": ".pagination",
                    "next_page_selector": ".next, [class*='next']",
                    "prev_page_selector": ".prev, [class*='prev']",
                },
                "reviews": {
                    "reviews_container_selector": ".reviews, [class*='review']",
                    "review_item_selector": ".review, [class*='review-item']",
                    "review_text_selector": ".text, .content, [class*='text']",
                    "review_rating_selector": "[class*='rating']",
                    "review_author_selector": "[class*='author'], [class*='user']",
                    "review_date_selector": "[class*='date']",
                    "reviews_link_selector": "a[href*='review']",
                },
                "special_notes": "Universal selectors for unknown marketplace",
            },
        }


class MockMarketplaceAnalyzer:
    """Mock version of analyzer for demonstration"""

    def __init__(self):
        self.name = "marketplace_analyzer"
        self.description = "Universal tool for working with any marketplaces"
        self._analyzed_structures = {}

    def analyze_marketplace(self, url: str) -> dict:
        """Analyzes marketplace structure"""
        print(f"🔍 Analyzing structure: {url}")

        # Simulate getting HTML
        html = f"<html><head><title>Store</title></head><body>HTML code for {url}</body></html>"

        # Simulate LLM analysis
        result = simulate_llm_analysis(url, html)

        if result["success"]:
            # Cache result
            from urllib.parse import urlparse

            domain = urlparse(url).netloc
            self._analyzed_structures[domain] = result["marketplace_structure"]

            return {
                "success": True,
                "message": f"✅ Analysis completed successfully!\n"
                f"Marketplace: {result['marketplace_structure']['marketplace_name']}\n"
                f"Confidence: {result['confidence']:.2f}\n"
                f"Page type: {result['page_type']}\n"
                f"Found selectors for search, products, filters and reviews",
            }
        else:
            return {
                "success": False,
                "message": f"❌ Analysis error: {result.get('error_message', 'Unknown error')}",
            }

    def search_products(self, url: str, query: str, max_results: int = 5) -> dict:
        """Searches for products on marketplace"""
        print(f"🔎 Searching for products: '{query}' on {url}")

        # Check if structure analysis exists
        from urllib.parse import urlparse

        domain = urlparse(url).netloc

        if domain not in self._analyzed_structures:
            print("📊 Analyzing structure first...")
            analysis = self.analyze_marketplace(url)
            if not analysis["success"]:
                return analysis

        structure = self._analyzed_structures[domain]

        # Simulate product search
        products = []
        for i in range(max_results):
            products.append(
                {
                    "title": f"Product {query} #{i+1}",
                    "price": f"${100 + i*50}",
                    "link": f"{url}/product/{i+1}",
                    "rating": f"{4 + i*0.1:.1f}/5",
                }
            )

        return {
            "success": True,
            "message": f"🛍️ Products found: {len(products)}\n\n"
            + "\n".join(
                [
                    f"{i+1}. 📦 {p['title']}\n"
                    f"   💰 {p['price']}\n"
                    f"   ⭐ {p['rating']}\n"
                    f"   🔗 {p['link']}"
                    for i, p in enumerate(products)
                ]
            ),
        }

    def compare_marketplaces(self, query: str, urls: list) -> dict:
        """Compares products between marketplaces"""
        print(f"⚖️ Comparing '{query}' between {len(urls)} marketplaces")

        comparison = []
        for url in urls:
            search_result = self.search_products(url, query, 3)
            if search_result["success"]:
                comparison.append(
                    {"marketplace": url, "status": "✅ Success", "products_found": 3}
                )
            else:
                comparison.append(
                    {"marketplace": url, "status": "❌ Error", "products_found": 0}
                )

        return {
            "success": True,
            "message": f"📊 Comparison completed!\n\n"
            + "\n".join(
                [
                    f"🌐 {comp['marketplace']}\n"
                    f"   {comp['status']}\n"
                    f"   📦 Products found: {comp['products_found']}"
                    for comp in comparison
                ]
            ),
        }


def demo_universal_analyzer():
    """Universal analyzer demonstration"""
    print("🚀 Universal marketplace analyzer demonstration")
    print("=" * 70)
    print("🧠 This tool uses LLM for automatic analysis")
    print("   of ANY marketplace structure without hardcoded selectors!")
    print()

    analyzer = MockMarketplaceAnalyzer()

    # Test 1: Ozon analysis
    print("📋 TEST 1: OZON structure analysis")
    print("-" * 40)
    result = analyzer.analyze_marketplace("https://www.ozon.ru")
    print(result["message"])
    print()

    # Test 2: Ozon search
    print("📋 TEST 2: Product search on OZON")
    print("-" * 40)
    result = analyzer.search_products("https://www.ozon.ru", "smartphone", 3)
    print(result["message"])
    print()

    # Test 3: Wildberries analysis
    print("📋 TEST 3: Wildberries structure analysis")
    print("-" * 40)
    result = analyzer.analyze_marketplace("https://www.wildberries.ru")
    print(result["message"])
    print()

    # Test 4: Wildberries search
    print("📋 TEST 4: Product search on Wildberries")
    print("-" * 40)
    result = analyzer.search_products("https://www.wildberries.ru", "sneakers", 3)
    print(result["message"])
    print()

    # Test 5: Universal analysis
    print("📋 TEST 5: Unknown marketplace analysis")
    print("-" * 40)
    result = analyzer.analyze_marketplace("https://new-marketplace.com")
    print(result["message"])
    print()

    # Test 6: Marketplace comparison
    print("📋 TEST 6: Marketplace comparison")
    print("-" * 40)
    result = analyzer.compare_marketplaces(
        "headphones",
        ["https://www.ozon.ru", "https://www.wildberries.ru", "https://aliexpress.com"],
    )
    print(result["message"])
    print()

    # Conclusion
    print("=" * 70)
    print("✅ DEMONSTRATION COMPLETED!")
    print()
    print("🎯 Key advantages:")
    print("   • Works with ANY marketplaces")
    print("   • Automatically determines selectors through LLM")
    print("   • No manual coding required for each site")
    print("   • Adapts to site structure changes")
    print("   • Caches analysis results for speed")
    print()
    print("🔄 Working principle:")
    print("   1. Load page → get HTML")
    print("   2. Send HTML to LLM → get selectors")
    print("   3. Cache structure → use for extraction")
    print("   4. Work with products, filters, reviews")
    print()
    print("🏆 Universality achieved!")


if __name__ == "__main__":
    demo_universal_analyzer()
