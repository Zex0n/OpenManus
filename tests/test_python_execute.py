import pytest
import asyncio
from app.tool.python_execute import PythonExecute

@pytest.mark.asyncio
async def test_python_execute_success():
    tool = PythonExecute()
    code = 'print("hello world")'
    result = await tool.execute(code)
    assert 'hello world' in result.get('observation', '')
    print("result", result)
    assert result.get('success', True) is not False

@pytest.mark.asyncio
async def test_python_execute_exception():
    tool = PythonExecute()
    code = 'raise ValueError("test error")'
    result = await tool.execute(code)
    assert 'test error' in result.get('observation', '')
    assert result.get('success', False) is False

@pytest.mark.asyncio
async def test_python_execute_timeout():
    tool = PythonExecute()
    code = 'while True: pass'
    result = await tool.execute(code, timeout=1)
    assert 'timeout' in result.get('observation', '')
    assert result.get('success', False) is False
