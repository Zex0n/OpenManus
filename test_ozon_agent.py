#!/usr/bin/env python3
"""
Простой тест для проверки работы OzonAgent
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from app.agent.ozon import OzonAgent
from app.logger import logger


async def test_ozon_agent():
    """Тест основных функций OzonAgent"""

    print("🧪 Тестирование OzonAgent")
    print("=" * 40)

    agent = OzonAgent()

    try:
        # Тест 1: Поиск товаров
        print("\n🔍 Тест 1: Поиск товаров")
        print("-" * 30)

        result = await agent.search_products("iPhone", max_results=2)
        print("✅ Результат поиска:")
        print(result[:500] + "..." if len(result) > 500 else result)

        # Тест 2: Проверка инициализации
        print("\n🔧 Тест 2: Проверка инициализации агента")
        print("-" * 30)

        print(f"✅ Имя агента: {agent.name}")
        print(f"✅ Описание: {agent.description}")
        print(f"✅ Максимальное количество шагов: {agent.max_steps}")
        print(
            f"✅ Доступные инструменты: {list(agent.available_tools.tool_map.keys())}"
        )

        # Тест 3: Простой запрос
        print("\n💬 Тест 3: Простой запрос")
        print("-" * 30)

        result = await agent.run("Найди один товар 'Samsung Galaxy' и покажи его цену")
        print("✅ Результат запроса:")
        print(result[:500] + "..." if len(result) > 500 else result)

        print("\n🎉 Все тесты пройдены успешно!")

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте: {e}")
        print(f"❌ Тест не пройден: {e}")

    finally:
        # Обязательно очищаем ресурсы
        await agent.cleanup()
        print("\n🧹 Ресурсы очищены")


async def test_ozon_tool_directly():
    """Тест OzonTool напрямую"""

    print("\n🛠️ Тест OzonTool напрямую")
    print("=" * 40)

    from app.tool.ozon_tool import OzonTool

    tool = OzonTool()

    try:
        # Тест поиска
        print("\n🔍 Тест поиска через OzonTool")
        print("-" * 30)

        result = await tool.execute(action="search", query="iPhone", max_results=1)
        print("✅ Результат поиска:")
        print(result)

        # Закрытие браузера
        print("\n🔒 Закрытие браузера")
        print("-" * 30)

        close_result = await tool.execute(action="close")
        print("✅ Результат закрытия:")
        print(close_result)

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте OzonTool: {e}")
        print(f"❌ Тест OzonTool не пройден: {e}")

    finally:
        # Очищаем ресурсы
        await tool.cleanup()


def main():
    """Главная функция тестирования"""

    print("🚀 Запуск тестов OzonAgent")
    print("=" * 50)

    # Выбор теста
    print("Выберите тест:")
    print("1. Тест OzonAgent (рекомендуется)")
    print("2. Тест OzonTool напрямую")
    print("3. Оба теста")

    while True:
        choice = input("\nВведите номер теста (1-3): ").strip()

        if choice == "1":
            asyncio.run(test_ozon_agent())
            break
        elif choice == "2":
            asyncio.run(test_ozon_tool_directly())
            break
        elif choice == "3":
            asyncio.run(test_ozon_agent())
            asyncio.run(test_ozon_tool_directly())
            break
        else:
            print("❌ Неверный выбор. Пожалуйста, введите число от 1 до 3.")


if __name__ == "__main__":
    main()
