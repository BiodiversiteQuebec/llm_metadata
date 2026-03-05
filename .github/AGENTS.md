# llm_metadata Project Instructions

## Project Overview
Python package for extracting and extracting metadata from biodiversity research using LLMs. Focus on data integration from Zenodo, Dryad, and other sources.

## Repository Structure
- `src/llm_metadata/` - Main source code with API clients (Zenodo, Dryad) and classification modules
- `notebooks/` - Jupyter notebooks for analysis and evaluation
- `tests/` - Test suite with pytest
- `docs/` - Documentation including feature tables

## Development Workflow

### Setup & Environment
- Always use Python 3.9+
- Install with: `pip install -e .` from project root
- Dependencies managed via `pyproject.toml`

### Code Style
- Follow PEP 8 conventions
- Use Pydantic for data validation and schemas (see `src/llm_metadata/schemas/`)
- Type hints required for all functions
- Keep functions focused and well-documented

### Testing
- Run tests: `python -m unittest discover tests/`
- Framework: `unittest` (Python standard library)
- Add tests for new features in `tests/`
- Use mocking for external API calls
- Test class naming: `class TestFeatureName(unittest.TestCase)`

### Schemas & Data Models
- Define data structures in `src/llm_metadata/schemas/`
- Inherit from Pydantic BaseModel
- Include validation rules and field descriptions

### Working with Notebooks
- Notebooks are for exploration and evaluation, not production code
- Document results and findings clearly
- Save results to `notebooks/results/` with timestamped folders
- **Follow lab logging protocol:** See `.github/LAB_LOGGING.md` for documentation standards

### API Integration
- API clients in `dryad.py` and `zenodo.py`
- Handle rate limiting and errors gracefully
- Use environment variables for API keys
