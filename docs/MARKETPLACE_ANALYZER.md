# Universal Marketplace Analyzer

## Overview

The Universal Marketplace Analyzer (`MarketplaceAnalyzer`) is a revolutionary tool that uses the capabilities of LLM (Large Language Model) to automatically analyze the structure of **any** marketplace or online store without the need for prior configuration.

### Key Advantages

🎯 **Universality**: Works with any marketplaces (Ozon, Wildberries, AliExpress, Amazon, eBay and others)

🧠 **AI Analysis**: Automatically determines element selectors through LLM

🚀 **No Setup**: No manual selector creation required

🔄 **Adaptability**: Automatically adjusts to site structure changes

## Working Principle

1. **Page Loading**: Tool opens the specified marketplace page
2. **HTML Extraction**: Gets the page HTML code
3. **LLM Analysis**: Sends HTML to LLM for structure analysis
4. **Selector Determination**: LLM returns CSS selectors for all elements
5. **Caching**: Saves structure for reuse
6. **Data Extraction**: Uses determined selectors to get information

## Capabilities

### Main Actions

- `analyze_page` - Page structure analysis
- `search_products` - Product search
- `get_product_info` - Product information retrieval
- `get_reviews` - Review extraction
- `apply_filters` - Filter application
- `navigate_page` - Page navigation
- `close` - Browser closure

### Supported Elements

#### Search
- Search query input field
- Search button
- Search form

#### Products in List
- Product container
- Product title
- Product price
- Product link
- Product image
- Product rating
- Discount information

#### Filters
- Filter groups
- Filter options (checkbox, radio, input, select)
- Filter application

#### Navigation
- Pagination
- Next/previous page buttons

#### Reviews
- Reviews container
- Individual reviews
- Review text
- Review rating
- Review author
- Review date

## Usage

### Through MarketplaceAgent

```python
from app.agent.marketplace import MarketplaceAgent

agent = MarketplaceAgent()

# Structure analysis
result = await agent.analyze_marketplace("https://www.ozon.ru")

# Product search
result = await agent.search_and_compare(
    marketplace_url="https://www.ozon.ru",
    query="smartphone",
    max_results=10,
    price_limit=50000
)

# Marketplace comparison
result = await agent.multi_marketplace_comparison(
    query="headphones",
    marketplace_urls=[
        "https://www.ozon.ru",
        "https://www.wildberries.ru"
    ]
)

await agent.cleanup()
```

### Direct Tool Usage

```python
from app.tool.marketplace_analyzer import MarketplaceAnalyzer

tool = MarketplaceAnalyzer()

# Structure analysis
result = await tool.execute(
    action="analyze_page",
    url="https://www.ozon.ru"
)

# Product search
result = await tool.execute(
    action="search_products",
    url="https://www.ozon.ru",
    query="laptop",
    max_results=5
)

# Product information retrieval
result = await tool.execute(
    action="get_product_info",
    product_url="https://www.ozon.ru/product/..."
)

await tool.cleanup()
```

### Through Manus Agent

```python
from app.agent.manus import Manus

manus = await Manus.create()

# Any marketplace analysis
result = await manus.run(
    "Analyze the structure of https://www.wildberries.ru "
    "and find 5 most popular products in electronics category"
)

await manus.cleanup()
```

## Data Structures

### MarketplaceStructure

Main structure describing the marketplace:

```python
class MarketplaceStructure(BaseModel):
    marketplace_name: str  # Marketplace name
    base_url: str         # Base URL
    search: SearchStructure
    product: ProductStructure
    product_page: ProductPageStructure
    filters: List[FilterGroup]
    navigation: Optional[NavigationStructure]
    reviews: Optional[ReviewStructure]
    special_notes: Optional[str]
```

### Analysis Result

```python
class AnalysisResult(BaseModel):
    success: bool
    marketplace_structure: Optional[MarketplaceStructure]
    error_message: Optional[str]
    confidence: float  # Confidence level (0.0-1.0)
    page_type: str    # search, product, category, main
```

### Extracted Product

```python
class ExtractedProduct(BaseModel):
    title: str
    price: Optional[str]
    link: Optional[str]
    image: Optional[str]
    rating: Optional[str]
    discount: Optional[str]
    additional_info: Dict[str, str]
```

## Usage Examples

### New Marketplace Analysis

```python
# Automatic analysis of any marketplace
agent = MarketplaceAgent()

# Works with any site!
result = await agent.analyze_marketplace("https://new-marketplace.com")
print(result)  # Will show found selectors and structure

await agent.cleanup()
```

### Search with Filters

```python
agent = MarketplaceAgent()

result = await agent.search_with_filters(
    marketplace_url="https://www.ozon.ru",
    query="phone",
    filters={
        "Brand": "Apple",
        "Price": "up to 100000",
        "Memory": "128GB"
    }
)

await agent.cleanup()
```

### Product Comparison by URL

```python
agent = MarketplaceAgent()

result = await agent.compare_products_by_urls([
    "https://www.ozon.ru/product/iphone-15-...",
    "https://www.wildberries.ru/catalog/.../detail.aspx",
    "https://market.yandex.ru/product/..."
])

await agent.cleanup()
```

## Testing

Run the test script to check functionality:

```bash
python test_marketplace_analyzer.py
```

Tests include:
- Ozon structure analysis
- Product search on Ozon
- Wildberries structure analysis
- Product search on Wildberries
- Marketplace comparison
- Direct tool usage

## Technical Details

### Requirements

- Python 3.8+
- Playwright
- OpenAI/Anthropic API for LLM
- Pydantic for data validation

### Architecture

1. **MarketplaceAnalyzer** - main tool
2. **MarketplaceAgent** - high-level agent
3. **Data schemas** - structured data models
4. **LLM analyzer** - intelligent HTML analysis

### Performance

- Structure analysis: ~10-30 seconds (with caching for subsequent requests)
- Product search: ~5-15 seconds
- Review extraction: ~10-20 seconds

### Limitations

- Dependency on LLM quality
- Analysis time depends on LLM API speed
- Requires stable internet connection
- Some sites may have automation protection

## Comparison with OzonTool

| Feature | OzonTool | MarketplaceAnalyzer |
|---------|----------|-------------------|
| Supported sites | Ozon only | Any marketplaces |
| Selector setup | Hardcoded | Automatic via LLM |
| Adaptability | Low | High |
| Setup time | Hours of development | Automatic |
| Maintenance | Manual updates | Self-adaptation |
| Accuracy | High for Ozon | Depends on LLM |

## Future Improvements

- [ ] Database caching of analysis results
- [ ] Training specialized model for e-commerce analysis
- [ ] API support for some marketplaces
- [ ] Automatic detection of structure changes
- [ ] Analysis quality metrics
- [ ] Mobile site version support

## Conclusion

The Universal Marketplace Analyzer represents a significant step forward in automating work with e-commerce sites. Through the use of LLM, the tool can work with any marketplaces without manual configuration, making it an ideal solution for universal product and price analysis tasks.
