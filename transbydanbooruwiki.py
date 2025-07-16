import csv
import time
import yaml
import re
from TagRelator import get_wikipage
from typing import List, Optional
from AIConfigManager import ConfigManager, AIProvider, AppConfig  # 追加
from AIProvider import AIConfig, BatchProcessResult, TranslatorFactory, AITranslator


# 設定管理インスタンス（グローバル）
config_manager = ConfigManager()
app_config = config_manager.get_config()

# レート制限のための変数
MAX_REQUESTS_PER_SECOND = 4
MIN_INTERVAL = 1.0 / MAX_REQUESTS_PER_SECOND
last_time = time.time()

def sanitize(tag: str) -> str:
    """タグの前処理：アンダースコアをスペースに変換"""
    return tag.replace("_", " ")

def format_prompt(batch: List[str], prefix_prompt: str) -> str:
    """AI用プロンプトを生成"""
    formatted_strings = []

    for item in batch:
        tag = sanitize(item["en"])
        choices = item["choices"]
        # choicesリストを"{...}"の形で連結
        choices_str = ",".join(f"{choice}" for choice in choices)
        formatted = f"翻訳対象: {tag}\n選択肢： {choices_str}"
        formatted_strings.append(formatted)

    final_output = prefix_prompt + "\n".join(formatted_strings)
    # print(final_output)
    return final_output

def rate_limited_request(call_func):
    global last_time
    now = time.time()
    elapsed = now - last_time
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    result = call_func()
    last_time = time.time()
    return result

def select_name_by_ai(translator:AITranslator, prompt: str) -> List[str]:
    # ChatGPT APIなどを用いた処理
    translations = rate_limited_request(lambda: translator.translate(prompt))
    return translations

def load_config(path="config.yaml"):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def score_name(name: str) -> int:
    score = 0

    if re.fullmatch(r'[ァ-ンヴー]+', name):  # 全カタカナ
        score += 10
    elif re.fullmatch(r'[ぁ-んァ-ンー]+', name):  # ひらがな＋カタカナ
        score += 8
    elif re.search(r'\([^\)]+\)', name):  # 括弧あり（補足）
        score += 6
    elif re.search(r'[一-龯]', name) and re.search(r'[ァ-ンぁ-ん]', name):  # 漢字＋カナ混在
        score += 9
    elif re.fullmatch(r'[a-zA-Z0-9_]+', name):  # アルファベットのみ
        score -= 10
    elif re.search(r'[\u4e00-\u9fff]', name) and not re.search(r'[ぁ-んァ-ン]', name):  # 漢字だけ
        score -= 8

    return score

def has_parentheses(name: str) -> bool:
    return re.search(r'\([^\)]+\)', name) is not None

def extract_japanese_name(wikipage_json) -> dict:
    """日本語名を抽出。括弧あり優先。それ以外はAIへ"""
    candidates = wikipage_json.get("other_names", [])
    if not candidates:
        return {"candidates": [], "success": False}

    if len(candidates) == 1:
        # 候補が1つだけの場合はそのまま返す
        return {"candidates": candidates, "success": True}
    else:
        with_paren = [name for name in candidates if has_parentheses(name)]
        if with_paren:
            scored = [(name, score_name(name)) for name in with_paren]
            best = sorted(scored, key=lambda x: x[1], reverse=True)[0][0]
            return {"candidates": [best], "success": True}
        else:
            return {"candidates": candidates, "success": False}

def process_batch(translator: AITranslator, batch: List[dict], prompt_prefix: str,
                  writer: csv.writer, fail_writer: csv.writer):
    """AIによりバッチを処理して出力"""
    if not batch:
        return

    prompt = format_prompt(batch, prompt_prefix)
    ai_result = select_name_by_ai(translator, prompt)

    for i, item in enumerate(batch):
        tag_en = item["en"]
        row = item["row"]
        name_ja = ai_result[i].strip() if ai_result and i < len(ai_result) else ""

        if name_ja:
            writer.writerow([tag_en, name_ja] + row[1:])
            print(f"✔️ {tag_en} → {name_ja} (AI選択)")
        else:
            fail_writer.writerow([tag_en] + row[1:])
            print(f"❌ AI選択失敗: {tag_en}")

    batch.clear()

def load_cache_dict(*filepaths) -> dict:
    """複数の既存CSVファイルから統合キャッシュを作成"""
    cache = {}
    for filepath in filepaths:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if row and len(row) >= 2:
                        cache[row[0]] = row[1]
        except FileNotFoundError:
            continue  # 無い場合は無視
    return cache


def process_file(
    input_path: str = None,
    output_path: str = None,
    failed_path: str = None,
    batch_size: int = None,
    sleep_time: float = None,
    provider: AIProvider = None,
    config: Optional[AIConfig] = None):

    # 設定取得
    input_path = input_path or app_config.files.input_path
    output_path = output_path or app_config.files.output_path
    failed_path = failed_path or app_config.files.failed_path
    batch_size = batch_size or app_config.processing.batch_size
    sleep_time = sleep_time or app_config.processing.sleep_sec
    provider = provider or app_config.default_provider
    auth = (app_config.danbooru.username, app_config.danbooru.api_key)

    # キャッシュとAI準備
    cache = load_cache_dict(output_path, failed_path)

    try:
        translator = TranslatorFactory.create_translator(provider, config)
        print(f"使用するAIプロバイダー: {translator.get_provider_name()}")
    except ValueError as e:
        print(f"✖ 翻訳インスタンスの作成に失敗: {e}")
        return BatchProcessResult([], [], 0, 0)

    with open(input_path, 'r', encoding='utf-8') as infile, \
         open(output_path, 'a', newline='', encoding='utf-8') as outfile, \
         open(failed_path, 'a', newline='', encoding='utf-8') as failfile:

        reader = csv.reader(infile)
        writer = csv.writer(outfile)
        fail_writer = csv.writer(failfile)

        batch = []

        for row in reader:
            if not row or len(row) < 1:
                continue

            tag_en = row[0]
            if tag_en in cache:
                continue

            wikipage = get_wikipage(tag_en, auth=auth)
            tag_info = extract_japanese_name(wikipage) if wikipage else {"candidates": [], "success": False}

            if tag_info["success"]:
                name_ja = tag_info["candidates"][0]
                writer.writerow([tag_en, name_ja] + row[1:])
                print(f"✔️ {tag_en} → {name_ja}")
            elif tag_info["candidates"]:
                batch.append({"en": tag_en, "choices": tag_info["candidates"], "row": row})
            else:
                fail_writer.writerow([tag_en] + row[1:])
                print(f"❌ Failed: {tag_en}")

            if len(batch) == batch_size:
                process_batch(translator, batch, app_config.openai.prompt, writer, fail_writer)

            time.sleep(sleep_time)

        # 残りのバッチ処理
        process_batch(translator, batch, app_config.openai.prompt, writer, fail_writer)

if __name__ == "__main__":

    start_time = time.time()

    config_manager.validate_config()
    process_file()

    end_time = time.time()

    elapsed_time = end_time - start_time
    print(f"処理時間: {elapsed_time:.4f}秒")
