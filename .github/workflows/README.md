# GitHub Actions Workflows

## Available Workflows

### `django-ci.yml`

Runs on every push and pull request to `main`.

Steps:
1. Spin up PostgreSQL 16 + Redis 7 services
2. Install Python dependencies (`pip install -r requirements.txt`)
3. Run database migrations (`python manage.py migrate`)
4. Check for missing migrations (`makemigrations --check --dry-run`)
5. Run test suite with coverage (`pytest --cov=apps --cov-fail-under=40`)

> **Known gap (Bug B7):** Step 5 is declared in `pytest.ini` but the `pytest` call is not yet wired into the workflow. The coverage gate is not enforced in CI. Fix: add the `pytest` step to `django-ci.yml`.

## Adding New Workflow Steps

Follow the existing job structure in `django-ci.yml`. Always pass `--settings=config.settings.ci` (not `dev`) so `DEBUG=False` in CI.

```yaml
- name: Run tests
  env:
    DJANGO_SETTINGS_MODULE: config.settings.ci
  run: |
    pytest --cov=apps --cov-report=xml --cov-fail-under=40
```

## Documentation

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest-django](https://pytest-django.readthedocs.io/)
