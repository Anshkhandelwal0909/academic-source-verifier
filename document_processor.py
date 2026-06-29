import io
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize
from PyPDF2 import PdfReader

try:
    stop_words = set(stopwords.words('english'))
except:
    nltk.download('stopwords')
    nltk.download('punkt')
    nltk.download('averaged_perceptron_tagger_eng')
    stop_words = set(stopwords.words('english'))

def classify_sentence(text: str) -> tuple:
    """Returns (status, reason)
    Note: Heuristic skipping (length, structural phrases, references) has been disabled per user request.
    All extracted lines will now be fully parsed and sent to the search engines.
    """
    return ("FACTUAL", "")

def extract_keywords(text: str) -> str:
    words = word_tokenize(text)
    try:
        tagged = nltk.pos_tag(words)
    except:
        return " ".join([w for w in words if w.lower() not in stop_words and w.replace('-','').isalnum()][:8])
    
    keywords = []
    for word, tag in tagged:
        clean_word = word.replace('-', '').replace('.', '')
        if word.lower() in stop_words or not clean_word.isalnum():
            continue
            
        # Keep acronyms (all caps > 1 char), numbers, Nouns (NN, NNP), Adjectives (JJ)
        if (word.isupper() and len(word) > 1) or \
           word.isdigit() or \
           tag.startswith('NN') or \
           tag.startswith('JJ'):
            keywords.append(word)
            
    seen = set()
    unique_keywords = []
    for k in keywords:
        if k.lower() not in seen:
            seen.add(k.lower())
            unique_keywords.append(k)
            
    return " ".join(unique_keywords[:8])

def parse_document(file_content: bytes, filename: str) -> list:
    lines_data = []
    
    if filename.lower().endswith('.pdf'):
        try:
            reader = PdfReader(io.BytesIO(file_content))
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    sentences = sent_tokenize(text.replace('\n', ' '))
                    for s in sentences:
                        s = s.strip()
                        if s:
                            lines_data.append({"page": i+1, "text": s})
        except Exception as e:
            print(f"PDF parsing error: {e}")
    else:
        # Assume text
        text = file_content.decode('utf-8', errors='ignore')
        # Split by newlines first so explicit line breaks aren't merged, then tokenize
        raw_lines = text.split('\n')
        for raw_line in raw_lines:
            raw_line = raw_line.strip()
            if raw_line:
                sentences = sent_tokenize(raw_line)
                for s in sentences:
                    s = s.strip()
                    if s:
                        lines_data.append({"page": 1, "text": s})
                
    for i, item in enumerate(lines_data):
        item["line_index"] = i
        status, reason = classify_sentence(item["text"])
        item["status"] = status
        item["reason"] = reason
        item["sources"] = []
        item["confidence"] = 0.0
        
    return lines_data
