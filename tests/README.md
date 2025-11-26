# OmniTrackr Test Suite

Comprehensive test suite for ensuring all functionality remains intact during development.

## Running Tests

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run All Tests
```bash
pytest
```

### Run with Coverage
```bash
pytest --cov=app --cov-report=html
```

### Run Specific Test File
```bash
pytest tests/test_auth.py
```

### Run Specific Test
```bash
pytest tests/test_auth.py::TestAuthEndpoints::test_login_success
```

### Run with Verbose Output
```bash
pytest -v
```

## Test Structure

### `tests/conftest.py`
- Test fixtures and configuration
- Database setup for testing
- Test client creation
- Sample data fixtures

### `tests/test_auth.py`
- Password hashing and verification
- JWT token creation and validation
- User registration
- Login functionality
- Email verification
- Password reset

### `tests/test_crud.py`
- User CRUD operations
- Movie CRUD operations
- TV Show CRUD operations
- Search and filtering
- Update and delete operations

### `tests/test_api.py`
- API endpoint testing
- Authentication requirements
- Movie endpoints
- TV Show endpoints
- Export/Import functionality
- Search and sorting

### `tests/test_email.py`
- Email token generation
- Token verification
- Token expiration
- Reset token functionality

## Test Coverage

The test suite covers:

✅ **Authentication**
- User registration
- Login (username and email)
- Password hashing and verification
- JWT token creation and validation
- Email verification
- Password reset

✅ **CRUD Operations**
- Create, Read, Update, Delete for all entities
- User data isolation
- Search functionality
- Sorting functionality

✅ **API Endpoints**
- All REST endpoints
- Authentication requirements
- Error handling
- Data validation

✅ **Email Utilities**
- Token generation
- Token verification
- Token expiration

## Continuous Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest
```

## Adding New Tests

When adding new features:

1. **Add tests first** (TDD approach)
2. **Test the happy path** - normal operation
3. **Test error cases** - invalid input, missing data
4. **Test edge cases** - boundary conditions
5. **Test security** - authentication, authorization

### Example Test Structure

```python
class TestNewFeature:
    """Test new feature functionality."""
    
    def test_feature_success(self, client):
        """Test successful feature operation."""
        response = client.post("/new-endpoint", json={"data": "value"})
        assert response.status_code == 200
    
    def test_feature_error(self, client):
        """Test feature error handling."""
        response = client.post("/new-endpoint", json={})
        assert response.status_code == 400
```

## Notes

- Tests use an in-memory SQLite database
- Each test gets a fresh database
- No external dependencies required
- Tests are isolated and can run in parallel
- All sensitive operations are mocked where appropriate

