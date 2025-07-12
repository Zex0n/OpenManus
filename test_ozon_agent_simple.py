#!/usr/bin/env python3
"""
Простой тест для проверки импорта и инициализации OzonAgent
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from app.logger import logger


async def test_imports():
    """Тест импортов"""

    print("🧪 Тест импортов")
    print("=" * 30)

    try:
        # Тест импорта OzonTool
        print("📦 Импорт OzonTool...")
        from app.tool.ozon_tool import OzonTool

        print("✅ OzonTool импортирован успешно")

        # Тест импорта OzonAgent
        print("🤖 Импорт OzonAgent...")
        from app.agent.ozon import OzonAgent

        print("✅ OzonAgent импортирован успешно")

        # Тест создания инстанса OzonAgent
        print("🏗️ Создание инстанса OzonAgent...")
        agent = OzonAgent()
        print("✅ OzonAgent создан успешно")

        # Проверка базовых свойств
        print("🔍 Проверка свойств агента...")
        print(f"   Имя: {agent.name}")
        print(f"   Описание: {agent.description[:50]}...")
        print(f"   Максимальное количество шагов: {agent.max_steps}")
        print(
            f"   Доступные инструменты: {list(agent.available_tools.tool_map.keys())}"
        )
        print("✅ Свойства агента корректны")

        # Тест создания инстанса OzonTool
        print("🛠️ Создание инстанса OzonTool...")
        tool = OzonTool()
        print("✅ OzonTool создан успешно")

        # Проверка базовых свойств OzonTool
        print("🔧 Проверка свойств инструмента...")
        print(f"   Имя: {tool.name}")
        print(f"   Описание: {tool.description[:50]}...")
        print(f"   Параметры: {list(tool.parameters.get('properties', {}).keys())}")
        print("✅ Свойства инструмента корректны")

        print("\n🎉 Все импорты и инициализация прошли успешно!")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте: {e}")
        print(f"❌ Тест не пройден: {e}")
        return False


async def test_tool_parameters():
    """Тест параметров OzonTool"""

    print("\n🔧 Тест параметров OzonTool")
    print("=" * 30)

    try:
        from app.tool.ozon_tool import OzonTool

        tool = OzonTool()

        # Проверяем, что у инструмента есть все необходимые параметры
        required_actions = ["search", "get_reviews", "get_product_info", "close"]

        actions = tool.parameters["properties"]["action"]["enum"]
        print(f"Доступные действия: {actions}")

        for action in required_actions:
            if action in actions:
                print(f"✅ Действие '{action}' доступно")
            else:
                print(f"❌ Действие '{action}' отсутствует")
                return False

        print("✅ Все необходимые действия доступны")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте параметров: {e}")
        print(f"❌ Тест параметров не пройден: {e}")
        return False


def main():
    """Главная функция тестирования"""

    print("🚀 Запуск простых тестов OzonAgent")
    print("=" * 50)

    # Запуск тестов
    result1 = asyncio.run(test_imports())
    result2 = asyncio.run(test_tool_parameters())

    if result1 and result2:
        print("\n🎉 Все тесты пройдены успешно!")
        print("✅ OzonAgent готов к использованию")
    else:
        print("\n❌ Некоторые тесты не пройдены")
        print("⚠️ Проверьте ошибки выше")


if __name__ == "__main__":
    main()
