"""
Modul analisis teks berbasis leksikon heuristik (VADER) untuk ekstraksi valensi polaritas sentimen spesifik domain keuangan.
"""
from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
from typing import Dict
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)
sia = SentimentIntensityAnalyzer()

def analyze_sentiment_vader(text: str) -> Dict:
    scores = sia.polarity_scores(text)
    compound = scores['compound']
    if compound >= 0.05:
        label = 'positive'
    elif compound <= -0.05:
        label = 'negative'
    else:
        label = 'neutral'
    return {'compound': compound, 'pos': scores['pos'], 'neu': scores['neu'], 'neg': scores['neg'], 'label': label}
if __name__ == '__main__':
    test_texts = ['Bitcoin is going to the moon! Great investment!', 'Crypto market crash, everyone is losing money', 'The price is stable today']
    for text in test_texts:
        result = analyze_sentiment_vader(text)
        print(f'Text: {text}')
        print(f"Sentiment: {result['label']} (score: {result['compound']:.3f})")
        print()
