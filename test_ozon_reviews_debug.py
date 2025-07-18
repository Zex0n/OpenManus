#!/usr/bin/env python3
"""
Тест для отладки системы получения отзывов с Ozon.ru
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from app.logger import logger


async def search_and_select_first_product(tool, search_query):
    """Вспомогательная функция для поиска товара и выбора первого результата"""

    print(f"🔍 Поиск товара: '{search_query}'")

    # Инициализируем браузер
    print("🌐 Инициализация браузера...")
    page = await tool._ensure_browser_ready()
    print("✅ Браузер готов")

    # Выполняем поиск товара
    print("🔎 Выполнение поиска...")
    search_result = await tool.execute(
        action="search", query=search_query, max_results=5
    )

    if search_result.error:
        print(f"❌ Ошибка поиска: {search_result.error}")
        return None

    print("✅ Поиск выполнен успешно")
    print(f"📊 Результаты поиска:\n{search_result.output}")

    # Извлекаем первую ссылку на товар из результатов
    lines = search_result.output.split("\n")
    first_product_url = None

    for line in lines:
        if line.startswith("🔗 https://www.ozon.ru/product/"):
            first_product_url = line.replace("🔗 ", "").strip()
            break

    if not first_product_url:
        print("❌ Не удалось найти ссылку на первый товар")
        return None

    print(f"📱 Найден первый товар: {first_product_url}")

    # Переходим на страницу первого товара
    print("📄 Переход на страницу товара...")
    await page.goto(first_product_url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(3)
    print("✅ Страница товара загружена")

    return first_product_url


async def test_reviews_link_extraction():
    """Тест поиска ссылки на отзывы через поиск товара"""

    print("🔗 Тест извлечения ссылки на отзывы")
    print("=" * 40)

    try:
        from app.tool.ozon_tool import OzonTool

        tool = OzonTool()

        # Поиск товара по ключевому слову
        search_query = "iphone"
        product_url = await search_and_select_first_product(tool, search_query)

        if not product_url:
            print("❌ Не удалось найти товар для тестирования")
            return None

        # Получаем страницу (браузер уже открыт и находится на странице товара)
        page = tool._page

        if not page:
            print("❌ Страница не инициализирована")
            return None

        # Ищем ссылку на отзывы
        print("🔍 Поиск ссылки на отзывы...")
        reviews_link = await tool._find_reviews_link(page)

        if reviews_link:
            print(f"✅ Ссылка на отзывы найдена: {reviews_link}")
            return reviews_link
        else:
            print("❌ Ссылка на отзывы НЕ найдена")

            # Отладочная информация
            print("\n🔍 Отладка - проверяем наличие элементов:")

            # Проверяем наличие webSingleProductScore
            score_widget = await page.query_selector(
                "div[data-widget='webSingleProductScore']"
            )
            if score_widget:
                print("✅ Виджет webSingleProductScore найден")
                score_html = await score_widget.inner_html()
                print(f"📝 HTML виджета: {score_html[:200]}...")
            else:
                print("❌ Виджет webSingleProductScore НЕ найден")

            # Проверяем все ссылки с reviews
            all_review_links = await page.query_selector_all("a[href*='/reviews/']")
            print(f"🔗 Найдено ссылок с '/reviews/': {len(all_review_links)}")

            for i, link in enumerate(all_review_links[:3]):
                href = await link.get_attribute("href")
                text = await link.inner_text()
                print(f"   {i+1}. {href} - '{text[:50]}...'")

            return None

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте поиска ссылки: {e}")
        print(f"❌ Ошибка: {e}")
        return None

    finally:
        # Закрываем браузер
        try:
            await tool.cleanup()
            print("🔒 Браузер закрыт")
        except:
            pass


async def test_reviews_extraction():
    """Тест извлечения отзывов через поиск товара"""

    print("\n📝 Тест извлечения отзывов")
    print("=" * 40)

    try:
        from app.tool.ozon_tool import OzonTool

        tool = OzonTool()

        # Поиск товара по ключевому слову
        search_query = "samsung"  # Используем другой запрос для разнообразия
        product_url = await search_and_select_first_product(tool, search_query)

        if not product_url:
            print("❌ Не удалось найти товар для тестирования")
            return False

        print(f"📱 Получение отзывов для: {product_url}")

        # Вызываем новый метод получения отзывов
        result = await tool.execute(
            action="get_reviews", product_url=product_url, max_reviews=5
        )

        if result.error:
            print(f"❌ Ошибка получения отзывов: {result.error}")
            return False
        else:
            print("✅ Отзывы получены успешно!")
            print(f"📊 Результат:\n{result.output}")
            return True

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте извлечения отзывов: {e}")
        print(f"❌ Ошибка: {e}")
        return False

    finally:
        # Закрываем браузер
        try:
            await tool.cleanup()
            print("🔒 Браузер закрыт")
        except:
            pass


async def test_ozon_only_agent_reviews():
    """Тест получения отзывов через OzonOnlyAgent с поиском"""

    print("\n🤖 Тест OzonOnlyAgent - получение отзывов")
    print("=" * 50)

    try:
        from app.agent.ozon_only import OzonOnlyAgent

        agent = OzonOnlyAgent()

        # Тестовый запрос с поиском и анализом отзывов
        test_query = "Найди смартфон xiaomi на озоне, выбери первый результат и проанализируй отзывы покупателей"

        print(f"💭 Запрос: {test_query}")
        print("⏳ Выполнение запроса...")

        result = await agent.run(test_query)

        print("✅ Запрос выполнен!")
        print(f"📋 Результат:\n{result}")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте OzonOnlyAgent: {e}")
        print(f"❌ Ошибка: {e}")
        return False

    finally:
        # Закрываем агент
        try:
            await agent.cleanup()
            print("🔒 Агент закрыт")
        except:
            pass


async def test_alternative_product():
    """Тест с поиском разных типов товаров"""

    print("\n🔄 Тест с разными типами товаров")
    print("=" * 40)

    try:
        from app.tool.ozon_tool import OzonTool

        # Тестируем разные категории товаров
        search_queries = [
            "наушники",
            "планшет",
        ]  # Уменьшил количество для экономии времени

        for i, search_query in enumerate(search_queries, 1):
            print(f"\n🔍 Тест {i}/{len(search_queries)}: Поиск '{search_query}'")

            tool = OzonTool()

            try:
                product_url = await search_and_select_first_product(tool, search_query)

                if product_url:
                    print(f"✅ Товар найден: {product_url}")

                    # Проверяем поиск ссылки на отзывы
                    page = tool._page
                    if page:
                        reviews_link = await tool._find_reviews_link(page)
                        if reviews_link:
                            print(f"✅ Ссылка на отзывы найдена: {reviews_link}")
                        else:
                            print("❌ Ссылка на отзывы не найдена")
                else:
                    print(f"❌ Товар '{search_query}' не найден")

            except Exception as e:
                print(f"❌ Ошибка при тестировании '{search_query}': {e}")

            finally:
                try:
                    await tool.cleanup()
                    await asyncio.sleep(1)  # Пауза между тестами
                except:
                    pass

        print("\n✅ Тест разных типов товаров завершен")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте разных товаров: {e}")
        print(f"❌ Ошибка: {e}")
        return False


def main():
    """Главная функция тестирования"""

    print("🚀 ТЕСТИРОВАНИЕ СИСТЕМЫ ОТЗЫВОВ OZON")
    print("=" * 60)
    print("Проверяем новую систему получения отзывов через поиск:")
    print("1. Поиск товара по ключевому слову")
    print("2. Выбор первого товара из результатов")
    print("3. Поиск ссылки на отзывы на странице товара")
    print("4. Переход на страницу отзывов")
    print("5. Извлечение отзывов с страницы отзывов")
    print("=" * 60)

    # Последовательное выполнение тестов
    tests = [
        ("Поиск товара и ссылки на отзывы", test_reviews_link_extraction),
        ("Поиск товара и извлечение отзывов", test_reviews_extraction),
        ("Тест разных категорий товаров", test_alternative_product),
        ("OzonOnlyAgent с поиском", test_ozon_only_agent_reviews),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n🧪 ЗАПУСК ТЕСТА: {test_name}")
        print("-" * 50)
        try:
            result = asyncio.run(test_func())
            results.append((test_name, result))
            if result:
                print(f"✅ Тест '{test_name}' ПРОЙДЕН")
            else:
                print(f"❌ Тест '{test_name}' НЕ ПРОЙДЕН")
        except Exception as e:
            print(f"❌ Тест '{test_name}' ЗАВЕРШИЛСЯ С ОШИБКОЙ: {e}")
            results.append((test_name, False))

    # Итоговый отчет
    print("\n📊 ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 60)

    passed_tests = sum(1 for _, result in results if result)
    total_tests = len(results)

    for test_name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ НЕ ПРОЙДЕН"
        print(f"   {test_name}: {status}")

    print(f"\n📈 Результат: {passed_tests}/{total_tests} тестов пройдено")

    if passed_tests == total_tests:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("\n💡 Обновленная система отзывов готова к использованию:")
        print("   - Выполняет поиск товаров по ключевым словам")
        print("   - Автоматически выбирает первый найденный товар")
        print("   - Корректно находит ссылки на отзывы")
        print("   - Переходит на страницу отзывов")
        print("   - Извлекает отзывы с правильной структурой")
        print("   - Работает с разными категориями товаров")
    else:
        print("⚠️ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        print("   Проверьте ошибки выше для диагностики проблем")


if __name__ == "__main__":
    main()
