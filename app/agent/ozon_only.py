from typing import List

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.tool import Terminate, ToolCollection
from app.tool.ozon_tool import OzonTool

OZON_ONLY_SYSTEM_PROMPT = """
Вы — ЭКСКЛЮЗИВНЫЙ агент для работы ТОЛЬКО с интернет-магазином Ozon.ru.

У вас есть доступ ТОЛЬКО к специализированному ozon_tool, который оптимизирован для работы с Ozon.

🎯 ВАША СПЕЦИАЛИЗАЦИЯ:
1. 🔍 Поиск товаров на OZON по любым критериям
2. 💰 Анализ цен и поиск товаров в заданном ценовом диапазоне
3. 💬 Анализ отзывов покупателей для оценки качества и надежности
4. 📊 Сравнение товаров и рекомендации лучших вариантов
5. 🏆 Комплексная оценка товаров по критериям цена/качество

✅ АЛГОРИТМ РАБОТЫ:
1. Получаете запрос пользователя
2. Используете ozon_tool для поиска товаров
3. Анализируете найденные товары
4. При необходимости получаете отзывы на товары
5. Предоставляете развернутый анализ и рекомендации
6. Закрываете браузер

🔍 ПОИСК ТОВАРОВ:
- Включайте ценовые ограничения в запрос поиска
- Формулируйте запросы четко: "товар до X рублей"
- Ищите несколько вариантов для сравнения

💬 АНАЛИЗ ОТЗЫВОВ:
- Суммируйте основные плюсы и минусы
- Обращайте внимание на надежность и долговечность
- Выделяйте повторяющиеся проблемы

📋 СТРУКТУРА ОТВЕТА:
1. Найденные товары с ценами
2. Анализ отзывов (если запрошен)
3. Ваши рекомендации
4. Итоговый вывод

Всегда завершайте работу закрытием браузера!
"""


class OzonOnlyAgent(ToolCallAgent):
    """
    Специализированный агент ТОЛЬКО для работы с Ozon.ru

    Этот агент имеет доступ только к ozon_tool, что исключает возможность
    выбора других инструментов для задач связанных с Ozon.
    """

    name: str = "ozon_only"
    description: str = (
        "Эксклюзивный агент для работы ТОЛЬКО с Ozon.ru. Имеет доступ только к специализированному ozon_tool."
    )

    system_prompt: str = OZON_ONLY_SYSTEM_PROMPT
    next_step_prompt: str = (
        "Используйте ozon_tool для выполнения следующего шага задачи пользователя."
    )

    max_observe: int = 15000
    max_steps: int = 15

    # ТОЛЬКО ozon_tool и terminate - никаких других инструментов!
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

    async def search_and_analyze(
        self, query: str, price_limit: int = None, analyze_reviews: bool = True
    ) -> str:
        """
        Поиск товаров с анализом отзывов

        Args:
            query: Поисковый запрос
            price_limit: Ценовое ограничение
            analyze_reviews: Анализировать ли отзывы

        Returns:
            Полный анализ товаров
        """
        search_query = query
        if price_limit:
            search_query += f" до {price_limit} рублей"

        request = f"Найди {search_query}"

        if analyze_reviews:
            request += " и проанализируй отзывы для оценки надежности"

        return await self.run(request)

    async def find_best_by_price_and_reviews(self, query: str, max_price: int) -> str:
        """
        Поиск лучшего товара по критериям цены и отзывов

        Args:
            query: Что ищем
            max_price: Максимальная цена

        Returns:
            Рекомендация лучшего товара
        """
        return await self.run(
            f"Найди лучший {query} не дороже {max_price} рублей. "
            f"Проанализируй отзывы и порекомендуй самый надежный вариант с хорошим соотношением цена/качество."
        )

    async def compare_products_by_urls(self, product_urls: List[str]) -> str:
        """
        Сравнение товаров по URL

        Args:
            product_urls: Список URL товаров

        Returns:
            Сравнительный анализ
        """
        urls_text = "\n".join([f"- {url}" for url in product_urls])
        return await self.run(f"Сравни товары по этим ссылкам:\n{urls_text}")

    async def analyze_product_reliability(self, product_url: str) -> str:
        """
        Анализ надежности конкретного товара

        Args:
            product_url: URL товара

        Returns:
            Анализ надежности на основе отзывов
        """
        return await self.run(
            f"Проанализируй надежность товара {product_url} на основе отзывов покупателей"
        )
