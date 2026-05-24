"""
Tests for VADER sentiment analysis.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ml.models.sentiment_vader import analyze_sentiment_vader


class TestAnalyzeSentimentVader:
    """Tests for the analyze_sentiment_vader function."""

    def test_positive_text(self):
        """Positive text should return positive label."""
        result = analyze_sentiment_vader("Bitcoin is going to the moon! Great investment!")
        assert result["label"] == "positive"
        assert result["compound"] > 0.05
        assert 0 <= result["pos"] <= 1
        assert 0 <= result["neu"] <= 1
        assert 0 <= result["neg"] <= 1

    def test_negative_text(self):
        """Negative text should return negative label."""
        result = analyze_sentiment_vader("Crypto market crash, everyone is losing money. Terrible.")
        assert result["label"] == "negative"
        assert result["compound"] < -0.05

    def test_neutral_text(self):
        """Neutral text should return neutral label."""
        result = analyze_sentiment_vader("The price is 43000 dollars today.")
        assert result["label"] == "neutral"
        assert -0.05 <= result["compound"] <= 0.05

    def test_empty_string(self):
        """Empty string should return neutral."""
        result = analyze_sentiment_vader("")
        assert result["label"] == "neutral"
        assert result["compound"] == 0.0

    def test_return_keys(self):
        """Result should contain all expected keys."""
        result = analyze_sentiment_vader("test text")
        expected_keys = {"compound", "pos", "neu", "neg", "label"}
        assert set(result.keys()) == expected_keys

    def test_compound_range(self):
        """Compound score should be between -1 and 1."""
        texts = [
            "Absolutely amazing bullish signal!!!",
            "Worst crash in history, sell everything now!!!",
            "The weather is nice today",
        ]
        for text in texts:
            result = analyze_sentiment_vader(text)
            assert -1.0 <= result["compound"] <= 1.0

    def test_long_text(self):
        """Long text should still work without errors."""
        long_text = "Bitcoin is great. " * 500
        result = analyze_sentiment_vader(long_text)
        assert result["label"] in ("positive", "negative", "neutral")

    def test_special_characters(self):
        """Text with special characters should not crash."""
        result = analyze_sentiment_vader("🚀🌕 BTC to the moon! $$$")
        assert result["label"] in ("positive", "negative", "neutral")

    def test_mixed_sentiment(self):
        """Mixed sentiment text should return a valid result."""
        result = analyze_sentiment_vader(
            "Bitcoin had a great day but Ethereum crashed badly"
        )
        # We just verify it doesn't crash and returns valid structure
        assert "compound" in result
        assert "label" in result
