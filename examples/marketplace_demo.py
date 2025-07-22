#!/usr/bin/env python3
"""
Демонстрация работы универсального MarketplaceAgent
Показывает как работать с ЛЮБЫМИ маркетплейсами через LLM-анализ
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent.marketplace import MarketplaceAgent
from app.logger import logger


async def demo_marketplace_agent():
    """Демонстрация работы универсального MarketplaceAgent"""

    # Создаем агента
    agent = MarketplaceAgent()

    try:
        print("🚀 Демонстрация работы универсального MarketplaceAgent")
        print("=" * 60)
        print("🎯 Этот агент работает с ЛЮБЫМИ маркетплейсами!")
        print("📊 Использует LLM для автоматического анализа структуры сайтов")

        # Пример 1: Поиск на OZON
        print("\n📱 Пример 1: Поиск смартфонов на OZON")
        print("-" * 40)

        result = await agent.search_products_simple(
            "https://www.ozon.ru", "iPhone 15", max_results=3
        )
        print(result)

        # Пример 2: Поиск на Wildberries
        print("\n👟 Пример 2: Поиск кроссовок на Wildberries")
        print("-" * 40)

        result = await agent.search_products_simple(
            "https://www.wildberries.ru", "Nike Air Max", max_results=3
        )
        print(result)

        # Пример 3: Сравнение между маркетплейсами
        print("\n⚖️ Пример 3: Сравнение товаров между маркетплейсами")
        print("-" * 40)

        result = await agent.multi_marketplace_comparison(
            "наушники Apple AirPods",
            ["https://www.ozon.ru", "https://www.wildberries.ru"],
            max_results_per_site=2,
        )
        print(result)

        # Пример 4: Поиск лучшего товара с критериями
        print("\n🏆 Пример 4: Поиск лучшего товара по критериям")
        print("-" * 40)

        result = await agent.find_best_product(
            "https://www.ozon.ru",
            "умные часы",
            criteria="цена до 20000 рублей и хорошие отзывы",
            max_price=20000,
        )
        print(result)

        # Пример 5: Анализ отзывов (если есть URL)
        print("\n💬 Пример 5: Анализ отзывов продукта")
        print("-" * 40)

        # Сначала найдем товар, а потом проанализируем отзывы
        search_result = await agent.search_products_simple(
            "https://www.ozon.ru", "планшет iPad", max_results=1
        )
        print("Найден товар для анализа отзывов:")
        print(search_result)

    except Exception as e:
        logger.error(f"Ошибка в демонстрации: {e}")
        print(f"❌ Произошла ошибка: {e}")

    finally:
        # Обязательно очищаем ресурсы
        await agent.cleanup()
        print("\n✅ Демонстрация завершена, ресурсы очищены")


async def interactive_search_demo():
    """Интерактивный поиск товаров"""

    agent = MarketplaceAgent()

    try:
        print("🔍 Интерактивный поиск товаров")
        print("=" * 40)
        print("🌐 Поддерживаемые маркетплейсы:")
        print("• https://www.ozon.ru")
        print("• https://www.wildberries.ru")
        print("• https://aliexpress.com (и другие)")

        # Выбор маркетплейса
        marketplace_url = input("\nВведите URL маркетплейса: ").strip()
        if not marketplace_url.startswith("http"):
            marketplace_url = f"https://{marketplace_url}"

        # Поисковый запрос
        query = input("Введите запрос для поиска: ").strip()

        # Количество результатов
        max_results = input("Количество результатов (по умолчанию 5): ").strip()
        max_results = int(max_results) if max_results.isdigit() else 5

        print(f"\n🔄 Ищем '{query}' на {marketplace_url}...")
        result = await agent.search_products_simple(marketplace_url, query, max_results)
        print(result)

    except Exception as e:
        logger.error(f"Ошибка в интерактивном поиске: {e}")
        print(f"❌ Произошла ошибка: {e}")

    finally:
        await agent.cleanup()


async def marketplace_analysis_demo():
    """Демонстрация анализа структуры маркетплейса"""

    agent = MarketplaceAgent()

    try:
        print("🔬 Анализ структуры маркетплейса")
        print("=" * 40)

        marketplace_url = input("Введите URL маркетплейса для анализа: ").strip()
        if not marketplace_url.startswith("http"):
            marketplace_url = f"https://{marketplace_url}"

        print(f"\n📊 Анализируем структуру {marketplace_url}...")
        result = await agent.analyze_marketplace(marketplace_url)
        print(result)

    except Exception as e:
        logger.error(f"Ошибка в анализе структуры: {e}")
        print(f"❌ Произошла ошибка: {e}")

    finally:
        await agent.cleanup()


def main():
    """Главная функция с меню выбора"""

    print("🛍️ Добро пожаловать в демонстрацию универсального MarketplaceAgent!")
    print("=" * 70)
    print("🎯 Этот агент может работать с ЛЮБЫМИ маркетплейсами!")
    print("🧠 Использует LLM для автоматического анализа структуры сайтов")
    print("\nВыберите режим работы:")
    print("1. Полная демонстрация (OZON, Wildberries, сравнение)")
    print("2. Интерактивный поиск товаров")
    print("3. Анализ структуры маркетплейса")
    print("4. Выход")

    while True:
        choice = input("\nВведите номер (1-4): ").strip()

        if choice == "1":
            asyncio.run(demo_marketplace_agent())
            break
        elif choice == "2":
            asyncio.run(interactive_search_demo())
            break
        elif choice == "3":
            asyncio.run(marketplace_analysis_demo())
            break
        elif choice == "4":
            print("👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор. Пожалуйста, введите число от 1 до 4.")


if __name__ == "__main__":
    main()
