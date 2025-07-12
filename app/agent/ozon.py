from datetime import datetime
from typing import List

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.tool import Terminate, ToolCollection
from app.tool.ozon_tool import OzonTool

OZON_SYSTEM_PROMPT = """
Вы — специализированный агент для работы с интернет-магазином Ozon.ru.

🚨 КРИТИЧЕСКИ ВАЖНО:
ВСЕГДА используйте ТОЛЬКО ozon_tool для ЛЮБЫХ задач связанных с Ozon.ru!
НИКОГДА не используйте browser_use или другие инструменты для работы с Ozon!

Ваши основные функции:
1. 🔍 Поиск товаров по запросу пользователя на OZON
2. 📋 Получение подробной информации о товарах с OZON
3. 💬 Анализ отзывов покупателей на OZON
4. 📊 Предоставление сводной информации о товарах с OZON
5. 🏆 Поиск лучших товаров по критериям цены и качества

ПРАВИЛА ИСПОЛЬЗОВАНИЯ ИНСТРУМЕНТОВ:
- Для ЛЮБЫХ запросов про OZON/ОЗОН/ozon.ru - используйте ТОЛЬКО ozon_tool
- ozon_tool имеет встроенный обход антибот защиты Ozon
- ozon_tool оптимизирован специально для структуры сайта Ozon

Особенности работы:
- При поиске товаров указывайте ценовые ограничения в query
- При анализе отзывов суммируйте основные плюсы и минусы
- Обязательно закрывайте браузер после завершения работы (action="close")
- Обрабатывайте ошибки и предлагайте альтернативы при неудачных попытках

Инструкции по использованию:
1. Для поиска товаров: {"action": "search", "query": "товар до XXXX рублей"}
2. Для получения отзывов: {"action": "get_reviews", "product_url": "URL товара"}
3. Для информации о товаре: {"action": "get_product_info", "product_url": "URL товара"}
4. Всегда завершайте работу: {"action": "close"}

Отвечайте на русском языке, будьте полезными и информативными.
"""

OZON_NEXT_STEP_PROMPT = """
Определите следующий шаг для выполнения задачи пользователя:

🚨 ВАЖНО: Для ЛЮБЫХ задач с OZON используйте ТОЛЬКО ozon_tool!

1. Если запрос упоминает OZON/ОЗОН/товары/покупки/отзывы - используйте ozon_tool для поиска
2. Если пользователь просит проанализировать отзывы - получите отзывы через ozon_tool
3. Если пользователь просит информацию о товаре - используйте ozon_tool
4. Если указан ценовой лимит - включите его в query поиска
5. Если задача выполнена - закройте браузер через ozon_tool (action="close")

НИКОГДА не используйте browser_use для задач с OZON!
Всегда предоставляйте пользователю полную и структурированную информацию.
"""


class OzonAgent(ToolCallAgent):
    """
    Агент для работы с интернет-магазином Ozon.ru

    Этот агент специализируется на:
    - Поиске товаров на Ozon
    - Анализе отзывов покупателей
    - Получении подробной информации о товарах
    - Сравнении товаров и цен
    """

    name: str = "ozon"
    description: str = (
        "Специализированный агент для работы с интернет-магазином Ozon.ru. Может искать товары, анализировать отзывы и предоставлять подробную информацию о товарах."
    )

    system_prompt: str = OZON_SYSTEM_PROMPT
    next_step_prompt: str = OZON_NEXT_STEP_PROMPT

    max_observe: int = 15000
    max_steps: int = 15

    # Инструменты для работы с Ozon
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            OzonTool(),
            Terminate(),
        )
    )

    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    async def cleanup(self):
        """Очистка ресурсов агента"""
        # Закрываем браузер перед завершением работы
        ozon_tool = self.available_tools.get_tool("ozon_tool")
        if ozon_tool:
            await ozon_tool.cleanup()

        # Вызываем родительский метод очистки
        await super().cleanup()

    async def search_products(self, query: str, max_results: int = 10) -> str:
        """
        Удобный метод для поиска товаров

        Args:
            query: Поисковый запрос
            max_results: Максимальное количество результатов

        Returns:
            Результаты поиска
        """
        return await self.run(
            f"Найди товары: {query} (максимум {max_results} результатов)"
        )

    async def analyze_product_reviews(
        self, product_url: str, max_reviews: int = 20
    ) -> str:
        """
        Удобный метод для анализа отзывов

        Args:
            product_url: URL товара
            max_reviews: Максимальное количество отзывов

        Returns:
            Анализ отзывов
        """
        return await self.run(
            f"Проанализируй отзывы на товар: {product_url} (максимум {max_reviews} отзывов)"
        )

    async def get_product_details(self, product_url: str) -> str:
        """
        Удобный метод для получения подробной информации о товаре

        Args:
            product_url: URL товара

        Returns:
            Подробная информация о товаре
        """
        return await self.run(f"Получи подробную информацию о товаре: {product_url}")

    async def compare_products(self, product_urls: List[str]) -> str:
        """
        Удобный метод для сравнения товаров

        Args:
            product_urls: Список URL товаров для сравнения

        Returns:
            Сравнение товаров
        """
        products_list = "\n".join([f"- {url}" for url in product_urls])
        return await self.run(f"Сравни следующие товары:\n{products_list}")

    async def find_best_product(
        self, query: str, criteria: str = "цена и отзывы"
    ) -> str:
        """
        Удобный метод для поиска лучшего товара по критериям

        Args:
            query: Поисковый запрос
            criteria: Критерии выбора

        Returns:
            Рекомендация лучшего товара
        """
        return await self.run(
            f"Найди лучший товар по запросу '{query}' с учетом критериев: {criteria}"
        )
