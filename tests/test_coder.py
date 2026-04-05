"""Unit tests for forgegod/coder.py — code extraction, AST validation, language detection."""

from __future__ import annotations

from forgegod.coder import ReflexionCoder


class TestExtractCode:
    """Test _extract_code() with various markdown fence formats."""

    def test_extract_code_python_fence(self) -> None:
        """Extract code from Python fence."""
        response = """Here's the code:
```python
def hello():
    print("world")
```
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        code = coder._extract_code(response, "python")
        assert code == "def hello():\n    print(\"world\")"

    def test_extract_code_ts_fence(self) -> None:
        """Extract code from TypeScript fence."""
        response = """Here's the code:
```typescript
const x: number = 42
```
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        code = coder._extract_code(response, "typescript")
        assert code == "const x: number = 42"

    def test_extract_code_js_fence(self) -> None:
        """Extract code from JavaScript fence."""
        response = """Here's the code:
```javascript
function add(a, b) {
    return a + b
}
```
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        code = coder._extract_code(response, "javascript")
        assert code == "function add(a, b) {\n    return a + b\n}"

    def test_extract_code_generic_fence(self) -> None:
        """Extract code from generic fence (no language tag)."""
        response = """Here's the code:
```
def hello():
    print("world")
```
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        code = coder._extract_code(response, "python")
        assert code == "def hello():\n    print(\"world\")"

    def test_extract_code_no_fences_looks_like_code(self) -> None:
        """Extract code when no fences but response looks like code."""
        response = """def hello():
    print("world")
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        code = coder._extract_code(response, "python")
        assert code == "def hello():\n    print(\"world\")"

    def test_extract_code_no_fences_not_code(self) -> None:
        """Extract code when no fences and response doesn't look like code."""
        response = """Here is some text that is not code at all.
It has no fences and no code-like structure.
Just plain text."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        code = coder._extract_code(response, "python")
        expected = (
            "Here is some text that is not code at all.\n"
            "It has no fences and no code-like structure.\n"
            "Just plain text."
        )
        assert code == expected

    def test_extract_code_empty_response(self) -> None:
        """Extract code from empty response."""
        response = ""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        code = coder._extract_code(response, "python")
        assert code == ""

    def test_extract_code_multiple_fences_uses_first(self) -> None:
        """Extract code from response with multiple fences (uses first)."""
        response = """First fence:
```python
def first():
    pass
```
Second fence:
```python
def second():
    pass
```
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        code = coder._extract_code(response, "python")
        assert code == "def first():\n    pass"

    def test_extract_code_py_fence(self) -> None:
        """Extract code from Python fence with 'py' tag."""
        response = """Here's the code:
```py
def hello():
    print("world")
```
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        code = coder._extract_code(response, "python")
        assert code == "def hello():\n    print(\"world\")"

    def test_extract_code_python3_fence(self) -> None:
        """Extract code from Python fence with 'python3' tag."""
        response = """Here's the code:
```python3
def hello():
    print("world")
```
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        code = coder._extract_code(response, "python")
        assert code == "def hello():\n    print(\"world\")"


