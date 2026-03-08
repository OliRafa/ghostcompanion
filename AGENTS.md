# Ghostcompanion Developer Guide

This document provides guidelines for agents and developers working on the Ghostcompanion repository.

## 1. Build, Lint, and Test

This project uses **Poetry** for dependency management and packaging.

### Dependencies
- **Install dependencies**:
  ```bash
  poetry install
  ```

### Testing
- **Run all tests**:
  ```bash
  poetry run pytest
  ```
- **Run a specific test file**:
  ```bash
  poetry run pytest tests/unit/core/entity/test_asset.py
  ```
- **Run a specific test class**:
  ```bash
  poetry run pytest tests/unit/core/entity/test_asset.py::TestHasTrade
  ```
- **Run a single test case**:
  ```bash
  poetry run pytest tests/unit/core/entity/test_asset.py::TestHasTrade::should_return_true_when_trade_exists
  ```
- **Test Naming Convention**: Tests MUST start with `should_` or `when_` (configured in `pyproject.toml`).

### Linting and Formatting
- **Check code quality (Lint)**:
  ```bash
  poetry run pylama .
  ```
- **Format code**:
  ```bash
  poetry run black .
  poetry run isort .
  ```
- **Check formatting without changes**:
  ```bash
  poetry run black --check .
  poetry run isort --check-only .
  ```
- **Configuration**:
  - `black` handles formatting (line length 88).
  - `isort` sorts imports (profile "black").
  - `pylama` handles linting (ignoring errors handled by black: E203, E231, W503).

## 2. Code Style and Conventions

### General
- **Python Version**: Target Python 3.12+.
- **Type Hinting**: Mandatory for function arguments and return types. Use `typing` module or standard collections.
  ```python
  def calculate_total(items: list[Item]) -> Decimal:
      ...
  ```
- **Docstrings**: Add docstrings to public modules, classes, and methods if the logic is complex.

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `ImportCoinbaseTransactions`).
- **Functions/Variables**: `snake_case` (e.g., `get_symbol_mappings`).
- **Private Members**: Prefix with `_` (e.g., `_filter_zero_network_fees`).
- **Constants**: `UPPER_CASE` (e.g., `DEFAULT_TIMEOUT`).
- **Tests**: `should_<expected_behavior>` or `when_<condition>_should_<behavior>`.
  - Example: `should_return_true_when_trade_exists`

### Imports
- **Absolute Imports**: Always use absolute imports rooted at `ghostcompanion`.
  - Good: `from ghostcompanion.core.entity.trade import Trade`
  - Bad: `from ..entity.trade import Trade`
- **Sorting**: Imports must be sorted alphabetically and separated by type (stdlib, third-party, local) - handled by `isort`.

### Error Handling
- Use specific exceptions defined in the project or standard library.
- Avoid bare `except:` clauses.
- Use `try...except` blocks to handle expected errors gracefully (e.g., `SymbolMappingsNotFoundException`).

### Architecture (Clean Architecture)
The project follows a Clean Architecture structure:
- **`src/ghostcompanion/core`**: Contains business logic, entities, and use cases. No dependencies on external frameworks or infrastructure.
  - `entity`: Domain objects (e.g., `Portfolio`, `Trade`).
  - `usecase`: Application business rules (e.g., `ImportCoinbaseTransactions`).
  - `provider` / `ports`: Interfaces for external services.
- **`src/ghostcompanion/infra`**: Implementations of interfaces (adapters).
  - `coinbase`, `ghostfolio`, `yahoo_finance`: API clients and adapters.
- **`src/ghostcompanion/configs`**: Configuration and settings (e.g., `Settings` class loading from env).
- **`src/ghostcompanion/repositories`**: Data access layer.

### Testing Strategy
- **Mandatory Coverage**: Every feature MUST have proper test coverage to prevent regressions.
- **Development Process**: Write tests to drive development and uncover bugs during implementation.
- **Unit Tests** (`tests/unit`): Test individual components in isolation.
- **Integration Tests** (`tests/integration`): Test interactions between components.
- **Fixtures**: Use `pytest.fixture` heavily. Group common fixtures in "Factory" classes or `conftest.py`.

## 3. CI/CD Workflows

GitHub Actions workflows are defined in `.github/workflows/`:

- **`continuous_integration.yml`**: Runs on push/PR to main
  - Checks code formatting with Black
  - Validates import sorting with isort
  - Runs pytest test suite
  
- **`continuous_delivery.yml`**: Runs on push to main
  - Creates semantic releases
  - Builds and publishes Docker images

## 4. Workflow and Commits

### Commit Messages
- **Format**: Follow [Conventional Commits](https://www.conventionalcommits.org/).
- **Structure**: `type(scope): description`
  - `feat`: New feature (triggers minor release)
  - `fix`: Bug fix (triggers patch release)
  - `docs`: Documentation changes
  - `style`: Formatting, missing semi colons, etc; no code change
  - `refactor`: Refactoring production code
  - `test`: Adding missing tests, refactoring tests
  - `chore`: Updating build tasks, package manager configs, etc
- **Semantic Release**: This project uses semantic releases. Correct commit types are crucial for automated versioning.
