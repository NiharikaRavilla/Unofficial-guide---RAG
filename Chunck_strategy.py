from pathlib import Path
import pandas as pd

# Change this to your document folder
DATA_DIR = Path("data")

results = []

total_chars = 0
total_words = 0
total_tokens = 0

for file_path in DATA_DIR.rglob("*.txt"):

    try:
        text = file_path.read_text(encoding="utf-8")

        char_count = len(text)
        word_count = len(text.split())

        # Rough token estimate
        # OpenAI approximation:
        # 1 token ≈ 4 characters
        token_count = round(char_count / 4)

        results.append({
            "document": file_path.name,
            "characters": char_count,
            "words": word_count,
            "estimated_tokens": token_count
        })

        total_chars += char_count
        total_words += word_count
        total_tokens += token_count

    except Exception as e:
        print(f"Error reading {file_path}: {e}")

df = pd.DataFrame(results)

print("\nDOCUMENT STATISTICS\n")
print(df.sort_values("characters", ascending=False))

print("\n" + "=" * 60)
print("CORPUS TOTALS")
print("=" * 60)

print(f"Total Documents : {len(df)}")
print(f"Total Characters: {total_chars:,}")
print(f"Total Words     : {total_words:,}")
print(f"Total Tokens    : {total_tokens:,}")

# Save report
df.to_csv("document_statistics.csv", index=False)

print("\nSaved report -> document_statistics.csv")