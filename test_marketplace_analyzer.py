#!/usr/bin/env python3
"""
Test of new universal marketplace analyzer
Demonstrates working with various marketplaces through LLM analysis
"""

import asyncio
import os
import sys

# Add root directory to PATH
sys.path.insert(0, os.path.abspath("."))

from app.agent.marketplace import MarketplaceAgent
from app.logger import logger


async def test_ozon_analysis():
    """Test Ozon structure analysis"""
    print("🔍 Testing Ozon structure analysis...")

    agent = MarketplaceAgent()

    try:
        # Analyze Ozon main page structure
        result = await agent.analyze_marketplace("https://www.ozon.ru")
        print("📊 Analysis result:")
        print(result)

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await agent.cleanup()


async def test_ozon_search():
    """Test product search on Ozon"""
    print("\n🔍 Testing product search on Ozon...")

    agent = MarketplaceAgent()

    try:
        # Search for products on Ozon
        result = await agent.search_and_compare(
            marketplace_url="https://www.ozon.ru",
            query="smartphone xiaomi",
            max_results=5,
            price_limit=30000,
            analyze_reviews=False,  # Disable review analysis for now
        )
        print("📱 Search result:")
        print(result)

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await agent.cleanup()


async def test_wildberries_analysis():
    """Test Wildberries structure analysis"""
    print("\n🔍 Testing Wildberries structure analysis...")

    agent = MarketplaceAgent()

    try:
        # Analyze Wildberries structure
        result = await agent.analyze_marketplace("https://www.wildberries.ru")
        print("📊 Analysis result:")
        print(result)

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await agent.cleanup()


async def test_wildberries_search():
    """Test product search on Wildberries"""
    print("\n🔍 Testing product search on Wildberries...")

    agent = MarketplaceAgent()

    try:
        # Search for products on Wildberries
        result = await agent.search_and_compare(
            marketplace_url="https://www.wildberries.ru",
            query="nike sneakers",
            max_results=3,
            analyze_reviews=False,
        )
        print("👟 Search result:")
        print(result)

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await agent.cleanup()


async def test_multi_marketplace_comparison():
    """Test comparison between multiple marketplaces"""
    print("\n🔍 Testing comparison between marketplaces...")

    agent = MarketplaceAgent()

    try:
        # Compare products between Ozon and Wildberries
        result = await agent.multi_marketplace_comparison(
            query="apple airpods",
            marketplace_urls=["https://www.ozon.ru", "https://www.wildberries.ru"],
            max_results_per_site=3,
        )
        print("🎧 Comparison result:")
        print(result)

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await agent.cleanup()


async def test_direct_tool_usage():
    """Test direct MarketplaceAnalyzer usage"""
    print("\n🔧 Testing direct MarketplaceAnalyzer usage...")

    from app.tool.marketplace_analyzer import MarketplaceAnalyzer

    tool = MarketplaceAnalyzer()

    try:
        # Analyze structure
        result = await tool.execute(action="analyze_page", url="https://www.ozon.ru")
        print("📊 Direct structure analysis:")
        print(result.output if result.output else result.error)

        if result.output and "successfully" in result.output:
            # Try search
            search_result = await tool.execute(
                action="search_products",
                url="https://www.ozon.ru",
                query="headphones",
                max_results=3,
            )
            print("\n🎧 Direct search:")
            print(search_result.output if search_result.output else search_result.error)

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await tool.cleanup()


def print_separator(title: str):
    """Print separator with title"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


async def main():
    """Main testing function"""
    print("🚀 Running universal marketplace analyzer tests")
    print("📝 This tool uses LLM for automatic structure analysis of any marketplaces")

    # Test list
    tests = [
        ("Ozon structure analysis", test_ozon_analysis),
        ("Product search on Ozon", test_ozon_search),
        ("Wildberries structure analysis", test_wildberries_analysis),
        ("Product search on Wildberries", test_wildberries_search),
        ("Comparison between marketplaces", test_multi_marketplace_comparison),
        ("Direct tool usage", test_direct_tool_usage),
    ]

    # Execute tests
    for test_name, test_func in tests:
        print_separator(test_name)
        try:
            await test_func()
        except Exception as e:
            print(f"❌ Critical error in test '{test_name}': {e}")
            logger.error(f"Test {test_name} failed: {e}")

    print_separator("Testing completed")
    print("✅ All tests executed!")
    print("\n📋 New tool capabilities:")
    print("  • Automatic structure analysis of any marketplace")
    print("  • Using LLM to determine selectors")
    print("  • Product search without hardcoded selectors")
    print("  • Review extraction and product comparison")
    print("  • Working with filters and navigation")
    print("  • Comparison between different marketplaces")


if __name__ == "__main__":
    asyncio.run(main())
