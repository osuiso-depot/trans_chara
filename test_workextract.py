import csv
import re

def extract_and_save_works(input_csv_file, output_txt_file):
    """
    CSVファイルからキャラクター名（1列目）を抽出し、
    括弧内の作品名を抽出してテキストファイルに保存します。

    Args:
        input_csv_file (str): 入力CSVファイルのパス。
        output_txt_file (str): 出力テキストファイルのパス。
    """
    extracted_works = []

    try:
        with open(input_csv_file, 'r', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            for row in reader:
                if row:  # 行が空でないことを確認
                    first_column_text = row[0]
                    # 括弧内の文字列を抽出する正規表現
                    match = re.search(r'\((.*?)\)', first_column_text)
                    if match:
                        extracted_works.append(match.group(1))
    except FileNotFoundError:
        print(f"エラー: 指定されたCSVファイル '{input_csv_file}' が見つかりません。")
        return
    except Exception as e:
        print(f"CSVファイルの読み込み中にエラーが発生しました: {e}")
        return

    try:
        extracted_works = list(set(extracted_works))  # 重複を削除
        extracted_works.sort()  # アルファベット順にソート
        with open(output_txt_file, 'w', encoding='utf-8') as outfile:
            outfile.write("\n".join(extracted_works))
        print(f"作品名が正常に '{output_txt_file}' に出力されました。")
    except Exception as e:
        print(f"テキストファイルへの書き込み中にエラーが発生しました: {e}")

# --- 使用例 ---
if __name__ == "__main__":
    # ここに入力CSVファイル名と出力テキストファイル名を設定してください
    input_csv = "translated_tags_4_character.txt"  # 例: "characters.csv"
    output_txt = "extracted_works.txt"

    extract_and_save_works(input_csv, output_txt)
