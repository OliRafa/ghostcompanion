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

### Abbreviations

Avoid abbreviations in code unless they are:
1. **Widely known** (e.g., `API`, `HTTP`, `URL`, `ID`)
2. **Domain-specific** (e.g., `USD`, `EUR`, `GBP` for currency codes)
3. **Standard conventions** (e.g., `i`, `j`, `k` for loop indices)

When using domain-specific abbreviations, prefer the full name unless the abbreviation is universally understood in that domain. Examples:
- ✅ `transaction` (not `tx`)
- ✅ `balance` (not `bal`)
- ✅ `currency` (not `curr`)
- ✅ `account` (not `acc`)
- ✅ `amount` (not `amt`)
- ✅ `value` (not `val`)
- ✅ `identifier` (acceptable: `id` - widely known)
- ✅ `API`, `HTTP`, `URL` (widely known technical terms)
- ✅ `USD`, `EUR`, `GBP` (domain-specific currency codes)

- Use specific exceptions defined in the project or standard library.
- Avoid bare `except:` clauses.
- Use `try...except` blocks to handle expected errors gracefully (e.g., `SymbolMappingsNotFoundException`).

### Comments

Comments should explain **WHY** the code exists or particular business decisions, not **WHAT** the code does. The code itself should be descriptive enough to explain its logic.

**Good comments explain:**
- Business rules and domain logic rationale
- Non-obvious side effects or consequences
- Workarounds for external system limitations
- References to external documentation or requirements

**Avoid comments that:**
- Describe obvious code behavior
- Explain what the next line does when the code is clear
- Redundantly describe what type hints already show
- State what docstrings already document

**Examples:**

❌ Bad - Explains obvious code:
```python
# Get the trades
result = self._get_trades()
```

✅ Good - Explains business logic:
```python
# Tastytrade SDK pagination bug: only returns first page
# per_page=1500 is workaround until upstream fix
result = self._account.get_history(per_page=1500)
```

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

### Testing Patterns

#### InMemory Repository Pattern

When testing components that depend on external APIs or ports, use the **InMemory repository pattern** instead of mocks:

- **Location**: Place InMemory implementations in `tests/infra/` (e.g., `InMemoryTastytradeApi`, `InMemoryCoinbaseApi`)
- **Implementation**: Create concrete classes that implement the Port interfaces with in-memory data storage
- **Benefits**:
  - Tests verify actual integration between layers
  - No need to update mocks when interfaces change
  - Tests are more representative of real behavior
  - Encourages designing testable interfaces

**Example**:

```python
# In tests/infra/tastytrade_api.py
class InMemoryTastytradeApi(TastytradePort):
    def __init__(self):
        self._trades = TRANSACTIONS

    def get_trades_history(self) -> list[Transaction]:
        return self._trades
```

**Usage in tests**:

```python
def test_should_return_all_assets(self):
    provider = TastytradeProvider(InMemoryTastytradeApi())
    results = provider.get_assets()
    assert len(results) == 3
```

**For test-specific scenarios**: If you need to test edge cases that require specific data, extend the InMemory implementation or add test data to `tests/resources/` rather than creating one-off mocks.

#### UseCase Testing

UseCases should be tested with **Integration Tests** using **InMemory repositories**, not Unit Tests with mocks:

- **Why InMemory over Mocks**: 
  - Tests verify actual integration between layers (UseCase -> Provider -> Port)
  - No need to update mocks when interfaces change
  - Tests are more representative of real behavior
  - Ensures the orchestration logic works correctly

- **Test Location**: Place UseCase integration tests in `tests/integration/core/usecase/`

- **Implementation Pattern**:
  ```python
  # In tests/integration/core/usecase/test_import_cash_balances.py
  def test_should_synchronize_cash_balances():
      # Arrange
      tastytrade_api = InMemoryTastytradeCashApi()
      ghostfolio_api = InMemoryGhostfolioCashApi()
      
      # Set up test data in InMemory repositories
      tastytrade_api.set_cash_balances([
          CashBalance(date=date(2024, 1, 1), amount=Decimal("1000"), currency="USD"),
      ])
      
      provider = TastytradeCashBalanceProvider(tastytrade_api)
      ghostfolio = GhostfolioAdapter(ghostfolio_api)
      use_case = ImportTastytradeCashBalances(provider, ghostfolio)
      
      # Act
      result = use_case.execute()
      
      # Assert
      assert len(ghostfolio_api.get_account_balances("account-123")) == 1
  ```

- **Unit Tests for UseCases**: Only appropriate for pure business logic within the UseCase itself (rare). Most UseCase testing should be integration tests.

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

### Commit Principles

Commits should be **small, self-contained units of work** that:
- ✅ Always leave the codebase in a working state
- ✅ Can be easily rolled back if needed
- ✅ Focus on a single logical change
- ✅ Include all related changes (code, tests, docs) in one commit

**Guidelines:**
- Avoid mixing unrelated changes in a single commit
- Each commit should pass all tests on its own
- If a commit introduces a bug, it should be easy to revert without affecting other functionality
- When in doubt, split into smaller commits rather than making one large commit

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