class TestValidatePythonAst:
    """Test _validate_python_ast() with valid and invalid code."""

    def test_valid_simple_function(self) -> None:
        """Validate simple valid Python function."""
        code = """def hello():
    print("world")
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        valid, error = coder._validate_python_ast(code)
        assert valid is True
        assert error is None

    def test_valid_class(self) -> None:
        """Validate valid Python class."""
        code = """class MyClass:
    def __init__(self, name):
        self.name = name
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        valid, error = coder._validate_python_ast(code)
        assert valid is True
        assert error is None

    def test_valid_import(self) -> None:
        """Validate code with imports."""
        code = """import os
import sys
from typing import Optional
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        valid, error = coder._validate_python_ast(code)
        assert valid is True
        assert error is None

    def test_valid_async_function(self) -> None:
        """Validate async function."""
        code = """async def fetch_data():
    return await some_async_call()
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        valid, error = coder._validate_python_ast(code)
        assert valid is True
        assert error is None

    def test_valid_type_hints(self) -> None:
        """Validate code with type hints."""
        code = """def add(a: int, b: int) -> int:
    return a + b
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        valid, error = coder._validate_python_ast(code)
        assert valid is True
        assert error is None

    def test_invalid_missing_colon(self) -> None:
        """Validate code with missing colon (syntax error)."""
        code = """def hello()
    print("world")
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        valid, error = coder._validate_python_ast(code)
        assert valid is False
        assert error is not None
        assert "SyntaxError" in error

    def test_invalid_missing_paren(self) -> None:
        """Validate code with missing parentheses."""
        code = """def hello(name)
    print("world")
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        valid, error = coder._validate_python_ast(code)
        assert valid is False
        assert error is not None
        assert "SyntaxError" in error

    def test_invalid_unclosed_string(self) -> None:
        """Validate code with unclosed string."""
        code = """def hello():
    print("world
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        valid, error = coder._validate_python_ast(code)
        assert valid is False
        assert error is not None
        assert "SyntaxError" in error

    def test_invalid_missing_comma(self) -> None:
        """Validate code with missing comma in tuple."""
        code = """def get_coords():
    return (1, 2)
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        valid, error = coder._validate_python_ast(code)
        assert valid is True
        assert error is None

    def test_invalid_missing_comma_in_tuple(self) -> None:
        """Validate code with missing comma in tuple (edge case)."""
        code = """def get_coords():
    return 1 2
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        valid, error = coder._validate_python_ast(code)
        assert valid is False
        assert error is not None
        assert "SyntaxError" in error

    def test_invalid_indentation(self) -> None:
        """Validate code with incorrect indentation."""
        code = """def hello():
print("world")
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        valid, error = coder._validate_python_ast(code)
        assert valid is False
        assert error is not None
        assert "SyntaxError" in error

    def test_invalid_extra_indent(self) -> None:
        """Validate code with extra indentation."""
        code = """    def hello():
        print("world")
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        valid, error = coder._validate_python_ast(code)
        assert valid is False
        assert error is not None
        assert "SyntaxError" in error

    def test_invalid_syntax_error_line_number(self) -> None:
        """Validate that error message includes line number."""
        code = """def hello()
    print("world")
"""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        valid, error = coder._validate_python_ast(code)
        assert valid is False
        assert error is not None
        assert "SyntaxError at line" in error


class TestDetectLanguage:
    """Test _detect_language() with various file extensions."""

    def test_detect_python(self) -> None:
        """Detect Python from .py extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("script.py")
        assert lang == "python"

    def test_detect_typescript(self) -> None:
        """Detect TypeScript from .ts extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("script.ts")
        assert lang == "typescript"

    def test_detect_typescript_tsx(self) -> None:
        """Detect TypeScript from .tsx extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("component.tsx")
        assert lang == "typescript"

    def test_detect_javascript(self) -> None:
        """Detect JavaScript from .js extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("script.js")
        assert lang == "javascript"

    def test_detect_javascript_jsx(self) -> None:
        """Detect JavaScript from .jsx extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("component.jsx")
        assert lang == "javascript"

    def test_detect_go(self) -> None:
        """Detect Go from .go extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("main.go")
        assert lang == "go"

    def test_detect_rust(self) -> None:
        """Detect Rust from .rs extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("main.rs")
        assert lang == "rust"

    def test_detect_ruby(self) -> None:
        """Detect Ruby from .rb extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("script.rb")
        assert lang == "ruby"

    def test_detect_java(self) -> None:
        """Detect Java from .java extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("Main.java")
        assert lang == "java"

    def test_detect_c(self) -> None:
        """Detect C from .c extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("main.c")
        assert lang == "c"

    def test_detect_cpp(self) -> None:
        """Detect C++ from .cpp extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("main.cpp")
        assert lang == "cpp"

    def test_detect_bash(self) -> None:
        """Detect Bash from .sh extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("script.sh")
        assert lang == "bash"

    def test_detect_sql(self) -> None:
        """Detect SQL from .sql extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("query.sql")
        assert lang == "sql"

    def test_detect_yaml(self) -> None:
        """Detect YAML from .yml extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("config.yml")
        assert lang == "yaml"

    def test_detect_yaml_yaml(self) -> None:
        """Detect YAML from .yaml extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("config.yaml")
        assert lang == "yaml"

    def test_detect_toml(self) -> None:
        """Detect TOML from .toml extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("config.toml")
        assert lang == "toml"

    def test_detect_json(self) -> None:
        """Detect JSON from .json extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("data.json")
        assert lang == "json"

    def test_detect_markdown(self) -> None:
        """Detect Markdown from .md extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("readme.md")
        assert lang == "markdown"

    def test_detect_html(self) -> None:
        """Detect HTML from .html extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("index.html")
        assert lang == "html"

    def test_detect_css(self) -> None:
        """Detect CSS from .css extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("style.css")
        assert lang == "css"

    def test_detect_unknown_extension_defaults_to_python(self) -> None:
        """Detect unknown extension defaults to Python."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("unknown.xyz")
        assert lang == "python"

    def test_detect_no_extension_defaults_to_python(self) -> None:
        """Detect file with no extension defaults to Python."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("script")
        assert lang == "python"

    def test_detect_uppercase_extension(self) -> None:
        """Detect with uppercase extension (case-sensitive)."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("SCRIPT.PY")
        assert lang == "python"

    def test_detect_mixed_case_extension(self) -> None:
        """Detect with mixed case extension."""
        coder = ReflexionCoder.__new__(ReflexionCoder)
        lang = coder._detect_language("script.Py")
        assert lang == "python"
