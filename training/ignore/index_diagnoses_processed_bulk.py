#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import csv
import time
import progressbar

# Load the data from the CSV file
with open('cie10-es-diagnoses_processed.csv') as csv_file:
    file_data = csv.reader(csv_file)
    headers = next(file_data)
    codes = [dict(zip(headers, i)) for i in file_data]

# Prepare headers and epoch
headers = {"Content-Type": "application/json"}
epoch = int(time.time())
index_name = f"diagnoses_processed_{epoch}"

# Define the mapping for the index
mapping = {
    "mappings": {
        "properties": {
            "text": {"type": "keyword"},
            "label": {"type": "text"},
        }
    }
}

# Create the index with the mapping
response = requests.put(f"http://localhost:9200/{index_name}", headers=headers, data=json.dumps(mapping))
if response.status_code == 200:
    print(f"Index {index_name} created successfully.")
else:
    print(f"Failed to create index {index_name}: {response.status_code}")
    print(response.text)

print("Indexing to Opensearch :runner: :dash: - BULK!")

# Function to send bulk data to Elasticsearch
def send_bulk_data(bulk_data):
    bulk_data_str = '\n'.join(bulk_data) + '\n'
    r = requests.post("http://localhost:9200/_bulk", data=bulk_data_str, headers=headers)
    if r.status_code != 200:
        print(f"Bulk indexing failed: {r.status_code}")
        print(r.text)

# Prepare and send bulk data in batches of 100
batch_size = 100
bulk_data = []

# Initialize the progress bar
bar = progressbar.ProgressBar(max_value=len(codes))

for i, entry in enumerate(codes):
    #entry = transform_fields(entry)
    action = {
        "index": {
            "_index": index_name,
            "_id": entry['label']
        }
    }
    bulk_data.append(json.dumps(action, ensure_ascii=False))
    bulk_data.append(json.dumps(entry, ensure_ascii=False))

    # Send the batch if it reaches the batch size
    if (i + 1) % batch_size == 0:
        send_bulk_data(bulk_data)
        bulk_data = []
    
    # Update the progress bar
    bar.update(i + 1)

# Send any remaining data
if bulk_data:
    send_bulk_data(bulk_data)

# Finish the progress bar
bar.finish()

