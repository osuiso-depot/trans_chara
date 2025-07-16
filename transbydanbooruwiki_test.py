import csv
import wikipediaapi
import re
import logging
import time
import requests
from TagRelator import collect_related_tags, get_tags, get_wikipage
import yaml

from tqdm import tqdm

# config.yamlから設定を読み込む
DEFAULT_CONFIG_PATH = "config.yaml"
with open(DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

USERNAME = data['danbooru']['username']
API_KEY = data['danbooru']['api_key']

if __name__ == "__main__":
    auth = (USERNAME, API_KEY)

    # result = collect_related_tags("smile", auth=auth, max_depth=2)

    # result = get_tags("chen", auth=auth)
    result = get_wikipage("nanami_chiaki", auth=auth)

    if(result):
        tagname = result["other_names"][0]
        print(f"Tag name: {tagname}\n")


    # import json
    # print(json.dumps(result, indent=2, ensure_ascii=False))
