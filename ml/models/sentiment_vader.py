"""
VADER sentiment analysis for quick sentiment scoring.
"""
from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
from typing import Dict

# Download VADER lexicon if not already present
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

# Initialize VADER analyzer
sia = SentimentIntensityAnalyzer()

def analyze_sentiment_vader(text: str) -> Dict:
    """
    Analyze sentiment using VADER.
    
    Returns:
        dict: {
            'compound': float (-1 to 1),
            'pos': float (0 to 1),
            'neu': float (0 to 1),
            'neg': float (0 to 1),
            'label': str ('positive', 'neutral', 'negative')
        }
    """
    scores = sia.polarity_scores(text)
    
    # Determine label based on compound score
    compound = scores['compound']
    if compound >= 0.05:
        label = 'positive'
    elif compound <= -0.05:
        label = 'negative'
    else:
        label = 'neutral'
    
    return {
        'compound': compound,
        'pos': scores['pos'],
        'neu': scores['neu'],
        'neg': scores['neg'],
        'label': label
    }

if __name__ == "__main__":
    # Test
    test_texts = [
        "Bitcoin is going to the moon! Great investment!",
        "Crypto market crash, everyone is losing money",
        "The price is stable today"
    ]
    
    for text in test_texts:
        result = analyze_sentiment_vader(text)
        print(f"Text: {text}")
        print(f"Sentiment: {result['label']} (score: {result['compound']:.3f})")
        print()
