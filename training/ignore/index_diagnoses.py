#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import csv
import time
import json
from progressbar import progressbar

codes = []

def transform_fields(code):
    female_only = code.pop("femalesOnly") != ""
    male_only = code.pop("malesOnly") != ""

    if female_only:
        code["exclusiveGender"] = "F"
    elif male_only:
        code["exclusiveGender"] = "M"
    else:
        code["exclusiveGender"] = ""

    code["perinatal"] = code["perinatal"] != "" 
    code["pediatric"] = code["pediatric"] != ""
    code["maternity"] = code["maternity"] != ""
    code["adult"] = code["adult"] != ""
    code["poaExempt"] = code["poaExempt"] != ""
    code["noPrincipal"] = code["noPrincipal"] != ""
    code["vcdp"] = code.pop("vcdp") != ""

with open('cie10-es-diagnoses.csv') as csv_file:
    file_data=csv.reader(csv_file)
    headers=next(file_data)
    codes = [dict(zip(headers,i)) for i in file_data]

headers = {"Content-Type": "application/json"}
epoch = int(time.time())

print("Indexing to Opensearch :runner: :dash:")

for entry in progressbar(codes, redirect_stdout=True):
    transform_fields(entry)
    r = requests.put(f"http://localhost:9200/diagnoses_{epoch}/_doc/{entry['code']}", data=json.dumps(entry, ensure_ascii=False), headers=headers)
    if r.status_code != 201:
        print(f"ERROR: {r.status_code} - {entry}")

