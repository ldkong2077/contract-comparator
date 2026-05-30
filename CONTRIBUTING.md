# Contributing to Contract Comparator

[English](CONTRIBUTING.md) | [中文](CONTRIBUTING_zh.md)

We love your input! We want to make contributing to this project as easy and transparent as possible.

## Development Process

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
6. Issue that pull request!

## Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) style guide
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use descriptive variable names (Chinese pinyin or English)

## Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`, `security`

Examples:
- `feat(ocr): add EasyOCR fallback engine`
- `fix(comparator): handle empty date list`
- `docs(api): update API reference`
- `security(auth): fix API key leak in logs`

## Testing

- Run tests: `pytest tests/ -v`
- Run with coverage: `pytest tests/ --cov=.`
- All new features must include tests

## Pull Request Process

1. Update the README.md with details of changes if needed
2. Update the CHANGELOG.md with a brief description
3. The PR will be merged once you have the sign-off of maintainers

## Any contributions you make will be under the MIT Software License

When you submit code changes, your submissions are understood to be under the same [MIT License](LICENSE) that covers the project.
