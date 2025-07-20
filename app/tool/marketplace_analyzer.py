import asyncio
import json
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page, async_playwright
from pydantic import Field

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
                "description": "Maximum number of results (default 10)",
                "default": 10,
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
        max_results: int = 10,
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
            page_number: Page number
        """
        try:
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
                return await self._get_reviews(product_url)

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
            headless=False,  # Show browser for debugging
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
            # Navigate to page
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            # Get HTML content
            html_content = await page.content()

            # Clean HTML for analysis (remove unnecessary parts)
            cleaned_html = self._clean_html_for_analysis(html_content)

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

    def _clean_html_for_analysis(self, html: str) -> str:
        """Cleans HTML for LLM analysis"""
        # Remove scripts and styles
        html = re.sub(
            r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        html = re.sub(
            r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE
        )

        # Remove comments
        html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

        # Remove extra whitespace
        html = re.sub(r"\s+", " ", html)

        # Limit size (take first 15000 characters)
        if len(html) > 15000:
            html = html[:15000] + "..."

        return html.strip()

    async def _analyze_html_with_llm(self, url: str, html: str) -> AnalysisResult:
        """Analyzes HTML using LLM to determine structure"""

        prompt = f"""
Analyze the HTML code of a marketplace page and determine its structure.

Page URL: {url}

HTML code:
{html}

IMPORTANT: Determine the page type and return selectors only for elements that are actually present on the page.

PAGE TYPES:
- main: main page (may not contain product lists)
- category: category page (should contain product lists)
- search: search results page (should contain product lists)
- product: individual product page

FOR EACH PAGE TYPE FIND THE FOLLOWING ELEMENTS (IF THEY EXIST):

1. SEARCH (usually present on all pages):
   - Search input field
   - Search button (if there's a separate button)
   - Search form

2. PRODUCTS IN LIST (only for category/search):
   - Single product container
   - Product title
   - Product price
   - Product link
   - Product image
   - Rating (if present)
   - Discount (if present)

3. PRODUCT PAGE (only for product):
   - Product title
   - Product price
   - Description
   - Specifications
   - Images
   - Availability

4. FILTERS (if present):
   - Filter groups with their options

5. NAVIGATION (if present):
   - Pagination
   - Next/previous page buttons

6. REVIEWS (if present):
   - Reviews container
   - Individual review
   - Review text
   - Review rating
   - Review author

RULES:
- If element is NOT FOUND on the page, use null
- Be precise with CSS selectors
- Study HTML structure carefully
- For main page, product lists may be absent - this is normal

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

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if not json_match:
                return AnalysisResult(
                    success=False,
                    error_message="LLM did not return valid JSON",
                    confidence=0.0,
                    page_type="unknown",
                )

            result_data = json.loads(json_match.group())

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
            products = await self._extract_products_with_structure(
                page, search_structure, max_results
            )

            if not products:
                # If no products found, try alternative extraction methods
                logger.info(
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
                logger.warning("Product container selector not defined")
                return []

            # Find product containers
            product_containers = await page.query_selector_all(
                structure.product.container_selector
            )

            if not product_containers:
                logger.warning(
                    f"No products found by selector: {structure.product.container_selector}"
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
            await page.goto(product_url, wait_until="networkidle", timeout=30000)
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

    async def _get_reviews(self, product_url: str) -> ToolResult:
        """Gets product reviews"""
        logger.info(f"Getting reviews for product: {product_url}")

        # Determine structure for domain
        domain = urlparse(product_url).netloc
        structure = self._analyzed_structures.get(domain)

        if not structure or not structure.reviews:
            return ToolResult(error="Reviews structure not defined for this site")

        page = await self._ensure_browser_ready()

        try:
            await page.goto(product_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            # Find reviews link or extract reviews directly from page
            if structure.reviews.reviews_link_selector:
                # Navigate to reviews page
                reviews_link = await page.query_selector(
                    structure.reviews.reviews_link_selector
                )
                if reviews_link:
                    href = await reviews_link.get_attribute("href")
                    if href:
                        reviews_url = urljoin(product_url, href)
                        await page.goto(
                            reviews_url, wait_until="networkidle", timeout=30000
                        )
                        await asyncio.sleep(3)

            # Extract reviews
            reviews = await self._extract_reviews_with_structure(page, structure)

            if not reviews:
                return ToolResult(error="Reviews not found")

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
