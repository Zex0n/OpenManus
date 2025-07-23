import asyncio
import json
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page, async_playwright
from pydantic import Field

from app.config import Config, MarketplaceSettings
from app.llm import get_llm
from app.logger import logger
from app.schema.marketplace import (
    AnalysisResult,
    ExtractedProduct,
    ExtractedReview,
    MarketplaceStructure,
)
from app.tool.base import BaseTool, ToolResult


class MarketplaceAnalyzer(BaseTool):
    """Universal marketplace analyzer using LLM for page markup"""

    name: str = "marketplace_analyzer"
    description: str = """Universal tool for working with any marketplaces.

Uses LLM to analyze page structure and automatically determine selectors.
Suitable for working with ANY online stores and marketplaces.

Features:
- Product search by query
- Page structure analysis through LLM
- Product information extraction
- Review collection
- Working with filters
- Page navigation"""

    # Configuration fields
    config: Config = Field(default_factory=Config)
    marketplace_config: MarketplaceSettings = Field(default=None)

    def __init__(self, **data):
        if "config" not in data:
            data["config"] = Config()
        if "marketplace_config" not in data:
            data["marketplace_config"] = data["config"].marketplace_config
        super().__init__(**data)

    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "analyze_page",
                    "search_products",
                    "get_product_info",
                    "get_reviews",
                    "apply_filters",
                    "navigate_page",
                    "close",
                ],
                "description": "Action: analyze_page - structure analysis, search_products - product search, get_product_info - product information, get_reviews - reviews, apply_filters - apply filters, navigate_page - navigation, close - close browser",
            },
            "url": {
                "type": "string",
                "description": "Marketplace URL for analysis or search",
            },
            "query": {
                "type": "string",
                "description": "Search query for products",
            },
            "product_url": {
                "type": "string",
                "description": "Product URL for detailed information or reviews",
            },
            "filters": {
                "type": "object",
                "description": "Filters to apply in format {filter_name: value}",
            },
            "max_results": {
                "type": "integer",
                "description": f"Maximum number of results (default {Config().marketplace_config.default_max_results})",
                "default": Config().marketplace_config.default_max_results,
            },
            "max_reviews": {
                "type": "integer",
                "description": f"Maximum number of reviews to extract (default {Config().marketplace_config.default_max_reviews})",
                "default": Config().marketplace_config.default_max_reviews,
            },
            "page_number": {
                "type": "integer",
                "description": "Page number for navigation",
                "default": 1,
            },
        },
        "required": ["action"],
    }

    # Browser state
    _playwright = None
    _browser = None
    _context = None
    _page: Optional[Page] = None

    # Page analysis cache
    _analyzed_structures: Dict[str, MarketplaceStructure] = {}

    async def execute(
        self,
        action: str,
        url: Optional[str] = None,
        query: Optional[str] = None,
        product_url: Optional[str] = None,
        filters: Optional[Dict] = None,
        max_results: int = None,
        max_reviews: int = None,
        page_number: int = 1,
        **kwargs,
    ) -> ToolResult:
        """
        Executes marketplace action

        Args:
            action: Action to execute
            url: Marketplace URL
            query: Search query
            product_url: Product URL
            filters: Filters
            max_results: Maximum number of results
            max_reviews: Maximum number of reviews
            page_number: Page number
        """
        try:
            # Set default values from config if not provided
            if max_results is None:
                max_results = self.marketplace_config.default_max_results
            if max_reviews is None:
                max_reviews = self.marketplace_config.default_max_reviews

            # Validate limits
            if max_reviews > self.marketplace_config.max_reviews_limit:
                logger.warning(
                    f"Requested {max_reviews} reviews, but limit is {self.marketplace_config.max_reviews_limit}. Using limit."
                )
                max_reviews = self.marketplace_config.max_reviews_limit
            if action == "analyze_page":
                if not url:
                    return ToolResult(error="URL is required for page analysis")
                return await self._analyze_page_structure(url)

            elif action == "search_products":
                if not url or not query:
                    return ToolResult(error="URL and query are required for search")
                return await self._search_products(url, query, max_results, filters)

            elif action == "get_product_info":
                if not product_url:
                    return ToolResult(
                        error="Product URL is required for information retrieval"
                    )
                return await self._get_product_info(product_url)

            elif action == "get_reviews":
                if not product_url:
                    return ToolResult(
                        error="Product URL is required for review retrieval"
                    )
                return await self._get_reviews(product_url, max_reviews)

            elif action == "apply_filters":
                if not filters:
                    return ToolResult(error="Filters are required for application")
                return await self._apply_filters(filters)

            elif action == "navigate_page":
                return await self._navigate_page(page_number)

            elif action == "close":
                return await self._close_browser()

            else:
                return ToolResult(error=f"Unknown action: {action}")

        except Exception as e:
            logger.error(f"Error in MarketplaceAnalyzer: {e}")
            return ToolResult(error=f"Execution error: {str(e)}")

    async def _ensure_browser_ready(self) -> Page:
        """Ensures browser is ready for work"""
        if self._page is None:
            await self._init_browser()

        if self._page is None:
            raise RuntimeError("Failed to initialize browser")

        return self._page

    async def _init_browser(self):
        """Initializes browser with anti-detection settings"""
        logger.info("Initializing browser for marketplace analysis...")

        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=self.marketplace_config.headless_browser,  # Use config setting
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

    async def _analyze_page_structure(self, url: str) -> ToolResult:
        """Analyzes page structure using LLM"""
        logger.info(f"Analyzing page structure: {url}")

        page = await self._ensure_browser_ready()

        try:
            # Navigate to page with extended timeout
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.marketplace_config.page_load_timeout + 15000,
            )
            logger.info("Page loaded, waiting for JavaScript content...")

            # Wait for network to settle
            await page.wait_for_load_state(
                "networkidle", timeout=self.marketplace_config.page_load_timeout
            )
            await asyncio.sleep(5)

            # Scroll to trigger lazy loading and wait for content
            await self._ensure_content_loaded(page)

            # Get HTML content
            html_content = await page.content()
            logger.info(f"Original HTML length: {len(html_content)} characters")

            # Clean HTML for analysis (remove unnecessary parts)
            cleaned_html = self._clean_html_for_analysis(html_content)
            logger.info(f"Cleaned HTML length: {len(cleaned_html)} characters")

            # Analyze with LLM
            analysis_result = await self._analyze_html_with_llm(url, cleaned_html)

            if analysis_result.success and analysis_result.marketplace_structure:
                # Cache result
                domain = urlparse(url).netloc
                self._analyzed_structures[domain] = (
                    analysis_result.marketplace_structure
                )

                return ToolResult(
                    output=f"Page structure analysis completed successfully!\n\n"
                    f"Marketplace: {analysis_result.marketplace_structure.marketplace_name}\n"
                    f"Confidence level: {analysis_result.confidence:.2f}\n"
                    f"Page type: {analysis_result.page_type}\n\n"
                    f"Found elements:\n"
                    f"- Search: {analysis_result.marketplace_structure.search.search_input_selector}\n"
                    f"- Product container: {analysis_result.marketplace_structure.product.container_selector}\n"
                    f"- Price: {analysis_result.marketplace_structure.product.price_selector}\n"
                    f"- Title: {analysis_result.marketplace_structure.product.title_selector}\n"
                    f"- Link: {analysis_result.marketplace_structure.product.link_selector}\n"
                    f"- Filters: {len(analysis_result.marketplace_structure.filters)} groups\n"
                    + (
                        f"\nSpecial notes: {analysis_result.marketplace_structure.special_notes}"
                        if analysis_result.marketplace_structure.special_notes
                        else ""
                    )
                )
            else:
                return ToolResult(
                    error=f"Failed to analyze structure: {analysis_result.error_message}"
                )

        except Exception as e:
            logger.error(f"Structure analysis error: {e}")
            return ToolResult(error=f"Analysis error: {str(e)}")

    async def _ensure_content_loaded(self, page: Page) -> None:
        """Ensures JavaScript content is fully loaded"""
        try:
            # Scroll down and up to trigger lazy loading
            await page.evaluate("window.scrollTo(0, 1000)")
            await asyncio.sleep(2)
            await page.evaluate("window.scrollTo(0, 2000)")
            await asyncio.sleep(2)
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(2)

            # Wait for common marketplace elements to appear
            common_selectors = [
                "[data-widget]",
                ".product-card",
                ".goods-tile",
                "[data-testid]",
                ".catalog-product",
                "input[type='search']",
                "input[placeholder*='поиск']",
                "input[placeholder*='search']",
            ]

            for selector in common_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    logger.info(f"Found element: {selector}")
                    break
                except:
                    continue

            # Additional wait for any pending requests
            await asyncio.sleep(3)

        except Exception as e:
            logger.warning(f"Content loading check failed: {e}")

    def _clean_html_for_analysis(self, html: str) -> str:
        """Cleans HTML for LLM analysis with improved preservation of structure"""
        logger.info(f"Starting HTML cleaning, original size: {len(html)}")

        # Remove only script contents, but keep script tags for data attributes
        html = re.sub(
            r"<script[^>]*>(.*?)</script>",
            lambda m: (
                f"<script{m.group(0)[7:m.group(0).index('>')]}></script>"
                if ">" in m.group(0)
                else m.group(0)
            ),
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Remove style contents but keep style tags
        html = re.sub(
            r"<style[^>]*>(.*?)</style>",
            lambda m: (
                f"<style{m.group(0)[6:m.group(0).index('>')]}></style>"
                if ">" in m.group(0)
                else m.group(0)
            ),
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Remove comments
        html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

        # Preserve important whitespace but remove excessive
        html = re.sub(r"\n\s*\n", "\n", html)
        html = re.sub(r"[ \t]+", " ", html)

        # Significantly increase limit for modern SPAs
        max_size = 80000  # Increased from 15000 to 80000
        if len(html) > max_size:
            # Try to keep the most important parts
            # Look for body content
            body_match = re.search(
                r"<body[^>]*>(.*)</body>", html, re.DOTALL | re.IGNORECASE
            )
            if body_match:
                body_content = body_match.group(1)
                if len(body_content) <= max_size:
                    html = f"<html><body>{body_content}</body></html>"
                else:
                    # Take first part of body
                    html = f"<html><body>{body_content[:max_size-50]}...</body></html>"
            else:
                html = html[:max_size] + "..."

        logger.info(f"HTML cleaning completed, final size: {len(html)}")
        return html.strip()

    async def _analyze_html_with_llm(self, url: str, html: str) -> AnalysisResult:
        """Analyzes HTML using LLM to determine structure"""

        prompt = f"""
You are an expert web scraper analyzing a marketplace page. Analyze the HTML code carefully and identify all interactive elements.

Page URL: {url}

HTML code (JavaScript-rendered content):
{html}

CRITICAL INSTRUCTIONS:
1. This HTML contains JavaScript-rendered content from a modern SPA marketplace
2. Look for data-* attributes, class names with modern naming conventions
3. Pay special attention to React/Vue component patterns
4. Identify elements that may have been dynamically created

PAGE TYPES:
- main: main page (may not contain product lists)
- category: category page (should contain product lists)
- search: search results page (should contain product lists)
- product: individual product page

MODERN MARKETPLACE PATTERNS TO LOOK FOR:

1. SEARCH (usually present on all pages):
   - Input with placeholders like "Поиск", "Search", "Найти товары"
   - Common patterns: input[type="search"], input[placeholder*="поиск"], [data-widget*="search"]
   - May be inside forms or standalone with buttons

2. PRODUCTS IN LIST (only for category/search):
   - Container patterns: [data-widget*="searchResults"], [data-widget*="products"], .product-card, .goods-tile
   - Title patterns: usually in links <a href="/product/...">, may have classes like .title, .name
   - Price patterns: often have gradient backgrounds, classes with "price", may use special Unicode spaces
   - OZON specific: [data-widget="searchResultsV2"], span with background-image gradients for prices
   - Wildberries: .product-card structures
   - Look for data-testid attributes

3. PRODUCT PAGE (only for product):
   - H1 tags for titles
   - Price containers with special styling
   - Description blocks with [data-widget] or .description classes

4. FILTERS (if present):
   - Often in sidebar containers
   - Checkbox/radio groups for categories, price ranges
   - May use [data-widget*="filter"] patterns

5. NAVIGATION (if present):
   - Pagination with .pagination, .pager classes
   - Next/prev buttons may have "next", "prev" in classes or data attributes

6. REVIEWS (if present):
   - Review containers: [data-widget*="review"], .review, .feedback
   - Individual reviews with ratings, text content

ANALYSIS RULES:
- If element is NOT FOUND on the page, use null - DO NOT GUESS
- Prefer data-* attributes and modern CSS selectors
- Look for actual existing elements in the provided HTML
- Pay attention to marketplace-specific patterns (Ozon, Wildberries, etc.)
- Modern SPAs often use component-based class names and data attributes

IMPORTANT: Study the actual HTML structure provided. Look for:
- [data-widget] attributes (common in Ozon)
- [data-testid] attributes (common in modern React apps)
- Component-based class names
- Dynamically generated content

Return result STRICTLY in JSON format:

{{
    "success": true,
    "confidence": 0.95,
    "page_type": "main|category|search|product",
    "marketplace_structure": {{
        "marketplace_name": "Marketplace Name",
        "base_url": "https://domain.com",
        "search": {{
            "search_input_selector": "input[type='search']",
            "search_button_selector": "button[type='submit']",
            "search_form_selector": "form.search"
        }},
        "product": {{
            "container_selector": null,
            "title_selector": null,
            "price_selector": null,
            "link_selector": null,
            "image_selector": null,
            "rating_selector": null,
            "discount_selector": null
        }},
        "product_page": {{
            "title_selector": null,
            "price_selector": null,
            "description_selector": null,
            "specifications_selector": null,
            "images_selector": null,
            "availability_selector": null,
            "buy_button_selector": null
        }},
        "filters": [
            {{
                "name": "Price",
                "container_selector": ".price-filter",
                "options": [
                    {{
                        "name": "Up to 1000",
                        "selector": "input[data-price='1000']",
                        "value": "1000",
                        "filter_type": "checkbox"
                    }}
                ]
            }}
        ],
        "navigation": {{
            "pagination_selector": null,
            "next_page_selector": null,
            "prev_page_selector": null
        }},
        "reviews": {{
            "reviews_container_selector": null,
            "review_item_selector": null,
            "review_text_selector": null,
            "review_rating_selector": null,
            "review_author_selector": null,
            "review_date_selector": null,
            "reviews_link_selector": null
        }},
        "special_notes": "Special notes about working with this site"
    }}
}}

IMPORTANT:
- If filters are not found, use empty array: "filters": []
- If products are not found (e.g., on main page), all product selectors should be null
- DO NOT INVENT selectors - use only those that actually exist in HTML!
"""

        try:
            llm = get_llm()
            response = await llm.ask([{"role": "user", "content": prompt}])

            logger.info(f"LLM response length: {len(response)} characters")
            logger.debug(f"LLM response preview: {response[:200]}...")

            # Try multiple methods to extract JSON from response
            result_data = None

            # Method 1: Look for JSON between triple backticks
            json_match = re.search(
                r"```json\s*(\{.*?\})\s*```", response, re.DOTALL | re.IGNORECASE
            )
            if json_match:
                try:
                    result_data = json.loads(json_match.group(1))
                    logger.info("Successfully parsed JSON from code block")
                except json.JSONDecodeError:
                    pass

            # Method 2: Look for any JSON object in response
            if not result_data:
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    try:
                        result_data = json.loads(json_match.group())
                        logger.info("Successfully parsed JSON from response body")
                    except json.JSONDecodeError:
                        pass

            # Method 3: Try to find JSON within larger blocks
            if not result_data:
                # Look for JSON starting with specific patterns
                patterns = [
                    r'"success":\s*true.*?\}',
                    r'"success":\s*false.*?\}',
                    r'"marketplace_structure".*?\}\s*\}',
                ]

                for pattern in patterns:
                    match = re.search(r"\{.*?" + pattern, response, re.DOTALL)
                    if match:
                        try:
                            result_data = json.loads(match.group())
                            logger.info(
                                f"Successfully parsed JSON using pattern: {pattern[:20]}..."
                            )
                            break
                        except json.JSONDecodeError:
                            continue

            if not result_data:
                logger.error(
                    f"Failed to extract JSON from LLM response: {response[:500]}..."
                )
                return AnalysisResult(
                    success=False,
                    error_message="LLM did not return valid JSON",
                    confidence=0.0,
                    page_type="unknown",
                )

            # Create AnalysisResult from JSON
            analysis_result = AnalysisResult(**result_data)

            logger.info(
                f"LLM analysis completed with confidence {analysis_result.confidence}"
            )
            return analysis_result

        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
            return AnalysisResult(
                success=False,
                error_message=f"LLM analysis error: {str(e)}",
                confidence=0.0,
                page_type="unknown",
            )

    async def _search_products(
        self, url: str, query: str, max_results: int, filters: Optional[Dict] = None
    ) -> ToolResult:
        """Performs product search"""
        logger.info(f"Searching products: {query} on {url}")

        # Get structure for this domain
        domain = urlparse(url).netloc
        structure = self._analyzed_structures.get(domain)

        if not structure:
            # Analyze structure first
            analysis_result = await self._analyze_page_structure(url)
            if "Error" in analysis_result.output:
                return analysis_result
            structure = self._analyzed_structures.get(domain)

        if not structure:
            return ToolResult(error="Failed to determine page structure")

        page = await self._ensure_browser_ready()

        try:
            # Navigate to page if needed
            current_url = page.url
            if not current_url or urlparse(current_url).netloc != domain:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)

            # Find search field and enter query
            if not structure.search.search_input_selector:
                return ToolResult(error="Search field selector not defined")

            search_input = await page.query_selector(
                structure.search.search_input_selector
            )
            if not search_input:
                return ToolResult(
                    error=f"Search field not found by selector: {structure.search.search_input_selector}"
                )

            await search_input.click()
            await search_input.fill("")
            await asyncio.sleep(0.5)
            await search_input.type(query, delay=100)

            # Press Enter or search button
            if structure.search.search_button_selector:
                try:
                    search_button = await page.query_selector(
                        structure.search.search_button_selector
                    )
                    if search_button:
                        await search_button.click()
                    else:
                        await search_input.press("Enter")
                except:
                    await search_input.press("Enter")
            else:
                await search_input.press("Enter")

            # Wait for search results to load
            logger.info("Waiting for search results to load...")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(5)  # Additional time for JavaScript content loading

            # Ensure search results are loaded
            await self._ensure_content_loaded(page)

            # IMPORTANT: Re-analyze search results page structure
            # since it may differ from the main page
            logger.info("Re-analyzing search results page structure...")
            search_results_url = page.url

            # Get search results page HTML
            html_content = await page.content()
            cleaned_html = self._clean_html_for_analysis(html_content)

            # Analyze search results page structure with LLM
            search_structure_result = await self._analyze_html_with_llm(
                search_results_url, cleaned_html
            )

            if (
                search_structure_result.success
                and search_structure_result.marketplace_structure
            ):
                # Update structure for this domain
                search_structure = search_structure_result.marketplace_structure
                self._analyzed_structures[domain] = search_structure
                logger.info("Search results page structure successfully updated")
            else:
                logger.warning(
                    "Failed to analyze search results page structure, using original"
                )
                search_structure = structure

            # Additional wait for OZON (known to require more time)
            if "ozon" in domain.lower():
                logger.info("Additional wait for OZON...")
                await asyncio.sleep(3)

                # Scroll page to load products
                await page.evaluate("window.scrollTo(0, 500)")
                await asyncio.sleep(2)
                await page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(2)

            # Apply filters if needed
            if filters:
                await self._apply_filters_with_structure(
                    page, search_structure, filters
                )

            # Extract products with updated structure
            logger.info(
                f"Attempting product extraction with structure: {search_structure.product.container_selector}"
            )
            products = await self._extract_products_with_structure(
                page, search_structure, max_results
            )

            if not products:
                # If no products found, try alternative extraction methods
                logger.warning(
                    "Standard extraction yielded no results, trying alternative methods..."
                )
                products = await self._extract_products_alternative_methods(
                    page, domain, max_results
                )

            if not products:
                return ToolResult(
                    output="No products found. Page structure may be different or no results for query."
                )

            return ToolResult(
                output=f"Found products: {len(products)}\n\n"
                + "\n".join([f"{i+1}. {product}" for i, product in enumerate(products)])
            )

        except Exception as e:
            logger.error(f"Product search error: {e}")
            return ToolResult(error=f"Search error: {str(e)}")

    async def _extract_products_with_structure(
        self, page: Page, structure: MarketplaceStructure, max_results: int
    ) -> List[str]:
        """Extracts products using defined structure"""
        products = []

        try:
            # Check if product container selector exists
            if not structure.product.container_selector:
                logger.warning("Product container selector not defined in structure")
                return []

            logger.info(
                f"Looking for products using selector: {structure.product.container_selector}"
            )

            # Find product containers
            product_containers = await page.query_selector_all(
                structure.product.container_selector
            )

            logger.info(f"Found {len(product_containers)} product containers")

            if not product_containers:
                logger.warning(
                    f"No products found by primary selector: {structure.product.container_selector}"
                )
                # Try alternative selectors
                alternative_selectors = [
                    "[data-widget='searchResultsV2'] > div",
                    ".tile-root",
                    ".product-card",
                    ".goods-tile",
                    "[data-testid*='product']",
                    ".catalog-product",
                ]

                for alt_selector in alternative_selectors:
                    try:
                        product_containers = await page.query_selector_all(alt_selector)
                        if product_containers:
                            logger.info(
                                f"Found products by alternative selector: {alt_selector}"
                            )
                            break
                    except:
                        continue

                if not product_containers:
                    return []

            for i, container in enumerate(product_containers[:max_results]):
                try:
                    # Extract product data
                    extracted_product = (
                        await self._extract_single_product_with_structure(
                            container, structure
                        )
                    )

                    if extracted_product:
                        product_info = f"📦 {extracted_product.title}"
                        if extracted_product.price:
                            product_info += f"\n💰 {extracted_product.price}"
                        if extracted_product.link:
                            product_info += f"\n🔗 {extracted_product.link}"
                        if extracted_product.rating:
                            product_info += f"\n⭐ {extracted_product.rating}"
                        if extracted_product.discount:
                            product_info += f"\n🏷️ {extracted_product.discount}"

                        products.append(product_info)

                except Exception as e:
                    logger.warning(f"Error extracting product {i+1}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Product extraction error: {e}")

        return products

    async def _extract_single_product_with_structure(
        self, container, structure: MarketplaceStructure
    ) -> Optional[ExtractedProduct]:
        """Extracts single product data"""
        try:
            # Title - try several variants
            title = "Title not found"
            title_selectors = []

            if structure.product.title_selector:
                title_selectors.append(structure.product.title_selector)

            # Add common title selectors
            title_selectors.extend(
                [
                    "a[href*='/product/']",
                    "[data-testid*='title']",
                    ".title",
                    ".name",
                    ".product-name",
                    ".goods-tile-title",
                    "h3",
                    "h4",
                    "h5",
                    ".tsBodyL",
                ]
            )

            for title_selector in title_selectors:
                try:
                    title_element = await container.query_selector(title_selector)
                    if title_element:
                        title_text = await title_element.inner_text()
                        if title_text and len(title_text.strip()) > 2:
                            title = title_text.strip()
                            break
                except:
                    continue

            # Price - try several variants with priority for OZON
            price = None
            price_selectors = []

            if structure.product.price_selector:
                price_selectors.append(structure.product.price_selector)

            # Special selectors for OZON (from user memory)
            if "ozon" in structure.base_url.lower():
                price_selectors.extend(
                    [
                        "span.c35_3_1-a1.tsHeadline500Medium.c35_3_1-b1.c35_3_1-a6",
                        "span.tsHeadline500Medium",
                        "span[style*='background-image'][style*='linear-gradient']",
                    ]
                )

            # Add common price selectors
            price_selectors.extend(
                [
                    "[data-testid*='price']",
                    ".price",
                    ".cost",
                    ".tsHeadline500Medium",
                    "span[style*='background-image'][style*='linear-gradient']",
                    ".c35_3_1-a1",
                    "[class*='price']",
                ]
            )

            for price_selector in price_selectors:
                try:
                    price_element = await container.query_selector(price_selector)
                    if price_element:
                        price_text = await price_element.inner_text()
                        if price_text and any(char.isdigit() for char in price_text):
                            # Replace special symbols (important for OZON)
                            price = (
                                price_text.replace("\u2009", " ")
                                .replace("&thinsp;", " ")
                                .replace("\u00A0", " ")
                                .strip()
                            )
                            if price:
                                break
                except:
                    continue

            # Link
            link = None
            link_selectors = []

            if structure.product.link_selector:
                link_selectors.append(structure.product.link_selector)

            link_selectors.extend(
                ["a[href*='/product/']", "a[href*='/goods/']", "a[href]"]
            )

            for link_selector in link_selectors:
                try:
                    link_element = await container.query_selector(link_selector)
                    if link_element:
                        href = await link_element.get_attribute("href")
                        if href and ("/product/" in href or "/goods/" in href):
                            # Make absolute link
                            link = urljoin(structure.base_url, href)
                            break
                except:
                    continue

            # Rating
            rating = None
            if structure.product.rating_selector:
                try:
                    rating_element = await container.query_selector(
                        structure.product.rating_selector
                    )
                    if rating_element:
                        rating = await rating_element.inner_text()
                except:
                    pass

            # Discount
            discount = None
            if structure.product.discount_selector:
                try:
                    discount_element = await container.query_selector(
                        structure.product.discount_selector
                    )
                    if discount_element:
                        discount = await discount_element.inner_text()
                except:
                    pass

            # Image
            image = None
            if structure.product.image_selector:
                try:
                    image_element = await container.query_selector(
                        structure.product.image_selector
                    )
                    if image_element:
                        image = await image_element.get_attribute("src")
                except:
                    pass

            return ExtractedProduct(
                title=title.strip() if title else "Title not found",
                price=price.strip() if price else None,
                link=link,
                image=image,
                rating=rating.strip() if rating else None,
                discount=discount.strip() if discount else None,
            )

        except Exception as e:
            logger.warning(f"Error extracting product data: {e}")
            return None

    async def _apply_filters_with_structure(
        self, page: Page, structure: MarketplaceStructure, filters: Dict
    ) -> None:
        """Applies filters using structure"""
        try:
            for filter_name, filter_value in filters.items():
                # Find matching filter group
                matching_group = None
                for group in structure.filters:
                    if group.name.lower() == filter_name.lower():
                        matching_group = group
                        break

                if not matching_group:
                    logger.warning(f"Filter group '{filter_name}' not found")
                    continue

                # Apply filter
                await self._apply_single_filter(page, matching_group, filter_value)

        except Exception as e:
            logger.error(f"Error applying filters: {e}")

    async def _apply_single_filter(self, page: Page, filter_group, value: str) -> None:
        """Applies single filter"""
        try:
            # Find option with needed value
            for option in filter_group.options:
                if option.value and option.value.lower() == value.lower():
                    element = await page.query_selector(option.selector)
                    if element:
                        if option.filter_type == "checkbox":
                            await element.check()
                        elif option.filter_type == "radio":
                            await element.click()
                        elif option.filter_type == "input":
                            await element.fill(value)
                        elif option.filter_type == "select":
                            await element.select_option(value)

                        logger.info(f"Applied filter: {filter_group.name} = {value}")
                        return

            logger.warning(
                f"Filter option '{value}' not found in group '{filter_group.name}'"
            )

        except Exception as e:
            logger.error(f"Error applying filter {filter_group.name}: {e}")

    async def _get_product_info(self, product_url: str) -> ToolResult:
        """Gets detailed product information"""
        logger.info(f"Getting product information: {product_url}")

        # Determine structure for domain
        domain = urlparse(product_url).netloc
        structure = self._analyzed_structures.get(domain)

        if not structure:
            # Analyze structure
            analysis_result = await self._analyze_page_structure(product_url)
            if "Error" in analysis_result.output:
                return analysis_result
            structure = self._analyzed_structures.get(domain)

        if not structure:
            return ToolResult(error="Failed to determine product page structure")

        page = await self._ensure_browser_ready()

        try:
            await page.goto(
                product_url,
                wait_until="networkidle",
                timeout=self.marketplace_config.page_load_timeout,
            )
            await asyncio.sleep(3)

            # Extract product information
            product_info = await self._extract_product_page_info(page, structure)

            return ToolResult(output=product_info)

        except Exception as e:
            logger.error(f"Error getting product information: {e}")
            return ToolResult(error=f"Error: {str(e)}")

    async def _extract_product_page_info(
        self, page: Page, structure: MarketplaceStructure
    ) -> str:
        """Extracts information from product page"""
        try:
            info_parts = []

            # Title - try several selectors
            title = "Title not found"
            title_selectors = []

            if structure.product_page.title_selector:
                title_selectors.append(structure.product_page.title_selector)

            title_selectors.extend(
                [
                    "h1",
                    "[data-testid*='title']",
                    ".product-title",
                    ".pdp-product-name",
                    ".goods-name",
                ]
            )

            for title_selector in title_selectors:
                try:
                    title_element = await page.query_selector(title_selector)
                    if title_element:
                        title_text = await title_element.inner_text()
                        if title_text and len(title_text.strip()) > 2:
                            title = title_text.strip()
                            break
                except:
                    continue

            info_parts.append(f"📦 PRODUCT: {title}")

            # Price - try several selectors with priority for OZON
            price = "Price not found"
            price_selectors = []

            if structure.product_page.price_selector:
                price_selectors.append(structure.product_page.price_selector)

            # Special selectors for OZON (from user memory)
            if "ozon" in structure.base_url.lower():
                price_selectors.extend(
                    [
                        "span.c35_3_1-a1.tsHeadline500Medium.c35_3_1-b1.c35_3_1-a6",
                        "span.tsHeadline500Medium",
                        "span[style*='background-image'][style*='linear-gradient']",
                    ]
                )

            price_selectors.extend(
                [
                    "[data-testid*='price']",
                    ".price",
                    ".product-price",
                    ".tsHeadline500Medium",
                    "span[style*='background-image'][style*='linear-gradient']",
                ]
            )

            for price_selector in price_selectors:
                try:
                    price_element = await page.query_selector(price_selector)
                    if price_element:
                        price_text = await price_element.inner_text()
                        if price_text and any(char.isdigit() for char in price_text):
                            # Replace special symbols (important for OZON)
                            price = (
                                price_text.replace("\u2009", " ")
                                .replace("&thinsp;", " ")
                                .replace("\u00A0", " ")
                                .strip()
                            )
                            if price:
                                break
                except:
                    continue

            info_parts.append(f"💰 PRICE: {price}")

            # Description
            if structure.product_page.description_selector:
                try:
                    desc_element = await page.query_selector(
                        structure.product_page.description_selector
                    )
                    if desc_element:
                        description = await desc_element.inner_text()
                        if description:
                            desc_short = (
                                description[:300] + "..."
                                if len(description) > 300
                                else description
                            )
                            info_parts.append(f"📝 DESCRIPTION: {desc_short}")
                except:
                    pass

            # Specifications
            if structure.product_page.specifications_selector:
                try:
                    spec_element = await page.query_selector(
                        structure.product_page.specifications_selector
                    )
                    if spec_element:
                        specifications = await spec_element.inner_text()
                        if specifications:
                            spec_short = (
                                specifications[:200] + "..."
                                if len(specifications) > 200
                                else specifications
                            )
                            info_parts.append(f"📋 SPECIFICATIONS: {spec_short}")
                except:
                    pass

            # Availability
            if structure.product_page.availability_selector:
                try:
                    avail_element = await page.query_selector(
                        structure.product_page.availability_selector
                    )
                    if avail_element:
                        availability = await avail_element.inner_text()
                        if availability:
                            info_parts.append(f"📦 AVAILABILITY: {availability}")
                except:
                    pass

            return "\n\n".join(info_parts)

        except Exception as e:
            logger.error(f"Error extracting product information: {e}")
            return f"Information extraction error: {str(e)}"

    async def _get_reviews(self, product_url: str, max_reviews: int = 50) -> ToolResult:
        """Gets product reviews"""
        logger.info(f"Getting reviews for product: {product_url}")

        page = await self._ensure_browser_ready()

        try:
            await page.goto(
                product_url,
                wait_until="networkidle",
                timeout=self.marketplace_config.page_load_timeout,
            )
            await asyncio.sleep(3)

            # Прокручиваем страницу для загрузки всех элементов
            await self._ensure_content_loaded(page)

            # Находим ссылку на отзывы, используя улучшенную логику
            reviews_url = await self._find_reviews_link(page, product_url)

            if not reviews_url:
                return ToolResult(error="Reviews link not found on product page")

            logger.info(f"Found reviews URL: {reviews_url}")

            # Переходим на страницу отзывов
            await page.goto(
                reviews_url,
                wait_until="networkidle",
                timeout=self.marketplace_config.page_load_timeout,
            )
            await asyncio.sleep(5)  # Больше времени для загрузки отзывов

            # Прокручиваем страницу отзывов для загрузки контента
            await self._ensure_content_loaded(page)

            # Загружаем дополнительные отзывы если их много
            await self._load_more_reviews(page, max_reviews)

            # Дополнительное ожидание для JavaScript-рендеринга отзывов
            await asyncio.sleep(3)

            # Извлекаем отзывы используя улучшенную логику
            reviews = await self._extract_reviews_improved(page, max_reviews)

            if not reviews:
                return ToolResult(error="Reviews not found on reviews page")

            return ToolResult(
                output=f"Found reviews: {len(reviews)}\n\n" + "\n---\n".join(reviews)
            )

        except Exception as e:
            logger.error(f"Error getting reviews: {e}")
            return ToolResult(error=f"Error: {str(e)}")

    async def _extract_reviews_with_structure(
        self, page: Page, structure: MarketplaceStructure
    ) -> List[str]:
        """Extracts reviews using structure"""
        reviews = []

        try:
            if not structure.reviews or not structure.reviews.review_item_selector:
                logger.warning("Reviews structure not defined")
                return []

            # Find reviews
            review_containers = await page.query_selector_all(
                structure.reviews.review_item_selector
            )

            if not review_containers:
                logger.warning(
                    f"Reviews not found by selector: {structure.reviews.review_item_selector}"
                )

                # Try alternative selectors
                alternative_selectors = [
                    ".review",
                    ".comment",
                    "[data-testid*='review']",
                    ".user-review",
                    ".feedback-item",
                ]

                for alt_selector in alternative_selectors:
                    try:
                        review_containers = await page.query_selector_all(alt_selector)
                        if review_containers:
                            logger.info(
                                f"Found reviews by alternative selector: {alt_selector}"
                            )
                            break
                    except:
                        continue

                if not review_containers:
                    return []

            for container in review_containers[:20]:  # Maximum 20 reviews
                try:
                    extracted_review = await self._extract_single_review_with_structure(
                        container, structure
                    )

                    if extracted_review and extracted_review.text:
                        review_info = f"👤 {extracted_review.author or 'Anonymous'}"
                        if extracted_review.rating:
                            review_info += f"\n⭐ {extracted_review.rating}"
                        if extracted_review.date:
                            review_info += f"\n📅 {extracted_review.date}"
                        review_info += f"\n💬 {extracted_review.text[:400]}{'...' if len(extracted_review.text) > 400 else ''}"

                        reviews.append(review_info)

                except Exception as e:
                    logger.warning(f"Error extracting review: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error extracting reviews: {e}")

        return reviews

    async def _extract_single_review_with_structure(
        self, container, structure: MarketplaceStructure
    ) -> Optional[ExtractedReview]:
        """Extracts single review"""
        try:
            if not structure.reviews:
                return None

            # Review text - try several selectors
            text = ""
            text_selectors = []

            if structure.reviews.review_text_selector:
                text_selectors.append(structure.reviews.review_text_selector)

            text_selectors.extend(
                [
                    ".review-text",
                    ".comment-text",
                    ".feedback-text",
                    "[data-testid*='text']",
                    "p",
                    ".content",
                ]
            )

            for text_selector in text_selectors:
                try:
                    text_element = await container.query_selector(text_selector)
                    if text_element:
                        text_content = await text_element.inner_text()
                        if text_content and len(text_content.strip()) > 10:
                            text = text_content.strip()
                            break
                except:
                    continue

            if not text or len(text.strip()) < 10:
                return None

            # Rating
            rating = None
            if structure.reviews.review_rating_selector:
                try:
                    rating_element = await container.query_selector(
                        structure.reviews.review_rating_selector
                    )
                    if rating_element:
                        rating = await rating_element.inner_text()
                except:
                    pass

            # Author
            author = None
            if structure.reviews.review_author_selector:
                try:
                    author_element = await container.query_selector(
                        structure.reviews.review_author_selector
                    )
                    if author_element:
                        author = await author_element.inner_text()
                except:
                    pass

            # Date
            date = None
            if structure.reviews.review_date_selector:
                try:
                    date_element = await container.query_selector(
                        structure.reviews.review_date_selector
                    )
                    if date_element:
                        date = await date_element.inner_text()
                except:
                    pass

            return ExtractedReview(
                text=text.strip(),
                rating=rating.strip() if rating else None,
                author=author.strip() if author else None,
                date=date.strip() if date else None,
            )

        except Exception as e:
            logger.warning(f"Error extracting review: {e}")
            return None

    async def _apply_filters(self, filters: Dict) -> ToolResult:
        """Applies filters on current page"""
        try:
            page = await self._ensure_browser_ready()
            current_url = page.url
            domain = urlparse(current_url).netloc
            structure = self._analyzed_structures.get(domain)

            if not structure:
                return ToolResult(error="Page structure not defined")

            await self._apply_filters_with_structure(page, structure, filters)

            # Wait for results update
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(2)

            return ToolResult(output="Filters applied successfully")

        except Exception as e:
            logger.error(f"Error applying filters: {e}")
            return ToolResult(error=f"Error: {str(e)}")

    async def _navigate_page(self, page_number: int) -> ToolResult:
        """Page navigation"""
        try:
            page = await self._ensure_browser_ready()
            current_url = page.url
            domain = urlparse(current_url).netloc
            structure = self._analyzed_structures.get(domain)

            if not structure or not structure.navigation:
                return ToolResult(error="Navigation not supported for this site")

            # Find pagination
            if structure.navigation.next_page_selector and page_number > 1:
                next_button = await page.query_selector(
                    structure.navigation.next_page_selector
                )
                if next_button:
                    await next_button.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    return ToolResult(output=f"Navigated to page {page_number}")

            return ToolResult(error="Navigation to specified page is not possible")

        except Exception as e:
            logger.error(f"Navigation error: {e}")
            return ToolResult(error=f"Error: {str(e)}")

    async def _close_browser(self) -> ToolResult:
        """Closes browser"""
        logger.info("Closing browser...")

        try:
            if self._page:
                await self._page.close()
                self._page = None

            if self._context:
                await self._context.close()
                self._context = None

            if self._browser:
                await self._browser.close()
                self._browser = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

            # Clear cache
            self._analyzed_structures.clear()

            logger.info("Browser closed successfully")
            return ToolResult(output="Browser closed successfully")

        except Exception as e:
            logger.error(f"Browser closing error: {e}")
            # Force clear state
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._analyzed_structures.clear()
            return ToolResult(error=f"Closing error: {str(e)}")

    async def cleanup(self):
        """Resource cleanup"""
        try:
            await self._close_browser()
        except Exception as e:
            logger.error(f"Error during MarketplaceAnalyzer cleanup: {e}")

    async def _extract_products_alternative_methods(
        self, page: Page, domain: str, max_results: int
    ) -> List[str]:
        """Alternative product extraction methods for complex cases"""
        products = []

        try:
            logger.info("Attempting alternative product extraction...")

            # Specific selectors for OZON
            if "ozon" in domain.lower():
                alternative_selectors = [
                    # Main OZON product containers
                    "[data-widget='searchResultsV2'] > div > div",
                    "[data-widget='searchResultsV2'] [data-index]",
                    ".tile-root",
                    "[data-widget='searchResultsV2'] a[href*='/product/']",
                    "div[data-testid*='tile']",
                    # Try to find any product links
                    "a[href*='/product/']",
                ]
            else:
                # General selectors for other marketplaces
                alternative_selectors = [
                    ".product-card",
                    ".product-item",
                    ".goods-tile",
                    "[data-testid*='product']",
                    ".catalog-product",
                    "a[href*='/product/']",
                    "a[href*='/goods/']",
                    ".product",
                ]

            for selector in alternative_selectors:
                try:
                    logger.info(f"Trying selector: {selector}")
                    elements = await page.query_selector_all(selector)

                    if elements:
                        logger.info(
                            f"Found {len(elements)} elements by selector {selector}"
                        )

                        for i, element in enumerate(elements[:max_results]):
                            try:
                                product_info = await self._extract_product_basic_info(
                                    element, domain
                                )
                                if product_info:
                                    products.append(product_info)
                                    logger.info(
                                        f"Extracted product {i+1}: {product_info[:50]}..."
                                    )
                            except Exception as e:
                                logger.warning(f"Error extracting product {i+1}: {e}")
                                continue

                        if products:
                            logger.info(
                                f"Successfully extracted {len(products)} products"
                            )
                            break

                except Exception as e:
                    logger.warning(f"Error with selector {selector}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Alternative extraction error: {e}")

        return products

    async def _find_reviews_link(self, page: Page, product_url: str) -> Optional[str]:
        """Находит ссылку на отзывы на странице товара используя LLM"""
        try:
            logger.info("Поиск ссылки на отзывы с помощью LLM...")

            # Получаем HTML контент страницы
            html_content = await page.content()
            cleaned_html = self._clean_html_for_analysis(html_content)

            # Анализируем HTML с помощью LLM для поиска ссылки на отзывы
            reviews_link = await self._find_reviews_link_with_llm(
                product_url, cleaned_html
            )

            if reviews_link:
                # Проверяем, что ссылка валидна и делаем её абсолютной
                if reviews_link.startswith("/"):
                    reviews_link = urljoin(product_url, reviews_link)
                elif not reviews_link.startswith("http"):
                    reviews_link = urljoin(product_url, reviews_link)

                logger.info(f"LLM нашел ссылку на отзывы: {reviews_link}")
                return reviews_link

            logger.warning("LLM не смог найти ссылку на отзывы")
            return None

        except Exception as e:
            logger.error(f"Ошибка поиска ссылки на отзывы: {e}")
            return None

    async def _find_reviews_link_with_llm(
        self, product_url: str, html: str
    ) -> Optional[str]:
        """Анализирует HTML с помощью LLM для поиска ссылки на отзывы"""

        prompt = f"""
Проанализируй HTML страницы товара и найди ссылку на отзывы.

URL страницы: {product_url}

HTML код:
{html}

ЗАДАЧА:
Найди ссылку, которая ведет на страницу отзывов о товаре. Это может быть:
- Ссылка содержащая "/reviews/"
- Ссылка содержащая "/review/"
- Ссылка содержащая "/comments/"
- Ссылка содержащая "/feedback/"
- Ссылка в тексте которой упоминаются "отзывы", "комментарии", "reviews"

ИНСТРУКЦИИ:
1. Внимательно изучи HTML код
2. Найди все ссылки (элементы <a href="...">)
3. Определи какая из них ведет на отзывы
4. Верни ТОЛЬКО относительный или абсолютный URL ссылки
5. Если ссылка не найдена, верни "NOT_FOUND"

ВАЖНО:
- Ищи именно ссылку на отзывы о данном товаре
- НЕ выдумывай ссылки - используй только те, что есть в HTML
- Возвращай только сам URL без дополнительного текста

Ответ (только URL или NOT_FOUND):
"""

        try:
            llm = get_llm()
            response = await llm.ask([{"role": "user", "content": prompt}])

            logger.info(f"LLM ответ для поиска ссылки на отзывы: {response}")

            # Очищаем ответ от лишних символов
            response = response.strip()

            if response == "NOT_FOUND" or not response:
                return None

            # Убираем возможные markdown символы
            response = response.replace("`", "").replace('"', "").replace("'", "")

            # Проверяем что это похоже на URL
            if response.startswith("http") or response.startswith("/"):
                return response

            return None

        except Exception as e:
            logger.error(f"Ошибка LLM анализа для поиска ссылки на отзывы: {e}")
            return None

    async def _load_more_reviews(self, page: Page, max_reviews: int) -> None:
        """Загружает дополнительные отзывы на странице (пагинация, прокрутка)"""
        try:
            logger.info(f"Попытка загрузить больше отзывов (цель: {max_reviews})...")

            # Метод 1: Прокрутка страницы для ленивой загрузки
            for scroll_attempt in range(
                self.marketplace_config.scroll_attempts
            ):  # Используем настройку из конфига
                current_height = await page.evaluate("document.body.scrollHeight")

                # Прокручиваем вниз
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                # Проверяем, изменилась ли высота страницы (загрузился ли новый контент)
                new_height = await page.evaluate("document.body.scrollHeight")

                if new_height == current_height:
                    logger.info(
                        f"Прокрутка {scroll_attempt + 1}: Контент не загружается"
                    )
                    break
                else:
                    logger.info(
                        f"Прокрутка {scroll_attempt + 1}: Загружен новый контент"
                    )

            # Метод 2: Поиск и клик по кнопкам "Показать еще" / "Загрузить еще"
            load_more_selectors = [
                'button:has-text("Показать еще")',
                'button:has-text("Загрузить еще")',
                'button:has-text("Еще отзывы")',
                'button:has-text("Show more")',
                'button:has-text("Load more")',
                'a:has-text("Показать еще")',
                'a:has-text("Загрузить еще")',
                '[data-testid*="load-more"]',
                '[data-testid*="show-more"]',
                ".load-more",
                ".show-more",
            ]

            for selector in load_more_selectors:
                try:
                    # Ищем кнопку "показать еще"
                    load_more_button = await page.query_selector(selector)
                    if load_more_button:
                        # Проверяем, что кнопка видима и доступна
                        is_visible = await load_more_button.is_visible()
                        if is_visible:
                            logger.info(f"Найдена кнопка загрузки: {selector}")

                            # Кликаем несколько раз для загрузки большего количества отзывов
                            for click_attempt in range(
                                self.marketplace_config.load_more_clicks
                            ):
                                try:
                                    await load_more_button.click()
                                    await asyncio.sleep(3)  # Ждем загрузки

                                    # Проверяем, что кнопка все еще доступна
                                    if not await load_more_button.is_visible():
                                        logger.info(
                                            "Кнопка исчезла - все отзывы загружены"
                                        )
                                        break

                                except Exception as e:
                                    logger.warning(
                                        f"Ошибка клика по кнопке (попытка {click_attempt + 1}): {e}"
                                    )
                                    break

                            break  # Найдли и использовали кнопку, прекращаем поиск

                except Exception as e:
                    # Игнорируем ошибки селекторов
                    continue

            # Метод 3: Поиск пагинации
            pagination_selectors = [
                'a:has-text("Следующая")',
                'a:has-text("Next")',
                'a:has-text(">")',
                ".pagination a[href]",
                '[data-testid*="next"]',
                ".next-page",
            ]

            for selector in pagination_selectors:
                try:
                    next_button = await page.query_selector(selector)
                    if next_button and await next_button.is_visible():
                        logger.info(f"Найдена пагинация: {selector}")

                        # Переходим на следующие страницы
                        for page_attempt in range(
                            self.marketplace_config.pagination_pages
                        ):
                            try:
                                await next_button.click()
                                await page.wait_for_load_state(
                                    "networkidle", timeout=10000
                                )
                                await asyncio.sleep(2)

                                # Обновляем ссылку на кнопку следующей страницы
                                next_button = await page.query_selector(selector)
                                if (
                                    not next_button
                                    or not await next_button.is_visible()
                                ):
                                    logger.info("Достигнута последняя страница")
                                    break

                            except Exception as e:
                                logger.warning(
                                    f"Ошибка перехода на страницу {page_attempt + 1}: {e}"
                                )
                                break

                        break  # Нашли пагинацию, прекращаем поиск

                except Exception:
                    continue

            # Финальная прокрутка для обеспечения загрузки всего контента
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

            logger.info("Завершена попытка загрузки дополнительных отзывов")

        except Exception as e:
            logger.warning(f"Ошибка при загрузке дополнительных отзывов: {e}")

    async def _extract_reviews_improved(
        self, page: Page, max_reviews: int = 50
    ) -> List[str]:
        """Универсальное извлечение отзывов с помощью LLM"""
        try:
            logger.info(
                f"Начинаем извлечение отзывов с помощью LLM (лимит: {max_reviews})..."
            )

            # Получаем HTML контент страницы отзывов
            html_content = await page.content()
            cleaned_html = self._clean_html_for_analysis(html_content)

            # Анализируем HTML с помощью LLM для извлечения отзывов
            reviews = await self._extract_reviews_with_llm(
                page.url, cleaned_html, max_reviews
            )

            logger.info(f"LLM извлек {len(reviews)} отзывов")
            return reviews

        except Exception as e:
            logger.error(f"Ошибка извлечения отзывов: {e}")
            return []

    async def _extract_reviews_with_llm(
        self, reviews_url: str, html: str, max_reviews: int = 50
    ) -> List[str]:
        """Универсальное извлечение отзывов с помощью LLM"""

        prompt = f"""
Проанализируй HTML страницы отзывов и извлеки все отзывы.

URL страницы: {reviews_url}

HTML код:
{html}

ЗАДАЧА:
Найди и извлеки все отзывы пользователей на странице. Для каждого отзыва попытайся найти:
- Автор отзыва (имя пользователя)
- Рейтинг/оценка (звезды, баллы)
- Дата написания отзыва
- Текст отзыва

ИНСТРУКЦИИ:
1. Внимательно изучи HTML код
2. Найди блоки, содержащие отзывы пользователей
3. Извлеки информацию из каждого отзыва
4. Верни данные в формате JSON массива

ФОРМАТ ОТВЕТА:
Верни ТОЛЬКО JSON массив объектов в формате:
[
  {{
    "author": "Имя автора или 'Аноним'",
    "rating": "Рейтинг или null",
    "date": "Дата или null",
    "text": "Текст отзыва"
  }}
]

 ВАЖНО:
 - Включай только настоящие отзывы пользователей, НЕ описания товара
 - Текст отзыва должен быть не менее 10 символов
 - Если данные не найдены, используй null для rating/date и "Аноним" для author
 - Максимум {max_reviews} отзывов (извлекай все найденные отзывы до этого лимита)
 - НЕ выдумывай отзывы - используй только те, что есть в HTML
 - Возвращай ТОЛЬКО JSON, никакого дополнительного текста

Ответ:
"""

        try:
            llm = get_llm()
            response = await llm.ask([{"role": "user", "content": prompt}])

            logger.info(
                f"LLM ответ для извлечения отзывов (первые 200 символов): {response[:200]}..."
            )

            # Очищаем ответ и извлекаем JSON
            response = response.strip()

            # Ищем JSON в ответе
            import re

            json_match = re.search(r"\[.*\]", response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                try:
                    import json

                    reviews_data = json.loads(json_str)

                    # Конвертируем в нужный формат
                    formatted_reviews = []
                    for review in reviews_data:
                        if isinstance(review, dict) and "text" in review:
                            # Проверяем что текст достаточно длинный
                            text = review.get("text", "").strip()
                            if len(text) >= 10:
                                formatted_review = (
                                    f"👤 {review.get('author', 'Аноним')}"
                                )

                                if review.get("rating"):
                                    formatted_review += f"\n⭐ {review['rating']}"

                                if review.get("date"):
                                    formatted_review += f"\n📅 {review['date']}"

                                # Ограничиваем длину текста
                                max_text_length = 400
                                if len(text) > max_text_length:
                                    text = text[:max_text_length] + "..."

                                formatted_review += f"\n💬 {text}"
                                formatted_reviews.append(formatted_review)

                    logger.info(f"Успешно обработано {len(formatted_reviews)} отзывов")
                    return formatted_reviews

                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга JSON отзывов: {e}")
                    return []
            else:
                logger.warning("JSON не найден в ответе LLM")
                return []

        except Exception as e:
            logger.error(f"Ошибка LLM анализа отзывов: {e}")
            return []

    async def _extract_product_basic_info(self, element, domain: str) -> Optional[str]:
        """Basic product information extraction"""
        try:
            # Extract title
            title = "Title not found"
            title_selectors = ["span", "a", "h1", "h2", "h3", "h4", ".title", ".name"]

            for title_selector in title_selectors:
                try:
                    title_element = await element.query_selector(title_selector)
                    if title_element:
                        title_text = await title_element.inner_text()
                        if (
                            title_text
                            and len(title_text.strip()) > 5
                            and not title_text.strip().isdigit()
                        ):
                            title = title_text.strip()[:100]  # Limit length
                            break
                except:
                    continue

            # Extract price
            price = None
            price_selectors = ["span", "div", ".price", "[data-testid*='price']"]

            # Special selectors for OZON
            if "ozon" in domain.lower():
                price_selectors.insert(
                    0, "span[style*='background-image'][style*='linear-gradient']"
                )
                price_selectors.insert(1, ".tsHeadline500Medium")

            for price_selector in price_selectors:
                try:
                    price_element = await element.query_selector(price_selector)
                    if price_element:
                        price_text = await price_element.inner_text()
                        if (
                            price_text
                            and any(char.isdigit() for char in price_text)
                            and (
                                "₽" in price_text
                                or "руб" in price_text
                                or price_text.replace(" ", "")
                                .replace(",", "")
                                .replace(".", "")
                                .isdigit()
                            )
                        ):
                            price = (
                                price_text.replace("\u2009", " ")
                                .replace("&thinsp;", " ")
                                .replace("\u00A0", " ")
                                .strip()
                            )
                            break
                except:
                    continue

            # Extract link
            link = None
            try:
                # First check if element itself is a link
                href = await element.get_attribute("href")
                if href and ("/product/" in href or "/goods/" in href):
                    link = (
                        href if href.startswith("http") else f"https://{domain}{href}"
                    )
                else:
                    # Find link inside element
                    link_element = await element.query_selector(
                        "a[href*='/product/'], a[href*='/goods/']"
                    )
                    if link_element:
                        href = await link_element.get_attribute("href")
                        if href:
                            link = (
                                href
                                if href.startswith("http")
                                else f"https://{domain}{href}"
                            )
            except:
                pass

            # Format result
            if title != "Title not found":
                product_info = f"📦 {title}"
                if price:
                    product_info += f"\n💰 {price}"
                if link:
                    product_info += f"\n🔗 {link}"
                return product_info

        except Exception as e:
            logger.warning(f"Error extracting basic information: {e}")

        return None
