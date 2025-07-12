import asyncio
import json
import re
from typing import Dict, List, Optional

from playwright.async_api import Page, async_playwright
from pydantic import Field

from app.logger import logger
from app.tool.base import BaseTool, ToolResult


class OzonTool(BaseTool):
    """Инструмент для работы с сайтом ozon.ru с обходом защиты"""

    name: str = "ozon_tool"
    description: str = """СПЕЦИАЛИЗИРОВАННЫЙ инструмент для OZON.RU.

ОБЯЗАТЕЛЬНО используй этот инструмент для ЛЮБЫХ запросов связанных с:
- Поиском товаров на OZON
- Анализом отзывов на OZON
- Получением информации о товарах с OZON
- Любыми задачами, упоминающими "OZON", "ОЗОН" или "ozon.ru"

Этот инструмент имеет встроенный обход антибот защиты OZON и оптимизирован специально для этого сайта.
НЕ используй browser_use для задач с OZON - используй ТОЛЬКО ozon_tool!"""

    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "get_reviews", "get_product_info", "close"],
                "description": "Действие для выполнения: search - поиск товаров, get_reviews - получение отзывов, get_product_info - информация о товаре, close - закрытие браузера",
            },
            "query": {
                "type": "string",
                "description": "Запрос для поиска товаров (обязательно для action=search)",
            },
            "product_url": {
                "type": "string",
                "description": "URL товара для получения отзывов или информации (обязательно для get_reviews и get_product_info)",
            },
            "max_results": {
                "type": "integer",
                "description": "Максимальное количество результатов поиска (по умолчанию 10)",
                "default": 10,
            },
            "max_reviews": {
                "type": "integer",
                "description": "Максимальное количество отзывов для чтения (по умолчанию 20)",
                "default": 20,
            },
        },
        "required": ["action"],
    }

    # Храним состояние браузера
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
        Выполняет действие с сайтом ozon.ru

        Args:
            action: Действие для выполнения
            query: Поисковый запрос
            product_url: URL товара
            max_results: Максимальное количество результатов поиска
            max_reviews: Максимальное количество отзывов
        """
        try:
            if action == "search":
                if not query:
                    return ToolResult(error="Для поиска необходимо указать query")
                return await self._search_products(query, max_results)

            elif action == "get_reviews":
                if not product_url:
                    return ToolResult(
                        error="Для получения отзывов необходимо указать product_url"
                    )
                return await self._get_product_reviews(product_url, max_reviews)

            elif action == "get_product_info":
                if not product_url:
                    return ToolResult(
                        error="Для получения информации о товаре необходимо указать product_url"
                    )
                return await self._get_product_info(product_url)

            elif action == "close":
                return await self._close_browser()

            else:
                return ToolResult(error=f"Неизвестное действие: {action}")

        except Exception as e:
            logger.error(f"Ошибка в OzonTool: {e}")
            return ToolResult(error=f"Ошибка выполнения: {str(e)}")

    async def _ensure_browser_ready(self) -> Page:
        """Гарантирует, что браузер готов к работе"""
        if self._page is None:
            await self._init_browser()
        return self._page

    async def _init_browser(self):
        """Инициализирует браузер с настройками для обхода антибота"""
        logger.info("Инициализация браузера для работы с ozon.ru...")

        self._playwright = await async_playwright().start()

        # Настройки браузера для обхода антибота
        self._browser = await self._playwright.chromium.launch(
            headless=False,  # Для отладки, можно поставить True
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
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            permissions=["geolocation"],
            java_script_enabled=True,
            bypass_csp=True,
        )

        # Скрипт для обхода детекции автоматизации
        await self._context.add_init_script(
            """
            delete navigator.__proto__.webdriver;
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
            window.chrome = {runtime: {}};
        """
        )

        self._page = await self._context.new_page()

        # Переходим на главную страницу Ozon
        await self._navigate_to_ozon()

    async def _navigate_to_ozon(self):
        """Переходит на главную страницу Ozon и обходит антибот"""
        logger.info("Переход на ozon.ru...")

        try:
            await self._page.goto(
                "https://www.ozon.ru/", wait_until="networkidle", timeout=120000
            )

            # Эмуляция человеческого поведения
            await self._page.mouse.move(100, 100)
            await asyncio.sleep(0.5)
            await self._page.mouse.move(200, 150)
            await asyncio.sleep(0.3)

            # Проверка капчи/антибота
            if await self._page.query_selector(".message .loader"):
                logger.info("Обнаружен антибот, ждем...")
                await self._page.wait_for_selector(
                    ".message .loader", state="hidden", timeout=60000
                )
                logger.info("Антибот пройден")

            await self._page.wait_for_load_state("networkidle", timeout=60000)
            logger.info("Страница загружена успешно")

        except Exception as e:
            logger.error(f"Ошибка при переходе на ozon.ru: {e}")
            raise

    async def _search_products(self, query: str, max_results: int) -> ToolResult:
        """Выполняет поиск товаров на Ozon"""
        logger.info(f"Поиск товаров: {query}")

        page = await self._ensure_browser_ready()

        try:
            # Ищем поле поиска (несколько вариантов селекторов)
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
                        logger.info(f"Найдено поле поиска с селектором: {selector}")
                        break
                except:
                    continue

            if not search_input:
                return ToolResult(error="Не найдено поле поиска")

            # Очищаем поле и вводим запрос
            await search_input.click()  # Кликаем для фокуса
            await search_input.fill("")  # Очищаем поле
            await asyncio.sleep(0.5)  # Небольшая пауза
            await search_input.type(
                query, delay=100
            )  # Задержка для имитации человеческого ввода

            # Нажимаем Enter или кнопку поиска
            await search_input.press("Enter")

            # Ждем загрузки результатов
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(2)  # Дополнительная пауза

            # Извлекаем результаты поиска
            products = await self._extract_search_results(page, max_results)

            return ToolResult(
                output=f"Найдено товаров: {len(products)}\n\n"
                + "\n".join([f"{i+1}. {product}" for i, product in enumerate(products)])
            )

        except Exception as e:
            logger.error(f"Ошибка при поиске товаров: {e}")
            return ToolResult(error=f"Ошибка поиска: {str(e)}")

    async def _extract_search_results(self, page: Page, max_results: int) -> List[str]:
        """Извлекает результаты поиска со страницы"""
        products = []

        try:
            # Ждем появления товаров (несколько вариантов селекторов)
            search_result_selectors = [
                "[data-widget*='searchResultsV2']",
                "[data-widget*='searchResults']",
                ".widget-search-result-container",
                ".search-result",
                "[data-widget='searchResultsV2']",
                ".tile-root",
            ]

            search_results_container = None
            for selector in search_result_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=3000)
                    search_results_container = selector
                    logger.info(f"Найдены результаты поиска с селектором: {selector}")
                    break
                except:
                    continue

            if not search_results_container:
                logger.warning("Не найден контейнер с результатами поиска")
                # Попробуем найти товары по более общим селекторам
                product_selectors = [
                    "a[href*='/product/']",
                    "a[href*='product']",
                    ".tile-root a",
                    "[data-widget] a",
                ]
            else:
                # Извлекаем информацию о товарах из найденного контейнера
                product_selectors = [f"{search_results_container} a"]

            product_elements = []
            for selector in product_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        product_elements = elements
                        logger.info(
                            f"Найдено {len(elements)} товаров с селектором: {selector}"
                        )
                        break
                except:
                    continue

            for element in product_elements[:max_results]:
                try:
                    # Получаем название товара (несколько вариантов селекторов)
                    title_selectors = [
                        "span[data-widget='searchResultTitle']",
                        ".tile-hover-target span",
                        "span",
                        ".tsHeadline500Medium",
                        "[data-widget] span",
                    ]

                    title = "Название не найдено"
                    for selector in title_selectors:
                        try:
                            title_element = await element.query_selector(selector)
                            if title_element:
                                title_text = await title_element.inner_text()
                                if title_text and title_text.strip():
                                    title = title_text.strip()
                                    break
                        except:
                            continue

                    # Получаем ссылку
                    href = await element.get_attribute("href")
                    full_url = (
                        f"https://www.ozon.ru{href}"
                        if href and href.startswith("/")
                        else href or "Ссылка не найдена"
                    )

                    # Получаем цену (несколько вариантов селекторов)
                    price_selectors = [
                        "span[style*='color']",
                        ".tsHeadline500Medium span",
                        "[data-widget='webPrice'] span",
                        ".price span",
                        "span",
                    ]

                    price = "Цена не найдена"
                    for selector in price_selectors:
                        try:
                            price_element = await element.query_selector(selector)
                            if price_element:
                                price_text = await price_element.inner_text()
                                # Проверяем, что это похоже на цену (содержит цифры и символ рубля или "₽")
                                if (
                                    price_text
                                    and any(char.isdigit() for char in price_text)
                                    and ("₽" in price_text or "руб" in price_text)
                                ):
                                    price = price_text.strip()
                                    break
                        except:
                            continue

                    product_info = f"📦 {title}\n💰 {price}\n🔗 {full_url}"
                    products.append(product_info)

                except Exception as e:
                    logger.warning(f"Ошибка при извлечении информации о товаре: {e}")
                    continue

        except Exception as e:
            logger.error(f"Ошибка при извлечении результатов поиска: {e}")

        return products

    async def _get_product_reviews(
        self, product_url: str, max_reviews: int
    ) -> ToolResult:
        """Получает отзывы на товар"""
        logger.info(f"Получение отзывов для товара: {product_url}")

        page = await self._ensure_browser_ready()

        try:
            # Переходим на страницу товара
            await page.goto(product_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Ищем кнопку "Отзывы" или секцию с отзывами
            reviews_section = await page.query_selector(
                "div[data-widget*='webReviewPager']"
            )
            if not reviews_section:
                # Пытаемся найти альтернативные селекторы
                reviews_section = await page.query_selector(
                    "div[data-widget*='reviews']"
                )

            if not reviews_section:
                return ToolResult(error="Не найдена секция с отзывами")

            # Прокручиваем к отзывам
            await reviews_section.scroll_into_view_if_needed()
            await asyncio.sleep(1)

            # Извлекаем отзывы
            reviews = await self._extract_reviews(page, max_reviews)

            return ToolResult(
                output=f"Найдено отзывов: {len(reviews)}\n\n" + "\n---\n".join(reviews)
            )

        except Exception as e:
            logger.error(f"Ошибка при получении отзывов: {e}")
            return ToolResult(error=f"Ошибка получения отзывов: {str(e)}")

    async def _extract_reviews(self, page: Page, max_reviews: int) -> List[str]:
        """Извлекает отзывы со страницы"""
        reviews = []

        try:
            # Ждем загрузки отзывов
            await page.wait_for_selector(
                "div[data-widget*='webReviewPager']", timeout=10000
            )

            # Извлекаем отзывы
            review_elements = await page.query_selector_all(
                "div[data-widget*='webReviewPager'] div"
            )

            for element in review_elements[:max_reviews]:
                try:
                    # Получаем рейтинг
                    rating_element = await element.query_selector(
                        "div[data-widget*='webReviewProductRating']"
                    )
                    rating = "⭐" * 5 if rating_element else "Рейтинг не найден"

                    # Получаем текст отзыва
                    review_text_element = await element.query_selector(
                        "div[data-widget*='webReviewText']"
                    )
                    review_text = (
                        await review_text_element.inner_text()
                        if review_text_element
                        else "Текст отзыва не найден"
                    )

                    # Получаем автора
                    author_element = await element.query_selector(
                        "span[data-widget*='webReviewAuthor']"
                    )
                    author = (
                        await author_element.inner_text()
                        if author_element
                        else "Автор не указан"
                    )

                    review_info = f"👤 {author}\n{rating}\n💬 {review_text}"
                    reviews.append(review_info)

                except Exception as e:
                    logger.warning(f"Ошибка при извлечении отзыва: {e}")
                    continue

        except Exception as e:
            logger.error(f"Ошибка при извлечении отзывов: {e}")

        return reviews

    async def _get_product_info(self, product_url: str) -> ToolResult:
        """Получает подробную информацию о товаре"""
        logger.info(f"Получение информации о товаре: {product_url}")

        page = await self._ensure_browser_ready()

        try:
            # Переходим на страницу товара
            await page.goto(product_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Извлекаем название товара
            title_element = await page.query_selector("h1")
            title = (
                await title_element.inner_text()
                if title_element
                else "Название не найдено"
            )

            # Извлекаем цену
            price_element = await page.query_selector("span[data-widget*='webPrice']")
            price = (
                await price_element.inner_text() if price_element else "Цена не найдена"
            )

            # Извлекаем рейтинг
            rating_element = await page.query_selector("div[data-widget*='webRating']")
            rating = (
                await rating_element.inner_text()
                if rating_element
                else "Рейтинг не найден"
            )

            # Извлекаем описание
            description_element = await page.query_selector(
                "div[data-widget*='webDescription']"
            )
            description = (
                await description_element.inner_text()
                if description_element
                else "Описание не найдено"
            )

            # Извлекаем характеристики
            characteristics = await self._extract_characteristics(page)

            product_info = f"""
