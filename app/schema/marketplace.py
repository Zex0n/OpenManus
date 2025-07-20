from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class FilterOption(BaseModel):
    """Filter option"""

    name: str = Field(description="Filter option name")
    selector: str = Field(description="CSS selector for filter element")
    value: Optional[str] = Field(default=None, description="Filter value")
    filter_type: str = Field(description="Filter type: checkbox, radio, input, select")


class FilterGroup(BaseModel):
    """Filter group"""

    name: str = Field(description="Filter group name")
    container_selector: str = Field(description="CSS selector for group container")
    options: List[FilterOption] = Field(description="List of options in group")


class ProductStructure(BaseModel):
    """Product structure on search page"""

    container_selector: Optional[str] = Field(
        default=None, description="CSS selector for product container"
    )
    title_selector: Optional[str] = Field(
        default=None, description="CSS selector for product title"
    )
    price_selector: Optional[str] = Field(
        default=None, description="CSS selector for product price"
    )
    link_selector: Optional[str] = Field(
        default=None, description="CSS selector for product link"
    )
    image_selector: Optional[str] = Field(
        default=None, description="CSS selector for product image"
    )
    rating_selector: Optional[str] = Field(
        default=None, description="CSS selector for rating"
    )
    discount_selector: Optional[str] = Field(
        default=None, description="CSS selector for discount"
    )


class SearchStructure(BaseModel):
    """Search structure"""

    search_input_selector: str = Field(description="CSS selector for search field")
    search_button_selector: Optional[str] = Field(
        default=None, description="CSS selector for search button"
    )
    search_form_selector: Optional[str] = Field(
        default=None, description="CSS selector for search form"
    )


class NavigationStructure(BaseModel):
    """Navigation structure"""

    pagination_selector: Optional[str] = Field(
        default=None, description="CSS selector for pagination"
    )
    next_page_selector: Optional[str] = Field(
        default=None, description="CSS selector for next page button"
    )
    prev_page_selector: Optional[str] = Field(
        default=None, description="CSS selector for previous page button"
    )


class ReviewStructure(BaseModel):
    """Review structure"""

    reviews_container_selector: Optional[str] = Field(
        default=None, description="CSS selector for reviews container"
    )
    review_item_selector: Optional[str] = Field(
        default=None, description="CSS selector for individual review"
    )
    review_text_selector: Optional[str] = Field(
        default=None, description="CSS selector for review text"
    )
    review_rating_selector: Optional[str] = Field(
        default=None, description="CSS selector for review rating"
    )
    review_author_selector: Optional[str] = Field(
        default=None, description="CSS selector for review author"
    )
    review_date_selector: Optional[str] = Field(
        default=None, description="CSS selector for review date"
    )
    reviews_link_selector: Optional[str] = Field(
        default=None, description="CSS selector for all reviews link"
    )


class ProductPageStructure(BaseModel):
    """Product page structure"""

    title_selector: Optional[str] = Field(
        default=None, description="CSS selector for product title"
    )
    price_selector: Optional[str] = Field(
        default=None, description="CSS selector for price"
    )
    description_selector: Optional[str] = Field(
        default=None, description="CSS selector for description"
    )
    specifications_selector: Optional[str] = Field(
        default=None, description="CSS selector for specifications"
    )
    images_selector: Optional[str] = Field(
        default=None, description="CSS selector for images"
    )
    availability_selector: Optional[str] = Field(
        default=None, description="CSS selector for availability"
    )
    buy_button_selector: Optional[str] = Field(
        default=None, description="CSS selector for buy button"
    )


class MarketplaceStructure(BaseModel):
    """Complete marketplace structure"""

    marketplace_name: str = Field(description="Marketplace name")
    base_url: str = Field(description="Marketplace base URL")
    search: SearchStructure = Field(description="Search structure")
    product: ProductStructure = Field(description="Product structure in list")
    product_page: ProductPageStructure = Field(description="Product page structure")
    filters: List[FilterGroup] = Field(
        default_factory=list, description="List of filter groups"
    )
    navigation: Optional[NavigationStructure] = Field(
        default=None, description="Navigation structure"
    )
    reviews: Optional[ReviewStructure] = Field(
        default=None, description="Reviews structure"
    )
    special_notes: Optional[str] = Field(
        default=None, description="Special notes about working with the site"
    )


class AnalysisResult(BaseModel):
    """Page analysis result"""

    success: bool = Field(description="Analysis success")
    marketplace_structure: Optional[MarketplaceStructure] = Field(
        default=None, description="Marketplace structure"
    )
    error_message: Optional[str] = Field(default=None, description="Error message")
    confidence: float = Field(description="Confidence level in analysis (0.0-1.0)")
    page_type: str = Field(description="Page type: search, product, category, main")


class ExtractedProduct(BaseModel):
    """Extracted product"""

    title: str = Field(description="Product title")
    price: Optional[str] = Field(default=None, description="Product price")
    link: Optional[str] = Field(default=None, description="Product link")
    image: Optional[str] = Field(default=None, description="Product image")
    rating: Optional[str] = Field(default=None, description="Product rating")
    discount: Optional[str] = Field(default=None, description="Discount")
    additional_info: Dict[str, str] = Field(
        default_factory=dict, description="Additional information"
    )


class ExtractedReview(BaseModel):
    """Extracted review"""

    text: str = Field(description="Review text")
    rating: Optional[str] = Field(default=None, description="Review rating")
    author: Optional[str] = Field(default=None, description="Review author")
    date: Optional[str] = Field(default=None, description="Review date")
    additional_info: Dict[str, str] = Field(
        default_factory=dict, description="Additional information"
    )
