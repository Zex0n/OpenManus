import asyncio
import sys
from pathlib import Path

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent.ozon import OzonAgent
from app.logger import logger


async def demo_ozon_agent():
    """Демонстрация работы OzonAgent"""

    # Создаем агента
    agent = OzonAgent()

    try:
        print("🚀 Демонстрация работы OzonAgent")
        print("=" * 50)

        # Пример 1: Поиск товаров
        print("\n📱 Пример 1: Поиск смартфонов")
        print("-" * 30)

        result = await agent.search_products("iPhone 15", max_results=3)
        print(result)

        # Пример 2: Поиск с анализом отзывов
        print("\n💻 Пример 2: Поиск ноутбуков с анализом")
        print("-" * 30)

        result = await agent.run(
            "Найди ноутбуки ASUS до 100000 рублей и проанализируй отзывы на первый найденный товар"
        )
        print(result)

        # Пример 3: Сравнение товаров
        print("\n⚖️ Пример 3: Сравнение товаров")
        print("-" * 30)

        result = await agent.run(
            "Найди наушники Apple AirPods и Sony WH-1000XM4, сравни их по цене и отзывам"
        )
        print(result)

        # Пример 4: Поиск лучшего товара
        print("\n🏆 Пример 4: Поиск лучшего товара")
        print("-" * 30)

        result = await agent.find_best_product(
            "умные часы", "цена до 20000 рублей и хорошие отзывы"
        )
        print(result)

    except Exception as e:
        logger.error(f"Ошибка в демонстрации: {e}")
        print(f"❌ Произошла ошибка: {e}")

    finally:
        # Обязательно очищаем ресурсы
        await agent.cleanup()
        print("\n✅ Демонстрация завершена, ресурсы очищены")


async def quick_search_demo():
    """Быстрый пример поиска"""

    agent = OzonAgent()

    try:
        print("🔍 Быстрый поиск товаров")
        print("=" * 30)

        # Поиск конкретного товара
        query = input("Введите запрос для поиска: ")
        result = await agent.search_products(query, max_results=5)
        print(result)

    except Exception as e:
        logger.error(f"Ошибка в быстром поиске: {e}")
        print(f"❌ Произошла ошибка: {e}")

    finally:
        await agent.cleanup()


async def review_analysis_demo():
    """Демонстрация анализа отзывов"""

    agent = OzonAgent()

    try:
        print("💬 Анализ отзывов")
        print("=" * 30)

        # Анализ отзывов на конкретный товар
        product_url = input("Введите URL товара для анализа отзывов: ")
        result = await agent.analyze_product_reviews(product_url, max_reviews=10)
        print(result)

    except Exception as e:
        logger.error(f"Ошибка в анализе отзывов: {e}")
        print(f"❌ Произошла ошибка: {e}")

    finally:
        await agent.cleanup()


def main():
    """Главная функция с меню выбора"""

    print("🛍️ Добро пожаловать в демонстрацию OzonAgent!")
    print("=" * 50)
    print("Выберите режим работы:")
    print("1. Полная демонстрация (поиск, анализ, сравнение)")
    print("2. Быстрый поиск товаров")
    print("3. Анализ отзывов на товар")
    print("4. Выход")

    while True:
        choice = input("\nВведите номер (1-4): ").strip()

        if choice == "1":
            asyncio.run(demo_ozon_agent())
            break
        elif choice == "2":
            asyncio.run(quick_search_demo())
            break
        elif choice == "3":
            asyncio.run(review_analysis_demo())
            break
        elif choice == "4":
            print("👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор. Пожалуйста, введите число от 1 до 4.")


if __name__ == "__main__":
    main()
