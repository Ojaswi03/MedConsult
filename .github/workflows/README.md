# GitHub Actions Workflows

This directory contains CI/CD workflow definitions for GitHub Actions.

## Available Workflows

### `django-ci.yml`
Continuous Integration workflow that runs on push and pull requests:
- Sets up PostgreSQL and Redis services
- Installs Python dependencies
- Runs database migrations
- Executes Django tests
- Checks for missing migrations

## Usage

Workflows automatically trigger based on their configuration:
- **Push to main/develop**: Runs full CI pipeline
- **Pull requests**: Runs tests and validation

## Adding New Workflows

Create `.yml` files in this directory following the GitHub Actions syntax:

```yaml
name: Workflow Name
on: [push, pull_request]
jobs:
  job-name:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # ... your steps here
```

## Documentation

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Django CI/CD Best Practices](https://docs.djangoproject.com/en/stable/topics/testing/)
