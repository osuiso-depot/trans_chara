import csv
import wikipediaapi
import re
import logging
import time
import requests
from TagRelator import collect_related_tags, get_tags, get_wikipage
import yaml

from tqdm import tqdm

# ログ設定
logging.basicConfig(
    filename='translation_failures.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

# Wikipedia API 初期化
USER_AGENT = "transbywiki/1.0 (contact: https://github.com/osuiso-depot/trans_chara)"
wiki_en = wikipediaapi.Wikipedia(language='en', user_agent=USER_AGENT)
wiki_ja = wikipediaapi.Wikipedia(language='ja', user_agent=USER_AGENT)

def get_japanese_title(english_name: str) -> str:
    """Wikipediaのlanglinkで日本語タイトルを取得する"""
    page_en = wiki_en.page(english_name)
    if page_en.exists():
        langlinks = page_en.langlinks
        if 'ja' in langlinks:
            return langlinks['ja'].title
    return ""

def format_wikipedia_name(tag: str) -> str:
    """アンダースコア表記をWikipedia風に整形"""
    return tag.replace("_", " ").title()

def load_cache_dict(output_file: str) -> dict:
    """すでに翻訳済みのタグを辞書として読み込む"""
    cache = {}
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row and len(row) >= 2:
                    cache[row[0]] = row[1]  # 英語名 -> 日本語名
    except FileNotFoundError:
        pass  # 初回実行時など、ファイルがなくてもOK
    return cache


def fallback_pixiv_translation(eng_tag: str) -> str:
    """
    Pixiv百科事典から英語タグに該当する日本語名を取得する（暫定）
    - 例: https://dic.pixiv.net/a/Mystia%20Lorelei
    """
    # タグを整形（アンダースコア→スペース）
    title = eng_tag.replace("_", " ").title()
    url = f"https://dic.pixiv.net/a/{title}"

    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            # <title>タグを日本語で返す（暫定処理）
            match = re.search(r"<title>([^<]+)とは.*? - ピクシブ百科事典</title>", response.text)
            if match:
                return match.group(1)
    except Exception as e:
        logging.info(f"Pixiv取得失敗: {eng_tag} - {e}")
    return ""


def translate_file(input_file: str, output_file: str):
    cache = load_cache_dict(output_file)

    with open(input_file, "r", encoding="utf-8") as infile, \
         open(output_file, "a", encoding="utf-8", newline="") as outfile:  # appendモード

        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        for row in tqdm(reader):
            if len(row) < 3:
                continue  # 不正行スキップ

            eng_name, genre, usage = row[0], row[1], row[2]
            related_tags = row[3] if len(row) > 3 else ""

            if eng_name in cache:
                continue  # すでに翻訳済みならスキップ

            wiki_search_name = format_wikipedia_name(eng_name)
            jp_name = get_japanese_title(wiki_search_name)

            # Wikipediaで取得できなければPixiv fallback
            if jp_name == "":
                jp_name = fallback_pixiv_translation(eng_name)

            if jp_name == "":
                logging.info(f"翻訳失敗: {eng_name}")
            else:
                cache[eng_name] = jp_name  # 新たにキャッシュに追加
                print(f"{eng_name} -> {jp_name}")

            time.sleep(0.5)  # アクセス制限対策

            writer.writerow([eng_name, jp_name, genre, usage, related_tags])

if __name__ == "__main__":
    translate_file("split_genres/genre_4.txt", "genre_4_translated.csv")
