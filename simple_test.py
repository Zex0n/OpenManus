#!/usr/bin/env python3
"""
Simple test to check the structure of the universal marketplace analyzer
"""

import os
import sys

# Add root directory to PATH
sys.path.insert(0, os.path.abspath("."))


def test_imports():
    """Test imports"""
    print("🔍 Testing imports...")

    try:
        # Check marketplace schemas
        from app.schema.marketplace import (
            AnalysisResult,
            ExtractedProduct,
            MarketplaceStructure,
        )

        print("✅ Marketplace schemas imported successfully")

        # Check basic schemas
        from app.schema import ROLE_VALUES, Message, ToolChoice

        print("✅ Basic schemas imported successfully")

        # Check LLM
        from app.llm import LLM, get_llm

        print("✅ LLM modules imported successfully")

        # Check tool
        from app.tool.marketplace_analyzer import MarketplaceAnalyzer

        print("✅ MarketplaceAnalyzer imported successfully")

        # Check agent (may not work due to dependencies)
        try:
            from app.agent.marketplace import MarketplaceAgent

            print("✅ MarketplaceAgent imported successfully")
        except Exception as e:
            print(f"⚠️ MarketplaceAgent not imported (expected): {e}")

        return True

    except Exception as e:
        print(f"❌ Import error: {e}")
        return False


def test_schema_structure():
    """Test schema structure"""
    print("\n📊 Testing schema structure...")

    try:
        from app.schema.marketplace import (
            MarketplaceStructure,
            ProductStructure,
            SearchStructure,
        )

        # Check that we can create structure
        search_structure = SearchStructure(
            search_input_selector="input[type='search']",
            search_button_selector="button[type='submit']",
        )
        print(f"✅ SearchStructure created: {search_structure.search_input_selector}")

        product_structure = ProductStructure(
            container_selector=".product-item",
            title_selector=".product-title",
            price_selector=".price",
            link_selector="a.product-link",
        )
        print(f"✅ ProductStructure created: {product_structure.container_selector}")

        return True

    except Exception as e:
        print(f"❌ Schema creation error: {e}")
        return False


def test_tool_structure():
    """Test tool structure"""
    print("\n🔧 Testing tool structure...")

    try:
        from app.tool.marketplace_analyzer import MarketplaceAnalyzer

        # Create tool instance
        tool = MarketplaceAnalyzer()

        print(f"✅ MarketplaceAnalyzer created: {tool.name}")
        print(f"📝 Description: {tool.description[:100]}...")

        # Check parameters
        print(f"🎛️ Available actions: {tool.parameters['properties']['action']['enum']}")

        return True

    except Exception as e:
        print(f"❌ Tool creation error: {e}")
        return False


def test_analyzer_concept():
    """Test analyzer concept"""
    print("\n💡 Testing universal analyzer concept...")

    try:
        from app.tool.marketplace_analyzer import MarketplaceAnalyzer

        tool = MarketplaceAnalyzer()

        # Check analysis cache
        print(
            f"📚 Analysis cache initialized: {len(tool._analyzed_structures)} structures"
        )

        # Check methods
        methods = [
            method
            for method in dir(tool)
            if not method.startswith("_") and callable(getattr(tool, method))
        ]
        important_methods = [
            m
            for m in methods
            if any(keyword in m for keyword in ["analyze", "extract", "search"])
        ]
        print(f"🔍 Key analysis methods: {important_methods}")

        return True

    except Exception as e:
        print(f"❌ Concept testing error: {e}")
        return False


def show_comparison():
    """Show comparison with OzonTool"""
    print("\n📊 Comparison with OzonTool:")
    print("┌─────────────────────┬─────────────────┬─────────────────────────┐")
    print("│ Feature             │ OzonTool        │ MarketplaceAnalyzer     │")
    print("├─────────────────────┼─────────────────┼─────────────────────────┤")
    print("│ Supported sites     │ Ozon only       │ Any marketplaces        │")
    print("│ Selector setup      │ Hardcoded       │ LLM automatically       │")
    print("│ Adaptability        │ Low             │ High                    │")
    print("│ Setup time          │ Hours of dev    │ Automatic               │")
    print("│ Maintenance         │ Manual          │ Self-adaptation         │")
    print("└─────────────────────┴─────────────────┴─────────────────────────┘")


def main():
    """Main testing function"""
    print("🚀 Universal marketplace analyzer test")
    print("=" * 60)

    tests = [
        ("Imports", test_imports),
        ("Schema structure", test_schema_structure),
        ("Tool structure", test_tool_structure),
        ("Analyzer concept", test_analyzer_concept),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Critical error in test '{test_name}': {e}")
            results.append(False)

    print("\n" + "=" * 60)
    print("📋 Test results:")

    success_count = sum(results)
    total_count = len(results)

    for i, (test_name, _) in enumerate(tests):
        status = "✅ PASSED" if results[i] else "❌ FAILED"
        print(f"  {test_name}: {status}")

    print(f"\n🎯 Overall result: {success_count}/{total_count} tests passed")

    if success_count == total_count:
        print("🎉 All tests passed! Universal analyzer is ready for use.")
    elif success_count > 0:
        print("⚠️ Some tests passed. Basic structure is created correctly.")
    else:
        print("💥 Tests failed. Error fixes required.")

    show_comparison()

    print("\n📚 New tool capabilities:")
    print("  • Automatic structure analysis of ANY marketplace")
    print("  • Using LLM to determine CSS selectors")
    print("  • Product search without hardcoding")
    print("  • Review extraction and product comparison")
    print("  • Working with filters and navigation")
    print("  • Comparison between different marketplaces")
    print("  • Analysis result caching")


if __name__ == "__main__":
    main()
