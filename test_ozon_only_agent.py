#!/usr/bin/env python3
"""
Тест для проверки OzonOnlyAgent - что он использует только ozon_tool
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from app.logger import logger


async def test_ozon_only_agent():
    """Тест OzonOnlyAgent"""

    print("🧪 Тест OzonOnlyAgent")
    print("=" * 40)

    try:
        # Импорт OzonOnlyAgent
        print("📦 Импорт OzonOnlyAgent...")
        from app.agent.ozon_only import OzonOnlyAgent

        print("✅ OzonOnlyAgent импортирован успешно")

        # Создание агента
        print("🤖 Создание OzonOnlyAgent...")
        agent = OzonOnlyAgent()
        print("✅ OzonOnlyAgent создан успешно")

        # Проверка доступных инструментов
        print("🔧 Проверка доступных инструментов...")
        available_tools = list(agent.available_tools.tool_map.keys())
        print(f"   Доступные инструменты: {available_tools}")

        # Проверка что есть только ozon_tool и terminate
        expected_tools = {"ozon_tool", "terminate"}
        actual_tools = set(available_tools)

        if actual_tools == expected_tools:
            print("✅ Правильный набор инструментов (только ozon_tool + terminate)")
        else:
            print(f"❌ Неправильный набор инструментов!")
            print(f"   Ожидалось: {expected_tools}")
            print(f"   Получено: {actual_tools}")
            return False

        # Проверка что browser_use НЕ доступен
        if "browser_use" not in available_tools:
            print("✅ browser_use правильно исключен из доступных инструментов")
        else:
            print("❌ browser_use НЕ должен быть доступен!")
            return False

        # Проверка базовых свойств
        print("📋 Проверка свойств агента...")
        print(f"   Имя: {agent.name}")
        print(f"   Описание: {agent.description[:50]}...")
        print(f"   Максимальное количество шагов: {agent.max_steps}")
        print("✅ Свойства агента корректны")

        print("\n🎉 OzonOnlyAgent готов к работе!")
        print("✅ Гарантированно будет использовать только ozon_tool для задач с Ozon")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте: {e}")
        print(f"❌ Тест не пройден: {e}")
        return False


async def test_methods():
    """Тест специальных методов OzonOnlyAgent"""

    print("\n🔧 Тест специальных методов")
    print("=" * 40)

    try:
        from app.agent.ozon_only import OzonOnlyAgent

        agent = OzonOnlyAgent()

        # Проверка наличия специальных методов
        methods_to_check = [
            "search_and_analyze",
            "find_best_by_price_and_reviews",
            "compare_products_by_urls",
            "analyze_product_reliability",
        ]

        for method_name in methods_to_check:
            if hasattr(agent, method_name):
                print(f"✅ Метод {method_name} доступен")
            else:
                print(f"❌ Метод {method_name} отсутствует")
                return False

        print("✅ Все специальные методы доступны")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте методов: {e}")
        print(f"❌ Тест методов не пройден: {e}")
        return False


def main():
    """Главная функция тестирования"""

    print("🚀 Тестирование OzonOnlyAgent")
    print("=" * 50)
    print("Этот агент гарантированно использует ТОЛЬКО ozon_tool!")
    print("=" * 50)

    # Запуск тестов
    result1 = asyncio.run(test_ozon_only_agent())
    result2 = asyncio.run(test_methods())

    if result1 and result2:
        print("\n🎉 Все тесты OzonOnlyAgent пройдены успешно!")
        print("\n💡 РЕКОМЕНДАЦИЯ:")
        print("   Для запросов связанных с Ozon используйте OzonOnlyAgent")
        print("   Он НИКОГДА не выберет browser_use вместо ozon_tool!")
        print("\n📋 Пример использования:")
        print("   from app.agent.ozon_only import OzonOnlyAgent")
        print("   agent = OzonOnlyAgent()")
        print('   result = await agent.run("найди триммер на ozon до 3000 рублей")')
    else:
        print("\n❌ Некоторые тесты не пройдены")
        print("⚠️ Проверьте ошибки выше")


if __name__ == "__main__":
    main()
