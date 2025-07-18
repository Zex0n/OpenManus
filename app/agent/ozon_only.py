from typing import List, Optional

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.tool import Terminate, ToolCollection
from app.tool.ozon_tool import OzonTool

OZON_ONLY_SYSTEM_PROMPT = """
You are an EXCLUSIVE agent for working ONLY with the Ozon.ru online store.

You have access ONLY to the specialized ozon_tool, which is optimized for working with Ozon.

YOUR SPECIALIZATION:
1. Product search on OZON by any criteria
2. Price analysis and finding products within specified price range
3. Customer review analysis for quality and reliability assessment
4. Product comparison and recommendations for best options
5. Comprehensive product evaluation by price/quality criteria

WORKFLOW ALGORITHM:
1. Receive user request
2. Use ozon_tool to search for products
3. Analyze found products
4. Get product reviews if necessary
5. Provide detailed analysis and recommendations
6. Close browser

PRODUCT SEARCH:
- Search for products only
- Don't include price constraints in search query
- Implement price constraints only using filters
- Search for multiple options for comparison

REVIEW ANALYSIS:
- Summarize main pros and cons
- Pay attention to reliability and durability
- Highlight recurring issues

RESPONSE STRUCTURE:
1. Found products with prices
2. Review analysis (if requested)
3. Your recommendations
4. Final conclusion

Always complete work by closing the browser!
"""


class OzonOnlyAgent(ToolCallAgent):
    """
    Specialized agent ONLY for working with Ozon.ru

    This agent has access only to ozon_tool, which excludes the possibility
    of choosing other tools for Ozon-related tasks.
    """

    name: str = "ozon_only"
    description: str = (
        "Exclusive agent for working ONLY with Ozon.ru. Has access only to specialized ozon_tool."
    )

    system_prompt: str = OZON_ONLY_SYSTEM_PROMPT
    next_step_prompt: str = "Use ozon_tool to perform the next step of the user's task."

    max_observe: int = 15000
    max_steps: int = 15

    # ONLY ozon_tool and terminate - no other tools!
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            OzonTool(),
            Terminate(),
        )
    )

    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    async def cleanup(self):
        """Agent resource cleanup"""
        # Close browser before finishing work
        ozon_tool = self.available_tools.get_tool("ozon_tool")
        if ozon_tool and isinstance(ozon_tool, OzonTool):
            await ozon_tool.cleanup()

        # Call parent cleanup method
        await super().cleanup()

    async def search_and_analyze(
        self,
        query: str,
        price_limit: Optional[int] = None,
        analyze_reviews: bool = True,
    ) -> str:
        """
        Product search with review analysis

        Args:
            query: Search query
            price_limit: Price limit
            analyze_reviews: Whether to analyze reviews

        Returns:
            Complete product analysis
        """
        search_query = query
        if price_limit:
            search_query += f" up to {price_limit} rubles"

        request = f"Find {search_query}"

        if analyze_reviews:
            request += " and analyze reviews for reliability assessment"

        return await self.run(request)

    async def find_best_by_price_and_reviews(self, query: str, max_price: int) -> str:
        """
        Find best product by price and review criteria

        Args:
            query: What we're looking for
            max_price: Maximum price

        Returns:
            Best product recommendation
        """
        return await self.run(
            f"Find the best {query} not more expensive than {max_price} rubles. "
            f"Analyze reviews and recommend the most reliable option with good price/quality ratio."
        )

    async def compare_products_by_urls(self, product_urls: List[str]) -> str:
        """
        Product comparison by URLs

        Args:
            product_urls: List of product URLs

        Returns:
            Comparative analysis
        """
        urls_text = "\n".join([f"- {url}" for url in product_urls])
        return await self.run(f"Compare products by these links:\n{urls_text}")

    async def analyze_product_reliability(self, product_url: str) -> str:
        """
        Analyze specific product reliability

        Args:
            product_url: Product URL

        Returns:
            Reliability analysis based on reviews
        """
        return await self.run(
            f"Analyze the reliability of product {product_url} based on customer reviews"
        )
