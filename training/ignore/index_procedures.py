#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import csv
import time
import json
from progressbar import progressbar

codes = []

with open('cie10-es-procedures.csv') as csv_file:
    file_data=csv.reader(csv_file)
    headers=next(file_data)
    codes = [dict(zip(headers,i)) for i in file_data]

headers = {"Content-Type": "application/json"}
epoch = int(time.time())

print("Indexing to Opensearch :runner: :dash:")

for entry in progressbar(codes, redirect_stdout=False):
    r = requests.put(f"http://localhost:9200/procedures-{epoch}/_doc/{entry['code']}", data=json.dumps(entry, ensure_ascii=False), headers=headers)
    if r.status_code != 201:
        print(f"ERROR: {r.status_code} - {entry}")
