import json
import os

from invoke import task


CWD = os.path.abspath(os.path.dirname(__file__))


@task
def linters(c):
    """Run linters"""

    cmd = "poetry run ruff check cwtch"
    c.run(cmd)


@task
def tests(c):
    """Run tests"""

    cmd = (
        "poetry run coverage run --data-file=artifacts/.coverage --source cwtch "
        "-m pytest -v --maxfail=1 --benchmark-columns=min,max,mean,stddev,median,ops tests/ && "
        "poetry run coverage json --data-file=artifacts/.coverage -o artifacts/coverage.json && "
        "poetry run coverage report --data-file=artifacts/.coverage -m"
    )
    c.run(cmd)


@task
def generate_coverage_gist(c):
    with open("artifacts/coverage.json") as f:
        data = json.load(f)
    percent = int(data["totals"]["percent_covered_display"])
    if percent >= 90:
        color = "brightgreen"
    elif percent >= 75:
        color = "green"
    elif percent >= 50:
        color = "yellow"
    else:
        color = "red"

    data = {
        "description": "Cwtch shields.io coverage json data",
        "files": {
            "coverage.json": {
                "content": json.dumps(
                    {
                        "schemaVersion": 1,
                        "label": "coverage",
                        "message": f"{percent}%",
                        "color": color,
                    }
                )
            },
        },
    }

    with open("artifacts/shields_io_coverage_gist_data.json", "w") as f:
        f.write(json.dumps(data))


@task
def build_docs(c):
    """Build documentation"""

    cmd = "poetry run mkdocs build -f docs/mkdocs.yml"
    c.run(cmd)

    cmd = "poetry run mkdocs build -f docs/en/mkdocs.yml -d ../site/en/"
    c.run(cmd)

    cmd = "poetry run mkdocs build -f docs/ru/mkdocs.yml -d ../site/ru/"
    c.run(cmd)
