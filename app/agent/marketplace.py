from typing import List, Optional

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.config import Config, MarketplaceSettings
from app.tool import Terminate, ToolCollection
from app.tool.marketplace_analyzer import MarketplaceAnalyzer

MARKETPLACE_SYSTEM_PROMPT = """
You are a universal agent for working with ANY online stores and marketplaces.

You have access to marketplace_analyzer - a tool that uses LLM to analyze the structure of any marketplace.

YOUR SPECIALIZATION:
1. Working with ANY marketplaces (Ozon, Wildberries, AliExpress, Amazon, eBay, etc.)
2. Automatic site structure analysis through LLM
3. Product search by any criteria
4. Price analysis and finding best offers
5. Extracting and analyzing customer reviews
6. Product comparison and recommendations
7. Working with filters and navigation

WORKFLOW:
1. Receive user request with marketplace URL
2. Analyze page structure through marketplace_analyzer
3. Perform product search or other actions
4. Extract necessary information
5. Analyze reviews if needed
6. Provide detailed analysis and recommendations
7. Close browser when finished

KEY FEATURES:
- Automatic selector determination through LLM
- Working with any marketplace structure
- Intelligent data extraction
- Filter analysis and application
- Result page navigation

RESPONSE STRUCTURE:
1. Analysis of found products
2. Price and feature comparison
3. Review analysis (if requested)
4. Your recommendations
5. Product links
6. Final conclusions

IMPORTANT: Always finish work by closing the browser!
"""


