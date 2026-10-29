"""Read immutable plain/gzip evidence without materializing whole JSONL files."""
import csv
import gzip
import json
from pathlib import Path


def open_text(path):
    path = Path(path)
    if path.exists():
        return path.open('rt', encoding='utf-8', newline='')
    return gzip.open(str(path) + '.gz', 'rt', encoding='utf-8', newline='')


def read_json(path):
    with open_text(path) as stream:
        return json.load(stream)


def json_rows(path):
    with open_text(path) as stream:
        for line in stream:
            yield json.loads(line)


def integer_csv_rows(path):
    with open_text(path) as stream:
        for row in csv.DictReader(stream):
            yield {key: int(value) for key, value in row.items()}