📦 ТОВАР: {title}
💰 ЦЕНА: {price}
⭐ РЕЙТИНГ: {rating}
📝 ОПИСАНИЕ: {description[:500]}{'...' if len(description) > 500 else ''}
📋 ХАРАКТЕРИСТИКИ:
{characteristics}
"""

            return ToolResult(output=product_info)

        except Exception as e:
            logger.error(f"Ошибка при получении информации о товаре: {e}")
            return ToolResult(error=f"Ошибка получения информации: {str(e)}")

    async def _extract_characteristics(self, page: Page) -> str:
        """Извлекает характеристики товара"""
        try:
            # Ждем загрузки характеристик
            await page.wait_for_selector(
                "div[data-widget*='webCharacteristics']", timeout=5000
            )

            characteristics = []
            char_elements = await page.query_selector_all(
                "div[data-widget*='webCharacteristics'] div"
            )

            for element in char_elements[:10]:  # Берем первые 10 характеристик
                try:
                    text = await element.inner_text()
                    if text and ":" in text:
                        characteristics.append(f"• {text}")
                except:
                    continue

            return (
                "\n".join(characteristics)
                if characteristics
                else "Характеристики не найдены"
            )

        except Exception as e:
            logger.warning(f"Ошибка при извлечении характеристик: {e}")
            return "Характеристики не найдены"

    async def _close_browser(self) -> ToolResult:
        """Закрывает браузер"""
        logger.info("Закрытие браузера...")

        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
                self._context = None
                self._page = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

            return ToolResult(output="Браузер успешно закрыт")

        except Exception as e:
            logger.error(f"Ошибка при закрытии браузера: {e}")
            return ToolResult(error=f"Ошибка закрытия браузера: {str(e)}")

    async def cleanup(self):
        """Очистка ресурсов"""
        if self._browser or self._playwright:
            await self._close_browser()
