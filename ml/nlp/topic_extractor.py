"""
Ekstraksi entitas dan distribusi topik dominan dari agregasi metadata teks berita guna memetakan narasi fundamental pasar.
"""
import logging
from typing import List, Dict
from datetime import datetime, timedelta, timezone
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
from storage.db_models import get_session, NewsArticle
logger = logging.getLogger(__name__)

def extract_topics(hours: int=24, top_n: int=15) -> List[Dict]:
    session = get_session()
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        articles = session.query(NewsArticle).filter(NewsArticle.published_at >= since).all()
        if not articles:
            return []
        corpus = []
        sentiments = []
        for a in articles:
            text = f"{a.title or ''} {a.content or ''}".strip()
            if len(text) > 20:
                corpus.append(text)
                sentiments.append(a.sentiment_score or 0.0)
        if not corpus:
            return []
        vectorizer = TfidfVectorizer(stop_words='english', max_df=0.8, min_df=1, ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(corpus)
        feature_names = vectorizer.get_feature_names_out()
        avg_tfidf = np.asarray(tfidf_matrix.mean(axis=0)).ravel()
        top_indices = avg_tfidf.argsort()[-top_n:][::-1]
        results = []
        for idx in top_indices:
            word = feature_names[idx]
            weight = float(avg_tfidf[idx])
            doc_indices = tfidf_matrix[:, idx].nonzero()[0]
            if len(doc_indices) > 0:
                word_sentiments = [sentiments[i] for i in doc_indices]
                avg_sent = sum(word_sentiments) / len(word_sentiments)
            else:
                avg_sent = 0.0
            if len(word) > 2 and weight > 0:
                results.append({'topic': word, 'weight': round(weight * 100, 2), 'sentiment': round(avg_sent, 3)})
        return results
    except Exception as e:
        logger.error('topic_extraction_failed', error=str(e))
        return []
    finally:
        session.close()