class MarketplaceAgent(ToolCallAgent):
    """
    Universal agent for working with any marketplaces

    Uses LLM to analyze site structure and can work
    with any online stores without prior configuration.
    """

    name: str = "marketplace"
    description: str = (
        "Universal agent for working with any marketplaces. "
        "Uses LLM for automatic site structure analysis."
    )

    # Configuration fields
    config: Config = Field(default_factory=Config, exclude=True)
    marketplace_config: MarketplaceSettings = Field(default=None, exclude=True)

    def __init__(self, **kwargs):
        if "config" not in kwargs:
            kwargs["config"] = Config()
        if "marketplace_config" not in kwargs:
            kwargs["marketplace_config"] = kwargs["config"].marketplace_config
        super().__init__(**kwargs)

    system_prompt: str = MARKETPLACE_SYSTEM_PROMPT
    next_step_prompt: str = (
        "Use marketplace_analyzer to execute the next step of the user's task."
    )

    max_observe: int = 15000
    max_steps: int = 20

    # Only marketplace_analyzer and terminate
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            MarketplaceAnalyzer(),
            Terminate(),
        )
    )

    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    async def cleanup(self):
        """Agent resource cleanup"""
        # Close browser before finishing work
        marketplace_tool = self.available_tools.get_tool("marketplace_analyzer")
        if marketplace_tool and isinstance(marketplace_tool, MarketplaceAnalyzer):
            await marketplace_tool.cleanup()

        # Call parent cleanup method
        await super().cleanup()

    async def analyze_marketplace(self, url: str) -> str:
        """
        Marketplace structure analysis

        Args:
            url: Marketplace URL for analysis

        Returns:
            Structure analysis result
        """
        return await self.run(f"Analyze marketplace structure: {url}")

    async def search_and_compare(
        self,
        marketplace_url: str,
        query: str,
        max_results: int = 10,
        price_limit: Optional[int] = None,
        analyze_reviews: bool = True,
    ) -> str:
        """
        Product search and comparison

        Args:
            marketplace_url: Marketplace URL
            query: Search query
            max_results: Maximum number of results
            price_limit: Price limit
            analyze_reviews: Whether to analyze reviews

        Returns:
            Search and analysis result
        """
        request = f"Find products on {marketplace_url} by query '{query}'"

        if max_results != 10:
            request += f", maximum {max_results} results"

        if price_limit:
            request += f", not more expensive than {price_limit} rubles"

        if analyze_reviews:
            request += ". Also analyze reviews to assess product quality"

        return await self.run(request)

    async def compare_products_by_urls(
        self, product_urls: List[str], analyze_reviews: bool = True
    ) -> str:
        """
        Product comparison by URLs

        Args:
            product_urls: List of product URLs
            analyze_reviews: Whether to analyze reviews

        Returns:
            Comparative product analysis
        """
        urls_text = "\n".join([f"- {url}" for url in product_urls])
        request = f"Compare products by these links:\n{urls_text}"

        if analyze_reviews:
            request += "\n\nAlso analyze reviews for each product"

        return await self.run(request)

    async def find_best_deals(
        self,
        marketplace_url: str,
        category: str,
        max_price: int,
        min_rating: Optional[float] = None,
    ) -> str:
        """
        Finding best deals in category

        Args:
            marketplace_url: Marketplace URL
            category: Product category
            max_price: Maximum price
            min_rating: Minimum rating

        Returns:
            Best deals with analysis
        """
        request = f"Find best deals on {marketplace_url} in category '{category}' "
        request += f"not more expensive than {max_price} rubles"

        if min_rating:
            request += f" with rating not less than {min_rating}"

        request += (
            ". Analyze reviews and give recommendations for best price/quality ratio"
        )

        return await self.run(request)

    async def analyze_product_reviews(
        self, product_url: str, max_reviews: int = None
    ) -> str:
        """
        Specific product review analysis

        Args:
            product_url: Product URL
            max_reviews: Maximum number of reviews to extract

        Returns:
            Review analysis and recommendations
        """
        if max_reviews is None:
            max_reviews = self.marketplace_config.default_max_reviews

        return await self.run(
            f"Analyze reviews for product {product_url}. "
            f"Extract up to {max_reviews} reviews. "
            f"Highlight main pros and cons, assess product reliability"
        )

    async def search_with_filters(
        self,
        marketplace_url: str,
        query: str,
        filters: dict,
        max_results: int = 10,
    ) -> str:
        """
        Search with filter application

        Args:
            marketplace_url: Marketplace URL
            query: Search query
            filters: Filter dictionary {name: value}
            max_results: Maximum number of results

        Returns:
            Search results with applied filters
        """
        filters_text = ", ".join([f"{k}: {v}" for k, v in filters.items()])

        return await self.run(
            f"Find products on {marketplace_url} by query '{query}' "
            f"with filters: {filters_text}. "
            f"Maximum {max_results} results"
        )

    async def multi_marketplace_comparison(
        self,
        query: str,
        marketplace_urls: List[str],
        max_results_per_site: int = 5,
    ) -> str:
        """
        Product comparison between multiple marketplaces

        Args:
            query: Search query
            marketplace_urls: List of marketplace URLs
            max_results_per_site: Maximum results per site

        Returns:
            Comparative analysis between marketplaces
        """
        sites_text = "\n".join([f"- {url}" for url in marketplace_urls])

        return await self.run(
            f"Find products by query '{query}' on these marketplaces:\n{sites_text}\n\n"
            f"Maximum {max_results_per_site} products from each site. "
            f"Compare prices, quality and conditions between different marketplaces"
        )

    # Convenient methods adapted from OzonAgent for better usability
    async def search_products_simple(
        self, marketplace_url: str, query: str, max_results: int = 10
    ) -> str:
        """
        Simple product search method

        Args:
            marketplace_url: Marketplace URL
            query: Search query
            max_results: Maximum number of results

        Returns:
            Search results
        """
        return await self.run(
            f"Search for '{query}' on {marketplace_url} (maximum {max_results} results)"
        )

    async def analyze_product_reviews_simple(
        self, product_url: str, max_reviews: int = None
    ) -> str:
        """
        Simple product review analysis method

        Args:
            product_url: Product URL
            max_reviews: Maximum number of reviews

        Returns:
            Review analysis
        """
        if max_reviews is None:
            max_reviews = self.marketplace_config.default_max_reviews

        return await self.run(
            f"Analyze reviews for product: {product_url} (maximum {max_reviews} reviews)"
        )

    async def get_product_details(self, product_url: str) -> str:
        """
        Get detailed product information

        Args:
            product_url: Product URL

        Returns:
            Detailed product information
        """
        return await self.run(f"Get detailed information about product: {product_url}")

    async def compare_products_by_urls_simple(self, product_urls: List[str]) -> str:
        """
        Simple product comparison by URLs

        Args:
            product_urls: List of product URLs for comparison

        Returns:
            Product comparison
        """
        products_list = "\n".join([f"- {url}" for url in product_urls])
        return await self.run(f"Compare the following products:\n{products_list}")

    async def find_best_product(
        self,
        marketplace_url: str,
        query: str,
        criteria: str = "price and reviews",
        max_price: Optional[int] = None,
    ) -> str:
        """
        Find best product by criteria

        Args:
            marketplace_url: Marketplace URL
            query: Search query
            criteria: Selection criteria
            max_price: Maximum price limit

        Returns:
            Best product recommendation
        """
        request = f"Find the best product for query '{query}' on {marketplace_url}"
        if max_price:
            request += f" with price up to {max_price}"
        request += f" considering criteria: {criteria}"

        return await self.run(request)

    async def extract_many_reviews(
        self, product_url: str, max_reviews: int = None
    ) -> str:
        """
        Extract a large number of reviews for detailed analysis

        Args:
            product_url: Product URL
            max_reviews: Maximum number of reviews to extract (up to limit)

        Returns:
            Large collection of reviews
        """
        if max_reviews is None:
            # For "many reviews" use double the default amount
            max_reviews = min(
                self.marketplace_config.default_max_reviews * 2,
                self.marketplace_config.max_reviews_limit,
            )

        return await self.run(
            f"Extract as many reviews as possible for product {product_url}. "
            f"Target: {max_reviews} reviews. Use all available methods to load more reviews "
            f"(pagination, scroll loading, etc.). Focus on quantity while maintaining quality."
        )
