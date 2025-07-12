import asyncio
import sys
from pathlib import Path

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent.ozon_only import OzonOnlyAgent
from app.logger import logger


async def search_trimmer_demo():
    """Демонстрация поиска аккумуляторного триммера"""

    print("🔋 Поиск аккумуляторного триммера на Ozon")
    print("=" * 50)

    # Используем специализированный OzonOnlyAgent
    agent = OzonOnlyAgent()

    try:
        # Ваш конкретный запрос
        query = "найди аккумуляторный триммер на ozon не дороже 3000 рублей и проверь по отзывам достаточно ли он надежный"

        print(f"🎯 Выполняю запрос: {query}")
        print("-" * 50)

        result = await agent.run(query)
        print(result)

    except Exception as e:
        logger.error(f"Ошибка в демонстрации: {e}")
        print(f"❌ Произошла ошибка: {e}")

    finally:
        # Обязательно очищаем ресурсы
        await agent.cleanup()
        print("\n✅ Ресурсы очищены")


async def search_with_specific_method():
    """Поиск с использованием специального метода"""

    print("\n🎯 Поиск с использованием специального метода")
    print("=" * 50)

    agent = OzonOnlyAgent()

    try:
        # Используем специальный метод для поиска с анализом
        result = await agent.find_best_by_price_and_reviews(
            query="аккумуляторный триммер", max_price=3000
        )
        print(result)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        print(f"❌ Произошла ошибка: {e}")

    finally:
        await agent.cleanup()


def main():
    """Главная функция"""

    print("🛍️ Демонстрация поиска триммера на Ozon")
    print("=" * 60)
    print("Выберите способ поиска:")
    print("1. Обычный запрос (как вы писали)")
    print("2. Специальный метод поиска")
    print("3. Оба варианта")
    print("4. Выход")

    while True:
        choice = input("\nВведите номер (1-4): ").strip()

        if choice == "1":
            asyncio.run(search_trimmer_demo())
            break
        elif choice == "2":
            asyncio.run(search_with_specific_method())
            break
        elif choice == "3":
            asyncio.run(search_trimmer_demo())
            asyncio.run(search_with_specific_method())
            break
        elif choice == "4":
            print("👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор. Пожалуйста, введите число от 1 до 4.")


if __name__ == "__main__":
    main()
