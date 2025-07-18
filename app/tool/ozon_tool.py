import asyncio
import json
import re
from typing import Dict, List, Optional

from playwright.async_api import Page, async_playwright
from pydantic import Field

from app.logger import logger
from app.tool.base import BaseTool, ToolResult


class OzonTool(BaseTool):
    """Tool for working with ozon.ru website with anti-bot bypass"""

    name: str = "ozon_tool"
    description: str = """SPECIALIZED tool for OZON.RU.

ALWAYS use this tool for ANY requests related to:
- Product search on OZON
- Review analysis on OZON
- Getting product information from OZON
- Any tasks mentioning "OZON", "ОЗОН" or "ozon.ru"

This tool has built-in anti-bot bypass for OZON and is optimized specifically for this site.
DO NOT use browser_use for OZON tasks - use ONLY ozon_tool!"""

    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "search",
                    "get_reviews",
                    "get_product_info",
                    "close",
                ],
                "description": "Action to perform: search - product search, get_reviews - get reviews, get_product_info - product information, close - close browser",
            },
            "query": {
                "type": "string",
                "description": "Search query for products (required for action=search)",
            },
            "product_url": {
                "type": "string",
                "description": "Product URL for getting reviews or information (required for get_reviews and get_product_info)",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of search results (default 10)",
                "default": 10,
            },
            "max_reviews": {
                "type": "integer",
                "description": "Maximum number of reviews to read (default 20)",
                "default": 20,
            },
        },
        "required": ["action"],
    }

    # Store browser state
    _playwright = None
    _browser = None
    _context = None
    _page: Optional[Page] = None

    async def execute(
        self,
        action: str,
        query: Optional[str] = None,
        product_url: Optional[str] = None,
        max_results: int = 10,
        max_reviews: int = 20,
        **kwargs,
    ) -> ToolResult:
        """
        Executes action with ozon.ru website

        Args:
            action: Action to perform
            query: Search query
            product_url: Product URL
            max_results: Maximum number of search results
            max_reviews: Maximum number of reviews
        """
        try:
            if action == "search":
                if not query:
                    return ToolResult(error="Query is required for search")
                return await self._search_products(query, max_results)

            elif action == "get_reviews":
                if not product_url:
                    return ToolResult(error="Product URL is required to get reviews")
                return await self._get_product_reviews(product_url, max_reviews)

            elif action == "get_product_info":
                if not product_url:
                    return ToolResult(
                        error="Product URL is required to get product information"
                    )
                return await self._get_product_info(product_url)

            elif action == "close":
                return await self._close_browser()

            else:
                return ToolResult(error=f"Unknown action: {action}")

        except Exception as e:
            logger.error(f"Error in OzonTool: {e}")
            return ToolResult(error=f"Execution error: {str(e)}")

    async def _ensure_browser_ready(self) -> Page:
        """Ensures browser is ready for work"""
        if self._page is None:
            await self._init_browser()

        if self._page is None:
            raise RuntimeError("Failed to initialize browser")

        return self._page

    async def _init_browser(self):
        """Initializes browser with anti-bot bypass settings"""
        logger.info("Initializing browser for ozon.ru...")

        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-infobars",
                "--disable-extensions",
                "--disable-popup-blocking",
            ],
        )

        self._context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            locale="ru-RU",
            permissions=["geolocation"],
            java_script_enabled=True,
            bypass_csp=True,
        )

        await self._context.add_init_script(
            """
            delete navigator.__proto__.webdriver;
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
            window.chrome = {runtime: {}};
        """
        )

        self._page = await self._context.new_page()
        await self._navigate_to_ozon()

    async def _navigate_to_ozon(self):
        """Navigates to Ozon main page and bypasses anti-bot"""
        logger.info("Navigating to ozon.ru...")

        if self._page is None:
            raise RuntimeError("Page is not initialized")

        try:
            await self._page.goto(
                "https://www.ozon.ru/", wait_until="networkidle", timeout=120000
            )

            # Emulate human behavior
            await self._page.mouse.move(100, 100)
            await asyncio.sleep(0.5)
            await self._page.mouse.move(200, 150)
            await asyncio.sleep(0.3)

            # Check for anti-bot
            if await self._page.query_selector(".message .loader"):
                logger.info("Anti-bot detected, waiting...")
                await self._page.wait_for_selector(
                    ".message .loader", state="hidden", timeout=60000
                )
                logger.info("Anti-bot passed")

            await self._page.wait_for_load_state("networkidle", timeout=60000)
            logger.info("Page loaded successfully")

        except Exception as e:
            logger.error(f"Error navigating to ozon.ru: {e}")
            raise

    async def _search_products(self, query: str, max_results: int) -> ToolResult:
        """Performs product search on Ozon"""
        logger.info(f"Searching products: {query}")

        page = await self._ensure_browser_ready()

        try:
            # Find search field
            search_selectors = [
                "input[placeholder*='Искать']",
                "input[placeholder*='искать']",
                "input[placeholder*='Поиск']",
                "input[name='text']",
                "input[type='text']",
                "[data-widget='searchBarDesktop'] input",
                ".tsBody400Medium input",
            ]

            search_input = None
            for selector in search_selectors:
                try:
                    search_input = await page.wait_for_selector(selector, timeout=3000)
                    if search_input:
                        break
                except:
                    continue

            if not search_input:
                return ToolResult(error="Search field not found")

            # Enter search query
            await search_input.click()
            await search_input.fill("")
            await asyncio.sleep(0.5)
            await search_input.type(query, delay=100)
            await search_input.press("Enter")

            # Wait for results
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

            # Additional wait for prices to load
            try:
                await page.wait_for_function(
                    "document.body.innerText.includes('₽')", timeout=10000
                )
            except:
                pass

            # Extract search results
            products = await self._extract_search_results(page, max_results, query)

            return ToolResult(
                output=f"Products found: {len(products)}\n\n"
                + "\n".join([f"{i+1}. {product}" for i, product in enumerate(products)])
            )

        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return ToolResult(error=f"Search error: {str(e)}")

    async def _extract_search_results(
        self, page: Page, max_results: int, query: str
    ) -> List[str]:
        """Extracts search results from page"""
        products = []

        try:
            # Find product containers
            product_container_selectors = [
                "[data-widget='searchResultsV2'] > div",
                "[data-widget='searchResults'] > div",
                ".tile-root",
                "[data-widget] > div",
                "div[class*='tile']",
                "div[class*='item']",
                ".product-card",
                "article",
            ]

            product_containers = []
            for selector in product_container_selectors:
                try:
                    containers = await page.query_selector_all(selector)
                    if containers and len(containers) > 5:
                        product_containers = containers[: max_results * 2]
                        break
                except:
                    continue

            if not product_containers:
                return await self._extract_search_results_fallback(
                    page, max_results, query
                )

            for i, container in enumerate(product_containers):
                if len(products) >= max_results:
                    break

                try:
                    # Find product URL
                    product_url = None
                    link_selectors = [
                        "a[href*='/product/']",
                        "a[href*='product']",
                        "a[href*='/p/']",
                        "a",
                    ]

                    for link_selector in link_selectors:
                        try:
                            link_element = await container.query_selector(link_selector)
                            if link_element:
                                href = await link_element.get_attribute("href")
                                if href and ("product" in href or "/p/" in href):
                                    product_url = (
                                        f"https://www.ozon.ru{href}"
                                        if href.startswith("/")
                                        else href
                                    )
                                    break
                        except:
                            continue

                    if not product_url:
                        continue

                    # Find price
                    price = None
                    price_selectors = [
                        "span.c35_3_1-a1.tsHeadline500Medium.c35_3_1-b1.c35_3_1-a6",
                        "span[style*='background-image'][style*='linear-gradient']",
                        "span.tsHeadline500Medium[style*='background-image']",
                        "span.tsHeadline500Medium",
                        "span[class*='price']",
                        "span[data-widget*='price']",
                        "*[class*='price']",
                    ]

                    for price_selector in price_selectors:
                        try:
                            price_element = await container.query_selector(
                                price_selector
                            )
                            if price_element:
                                price_text = await price_element.inner_text()
                                if price_text and "₽" in price_text:
                                    price = self._clean_price_text(price_text)
                                    break
                        except:
                            continue

                    if not price:
                        continue

                    # Find title
                    title = await self._extract_product_title(container, query)
                    if not title:
                        title = "Title not found"

                    # Add product
                    product_info = f"📦 {title}\n💰 {price}\n🔗 {product_url}"
                    products.append(product_info)

                except Exception as e:
                    logger.warning(f"Error processing container {i+1}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error extracting search results: {e}")

        return products

    async def _extract_search_results_fallback(
        self, page: Page, max_results: int, query: str
    ) -> List[str]:
        """Fallback method for extracting search results"""
        products = []

        try:
            # Global search for prices
            all_prices = await self._find_all_prices(page)

            # Global search for product links
            all_product_links = await self._find_all_product_links(page)

            # Global search for titles
            all_titles = await self._find_all_titles(page, query)

            # Combine results
            max_items = min(max_results, len(all_product_links), len(all_prices))

            for i in range(max_items):
                try:
                    product_url = (
                        all_product_links[i]
                        if i < len(all_product_links)
                        else "Link not found"
                    )
                    price = all_prices[i] if i < len(all_prices) else "Price not found"
                    title = all_titles[i] if i < len(all_titles) else "Title not found"

                    product_info = f"📦 {title}\n💰 {price}\n🔗 {product_url}"
                    products.append(product_info)

                except Exception as e:
                    logger.warning(f"Error creating product {i+1}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in fallback extraction: {e}")

        return products

    async def _find_all_prices(self, page: Page) -> List[str]:
        """Find all prices on page"""
        all_prices = []
        price_selectors = [
            "span.c35_3_1-a1.tsHeadline500Medium.c35_3_1-b1.c35_3_1-a6",
            "span[style*='background-image'][style*='linear-gradient']",
            "span.tsHeadline500Medium[style*='background-image']",
            "span.tsHeadline500Medium",
        ]

        for selector in price_selectors:
            try:
                price_elements = await page.query_selector_all(selector)
                for price_element in price_elements:
                    price_text = await price_element.inner_text()
                    if price_text and "₽" in price_text:
                        price_cleaned = self._clean_price_text(price_text)
                        if price_cleaned not in all_prices:
                            all_prices.append(price_cleaned)
            except:
                continue

        return all_prices

    async def _find_all_product_links(self, page: Page) -> List[str]:
        """Find all product links on page"""
        all_product_links = []
        link_selectors = [
            "a[href*='/product/']",
            "a[href*='product']",
            "a[href*='/p/']",
        ]

        for selector in link_selectors:
            try:
                link_elements = await page.query_selector_all(selector)
                for link_element in link_elements:
                    href = await link_element.get_attribute("href")
                    if href and ("product" in href or "/p/" in href):
                        full_url = (
                            f"https://www.ozon.ru{href}"
                            if href.startswith("/")
                            else href
                        )
                        if full_url not in all_product_links:
                            all_product_links.append(full_url)
            except:
                continue

        return all_product_links

    async def _find_all_titles(self, page: Page, query: str) -> List[str]:
        """Find all product titles on page"""
        all_titles = []
        title_selectors = [
            "span.tsBody500Medium",
            "span.tsBody400Medium",
            "span[data-widget*='Title']",
        ]

        for selector in title_selectors:
            try:
                title_elements = await page.query_selector_all(selector)
                for title_element in title_elements:
                    title_text = await title_element.inner_text()
                    if self._is_valid_title(title_text, query):
                        title_cleaned = title_text.strip()
                        if title_cleaned not in all_titles:
                            all_titles.append(title_cleaned)
            except:
                continue

        return all_titles

    async def _extract_product_title(self, container, query: str) -> Optional[str]:
        """Extract product title from container"""
        title_selectors = [
            "span.tsBody500Medium",
            "span.tsBody400Medium",
            "span[data-widget*='Title']",
            "span[data-widget*='title']",
            "[data-widget*='title'] span",
            ".title",
            "h3",
            "h2",
            "a[href*='product'] span",
            "span[class*='title']",
        ]

        for title_selector in title_selectors:
            try:
                title_elements = await container.query_selector_all(title_selector)
                for title_element in title_elements:
                    title_text = await title_element.inner_text()
                    if self._is_valid_title(title_text, query):
                        return title_text.strip()
            except:
                continue

        # Fallback: search for any suitable text
        try:
            all_spans = await container.query_selector_all("span")
            for span in all_spans:
                span_text = await span.inner_text()
                if self._is_valid_title(span_text, query, min_length=20):
                    return span_text.strip()
        except:
            pass

        return None

    def _is_valid_title(self, text: str, query: str, min_length: int = 15) -> bool:
        """Check if text is a valid product title"""
        if not text or not text.strip():
            return False

        text = text.strip()

        # Basic validation
        if "₽" in text or len(text) < min_length or len(text) > 200:
            return False

        # Check for service/UI text that shouldn't be product titles
        text_lower = text.lower()
        service_words = [
            "добавить",
            "корзина",
            "купить",
            "заказать",
            "доставка",
            "скидка",
            "акция",
            "бонус",
            "cashback",
            "кэшбэк",
            "войти",
            "регистрация",
            "профиль",
            "избранное",
            "сравнить",
            "отзыв",
            "рейтинг",
            "фото",
            "видео",
            "показать",
            "скрыть",
            "больше",
            "меньше",
            "все",
            "руб",
            "₽",
            "цена",
            "стоимость",
        ]

        # Skip service/UI text
        if any(service_word in text_lower for service_word in service_words):
            return False

        # Check relevance to search query
        if query and len(query.strip()) > 2:
            query_words = query.lower().split()
            # Check if any query word appears in title
            if any(
                query_word in text_lower
                for query_word in query_words
                if len(query_word) > 2
            ):
                return True

        # General product indicators (brands, categories, etc.)
        product_indicators = [
            # Brands
            "apple",
            "samsung",
            "xiaomi",
            "huawei",
            "honor",
            "realme",
            "oppo",
            "vivo",
            "sony",
            "lg",
            "panasonic",
            "philips",
            "bosch",
            "siemens",
            "electrolux",
            "nike",
            "adidas",
            "puma",
            "reebok",
            "new balance",
            "converse",
            "zara",
            "h&m",
            "uniqlo",
            "mango",
            "bershka",
            "stradivarius",
            # Product types
            "смартфон",
            "телефон",
            "планшет",
            "ноутбук",
            "компьютер",
            "монитор",
            "наушники",
            "колонка",
            "клавиатура",
            "мышь",
            "камера",
            "фотоаппарат",
            "часы",
            "браслет",
            "кольцо",
            "серьги",
            "цепочка",
            "подвеска",
            "куртка",
            "пальто",
            "рубашка",
            "футболка",
            "джинсы",
            "брюки",
            "платье",
            "юбка",
            "блузка",
            "свитер",
            "кроссовки",
            "ботинки",
            "сумка",
            "рюкзак",
            "кошелек",
            "чемодан",
            "косметика",
            "парфюм",
            "шампунь",
            "крем",
            "маска",
            "сыворотка",
            "тональный",
            "помада",
            "книга",
            "учебник",
            "роман",
            "детектив",
            "фантастика",
            "комикс",
            "игрушка",
            "конструктор",
            "кукла",
            "машинка",
            "пазл",
            "настольная",
            "витамины",
            "бад",
            "лекарство",
            "мазь",
            "таблетки",
            "капсулы",
        ]

        # Check if text contains any product indicators
        if any(indicator in text_lower for indicator in product_indicators):
            return True

        # If title is long enough and doesn't contain service words, likely a product
        return len(text) >= 20

    def _clean_price_text(self, price_text: str) -> str:
        """Clean price text"""
        return (
            price_text.strip()
            .replace("&thinsp;", " ")
            .replace("​", " ")
            .replace("\u2009", " ")
            .replace("  ", " ")
            .strip()
        )

    async def _get_product_reviews(
        self, product_url: str, max_reviews: int
    ) -> ToolResult:
        """Gets product reviews by navigating to dedicated reviews page"""
        logger.info(f"Getting reviews for product: {product_url}")

        page = await self._ensure_browser_ready()

        try:
            # Go to product page first
            await page.goto(product_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            # Find reviews link in webSingleProductScore widget
            reviews_link = await self._find_reviews_link(page)
            if not reviews_link:
                return ToolResult(error="Reviews link not found on product page")

            logger.info(f"Found reviews link: {reviews_link}")

            # Navigate to reviews page
            await page.goto(reviews_link, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            # Extract reviews from dedicated reviews page
            reviews = await self._extract_reviews_from_reviews_page(page, max_reviews)

            if not reviews:
                return ToolResult(error="No reviews found on reviews page")

            return ToolResult(
                output=f"Reviews found: {len(reviews)}\n\n" + "\n---\n".join(reviews)
            )

        except Exception as e:
            logger.error(f"Error getting reviews: {e}")
            return ToolResult(error=f"Error getting reviews: {str(e)}")

    async def _find_reviews_link(self, page: Page) -> Optional[str]:
        """Find reviews link in webSingleProductScore widget"""
        try:
            # Look for the reviews link in webSingleProductScore widget
            selectors = [
                "div[data-widget='webSingleProductScore'] a[href*='/reviews/']",
                "div[data-widget*='Score'] a[href*='/reviews/']",
                "a[href*='/reviews/']",
            ]

            for selector in selectors:
                try:
                    link_element = await page.query_selector(selector)
                    if link_element:
                        href = await link_element.get_attribute("href")
                        if href:
                            # Construct full URL if needed
                            if href.startswith("/"):
                                return f"https://www.ozon.ru{href}"
                            return href
                except Exception as e:
                    logger.warning(f"Error with selector {selector}: {e}")
                    continue

            logger.warning("Reviews link not found with any selector")
            return None

        except Exception as e:
            logger.error(f"Error finding reviews link: {e}")
            return None

    async def _extract_reviews_from_reviews_page(
        self, page: Page, max_reviews: int
    ) -> List[str]:
        """Extracts reviews from dedicated reviews page"""
        reviews = []

        try:
            # Wait for reviews to load
            await asyncio.sleep(3)

            # First, try to find individual review items directly
            review_item_selectors = [
                # Common review selectors
                "div[data-widget*='webReview']",
                "div[data-widget*='Review']",
                "article[data-widget*='review']",
                "[data-widget*='reviewItem']",
                # General selectors
                "div[class*='review']",
                "article[class*='review']",
                ".review-item",
                ".review-card",
                # Broader selectors
                "div[data-widget] div[class*='text']",
                "div[data-widget] p",
            ]

            all_review_elements = []
            used_selector = None

            for selector in review_item_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements and len(elements) > 0:
                        # Filter elements that actually contain meaningful text
                        valid_elements = []
                        for element in elements:
                            try:
                                text = await element.inner_text()
                                if (
                                    text and len(text.strip()) > 20
                                ):  # Minimum length for review
                                    valid_elements.append(element)
                            except:
                                continue

                        if valid_elements:
                            all_review_elements = valid_elements[
                                : max_reviews * 3
                            ]  # Take more to filter later
                            used_selector = selector
                            logger.info(
                                f"Found {len(valid_elements)} review elements with selector: {selector}"
                            )
                            break
                except Exception as e:
                    logger.warning(f"Error with selector {selector}: {e}")
                    continue

            if not all_review_elements:
                logger.warning("No review elements found with any selector")
                # Fallback: try to extract any text that looks like reviews
                return await self._extract_reviews_fallback(page, max_reviews)

            # Extract reviews from found elements
            reviews_found = 0
            for element in all_review_elements:
                if reviews_found >= max_reviews:
                    break

                try:
                    review_data = await self._extract_single_review_improved(element)
                    if review_data:
                        reviews.append(review_data)
                        reviews_found += 1
                except Exception as e:
                    logger.warning(f"Error extracting review {reviews_found + 1}: {e}")
                    continue

            logger.info(
                f"Successfully extracted {len(reviews)} reviews using selector: {used_selector}"
            )

        except Exception as e:
            logger.error(f"Error extracting reviews from reviews page: {e}")

        return reviews

    async def _extract_single_review_improved(self, element) -> Optional[str]:
        """Extract data from a single review element with improved detection"""
        try:
            # Get the full text of the element first
            full_text = await element.inner_text()
            if not full_text or len(full_text.strip()) < 10:
                return None

            # Initialize default values
            rating = "⭐ Не указан"
            review_text = full_text.strip()
            author = "Автор не указан"

            # Extract rating (try multiple approaches)
            rating_selectors = [
                # Standard selectors
                "div[data-widget*='webReviewProductRating']",
                "div[data-widget*='Rating']",
                "span[data-widget*='Rating']",
                # Star-based selectors
                "div[class*='rating']",
                "span[class*='star']",
                "div[class*='star']",
                # SVG stars
                "svg[class*='star']",
                # General rating indicators
                "[class*='rate']",
                "[data-widget*='rate']",
            ]

            for rating_selector in rating_selectors:
                try:
                    rating_element = await element.query_selector(rating_selector)
                    if rating_element:
                        rating_text = await rating_element.inner_text()
                        if rating_text and any(char.isdigit() for char in rating_text):
                            rating = f"⭐ {rating_text.strip()}"
                            break
                        # Check for star count via SVG or other elements
                        stars = await rating_element.query_selector_all("svg")
                        if stars:
                            rating = f"⭐ {len(stars)} из 5"
                            break
                except:
                    continue

            # Extract author with multiple approaches
            author_selectors = [
                # Standard selectors
                "span[data-widget*='webReviewAuthor']",
                "div[data-widget*='Author']",
                # Class-based selectors
                "div[class*='author']",
                "span[class*='author']",
                ".reviewer-name",
                ".user-name",
                # Text pattern matching
                "div[class*='name']",
                "span[class*='name']",
            ]

            for author_selector in author_selectors:
                try:
                    author_element = await element.query_selector(author_selector)
                    if author_element:
                        author_text = await author_element.inner_text()
                        if author_text and len(author_text.strip()) > 0:
                            # Filter out dates, ratings, and other non-name text
                            author_clean = author_text.strip()
                            if not any(
                                word in author_clean.lower()
                                for word in [
                                    "отзыв",
                                    "review",
                                    "2023",
                                    "2024",
                                    "2025",
                                    "января",
                                    "февраля",
                                    "марта",
                                ]
                            ):
                                author = author_clean
                                break
                except:
                    continue

            # Clean review text (remove author and rating info if included)
            lines = review_text.split("\n")
            cleaned_lines = []

            for line in lines:
                line_clean = line.strip()
                # Skip lines that are likely metadata (short, contain dates, etc.)
                if len(line_clean) > 15 and not any(
                    word in line_clean.lower()
                    for word in ["достоинства:", "недостатки:", "комментарий:"]
                ):
                    cleaned_lines.append(line_clean)

            if cleaned_lines:
                review_text = " ".join(cleaned_lines)

            # Make sure we have meaningful content
            if len(review_text.strip()) < 20:
                return None

            return f"👤 {author}\n{rating}\n💬 {review_text[:500]}{'...' if len(review_text) > 500 else ''}"

        except Exception as e:
            logger.warning(f"Error extracting improved single review: {e}")
            return None

    async def _extract_reviews_fallback(
        self, page: Page, max_reviews: int
    ) -> List[str]:
        """Fallback method to extract reviews when standard selectors fail"""
        reviews = []

        try:
            logger.info("Using fallback method to extract reviews")

            # Try to find any text blocks that might be reviews
            text_selectors = [
                "div[data-widget] div",
                "div[class*='text'] span",
                "p",
                "div span",
                "[data-widget] span",
            ]

            all_text_elements = []

            for selector in text_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        try:
                            text = await element.inner_text()
                            # Look for text that might be a review (longer than 50 chars, contains meaningful words)
                            if (
                                text
                                and len(text.strip()) > 50
                                and len(text.strip()) < 1000
                                and any(
                                    word in text.lower()
                                    for word in [
                                        "хорош",
                                        "плох",
                                        "отлично",
                                        "ужасно",
                                        "рекомендую",
                                        "покупал",
                                        "использую",
                                        "качество",
                                        "цена",
                                        "товар",
                                    ]
                                )
                            ):
                                all_text_elements.append(text.strip())
                                if len(all_text_elements) >= max_reviews:
                                    break
                        except:
                            continue
                    if len(all_text_elements) >= max_reviews:
                        break
                except:
                    continue

            # Format found text as reviews
            for i, text in enumerate(all_text_elements[:max_reviews]):
                reviews.append(f"👤 Покупатель {i+1}\n⭐ Оценка не указана\n💬 {text}")

            logger.info(f"Fallback method found {len(reviews)} potential reviews")

        except Exception as e:
            logger.error(f"Error in fallback review extraction: {e}")

        return reviews

    async def _extract_single_review(self, container) -> Optional[str]:
        """Legacy method - redirects to improved version"""
        return await self._extract_single_review_improved(container)

    async def _extract_reviews(self, page: Page, max_reviews: int) -> List[str]:
        """Legacy method - now redirects to new method"""
        return await self._extract_reviews_from_reviews_page(page, max_reviews)

    async def _get_product_info(self, product_url: str) -> ToolResult:
        """Gets detailed product information"""
        logger.info(f"Getting product information: {product_url}")

        page = await self._ensure_browser_ready()

        try:
            await page.goto(product_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Extract product info
            title_element = await page.query_selector("h1")
            title = (
                await title_element.inner_text() if title_element else "Title not found"
            )

            price_element = await page.query_selector("span[data-widget*='webPrice']")
            price = (
                await price_element.inner_text() if price_element else "Price not found"
            )

            rating_element = await page.query_selector("div[data-widget*='webRating']")
            rating = (
                await rating_element.inner_text()
                if rating_element
                else "Rating not found"
            )

            description_element = await page.query_selector(
                "div[data-widget*='webDescription']"
            )
            description = (
                await description_element.inner_text()
                if description_element
                else "Description not found"
            )

            characteristics = await self._extract_characteristics(page)

            product_info = f"""
📦 PRODUCT: {title}
💰 PRICE: {price}
⭐ RATING: {rating}
📝 DESCRIPTION: {description[:500]}{'...' if len(description) > 500 else ''}
📋 CHARACTERISTICS:
{characteristics}
"""

            return ToolResult(output=product_info)

        except Exception as e:
            logger.error(f"Error getting product information: {e}")
            return ToolResult(error=f"Error getting information: {str(e)}")

    async def _extract_characteristics(self, page: Page) -> str:
        """Extracts product characteristics"""
        try:
            await page.wait_for_selector(
                "div[data-widget*='webCharacteristics']", timeout=5000
            )

            characteristics = []
            char_elements = await page.query_selector_all(
                "div[data-widget*='webCharacteristics'] div"
            )

            for element in char_elements[:10]:
                try:
                    text = await element.inner_text()
                    if text and ":" in text:
                        characteristics.append(f"• {text}")
                except:
                    continue

            return (
                "\n".join(characteristics)
                if characteristics
                else "Characteristics not found"
            )

        except Exception as e:
            logger.warning(f"Error extracting characteristics: {e}")
            return "Characteristics not found"

    async def _close_browser(self) -> ToolResult:
        """Closes browser"""
        logger.info("Closing browser...")

        try:
            # Close page first if it exists
            if self._page:
                try:
                    await self._page.close()
                except Exception as e:
                    logger.warning(f"Error closing page: {e}")
                self._page = None

            # Close context if it exists
            if self._context:
                try:
                    await self._context.close()
                except Exception as e:
                    logger.warning(f"Error closing context: {e}")
                self._context = None

            # Close browser if it exists
            if self._browser:
                try:
                    await self._browser.close()
                except Exception as e:
                    logger.warning(f"Error closing browser: {e}")
                self._browser = None

            # Stop playwright last
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception as e:
                    logger.warning(f"Error stopping playwright: {e}")
                self._playwright = None

            logger.info("Browser closed successfully")
            return ToolResult(output="Browser closed successfully")

        except Exception as e:
            logger.error(f"Error closing browser: {e}")
            # Reset all to None even if there was an error
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            return ToolResult(error=f"Browser closing error: {str(e)}")

    async def cleanup(self):
        """Resource cleanup"""
        try:
            if self._browser or self._playwright:
                await self._close_browser()
        except Exception as e:
            logger.error(f"Error during OzonTool cleanup: {e}")
            # Force cleanup even if _close_browser fails
            try:
                if self._browser:
                    await self._browser.close()
                    self._browser = None
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None
                self._context = None
                self._page = None
                logger.info("Force cleanup completed for OzonTool")
            except Exception as force_error:
                logger.error(f"Force cleanup also failed: {force_error}")
