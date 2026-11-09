"""Перевірка середовища: python src/check_env.py [--llm]"""
import sys
import spacy
from config import RAW_DIR, SPACY_MODEL, GEMINI_MODEL, gemini_key


def main():
    nlp = spacy.load(SPACY_MODEL)
    docs = sorted(RAW_DIR.glob("*.txt"))
    print(f"spaCy {spacy.__version__}, модель {SPACY_MODEL}: OK; документів: {len(docs)}")
    text = docs[0].read_text(encoding="utf-8")
    print("NER-приклад:", [(e.text, e.label_) for e in nlp(text).ents][:6])
    if "--llm" in sys.argv:
        from google import genai
        client = genai.Client(api_key=gemini_key())
        r = client.models.generate_content(model=GEMINI_MODEL, contents="Reply with the single word: ok")
        print(f"Gemini {GEMINI_MODEL}:", r.text.strip())


if __name__ == "__main__":
    main()
