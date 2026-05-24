"""
YARS – Yet Another Reddit Scraper (without API keys).

Scrape search results, posts, comments, user data, and subreddit feeds
from Reddit using its public .json endpoints.

Source: https://github.com/datavorous/yars
License: MIT
"""
from __future__ import annotations

import logging
import random
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .sessions import RandomUserAgentSession

logger = logging.getLogger(__name__)


class YARS:
    """Reddit scraper using public .json endpoints – no API keys needed."""

    __slots__ = ("session", "proxy", "timeout")

    def __init__(self, proxy=None, timeout=10, random_user_agent=True):
        self.session = RandomUserAgentSession() if random_user_agent else requests.Session()
        self.proxy = proxy
        self.timeout = timeout

        retries = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})

    # ── Search ────────────────────────────────────────────────────────

    def _handle_search(self, url, params, after=None, before=None):
        if after:
            params["after"] = after
        if before:
            params["before"] = before

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            logger.info("Search request successful")
        except Exception as e:
            logger.warning("Search request failed: %s", e)
            return []

        data = response.json()
        results = []
        for post in data.get("data", {}).get("children", []):
            post_data = post["data"]
            results.append({
                "title": post_data["title"],
                "link": f"https://www.reddit.com{post_data['permalink']}",
                "description": post_data.get("selftext", "")[:269],
            })
        logger.info("Search returned %d results", len(results))
        return results

    def search_reddit(self, query, limit=10, after=None, before=None):
        """Search all of Reddit for posts matching *query*."""
        url = "https://www.reddit.com/search.json"
        params = {"q": query, "limit": limit, "sort": "relevance", "type": "link"}
        return self._handle_search(url, params, after, before)

    def search_subreddit(self, subreddit, query, limit=10, after=None, before=None, sort="relevance"):
        """Search within a specific subreddit."""
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {"q": query, "limit": limit, "sort": sort, "type": "link", "restrict_sr": "on"}
        return self._handle_search(url, params, after, before)

    # ── Post Details ──────────────────────────────────────────────────

    def scrape_post_details(self, permalink):
        """Scrape a single post's details and comments by its permalink."""
        url = f"https://www.reddit.com{permalink}.json"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            logger.info("Post details request successful: %s", url)
        except Exception as e:
            logger.warning("Post details request failed: %s", e)
            return None

        post_data = response.json()
        if not isinstance(post_data, list) or len(post_data) < 2:
            logger.warning("Unexpected post data structure")
            return None

        main_post = post_data[0]["data"]["children"][0]["data"]
        comments = self._extract_comments(post_data[1]["data"]["children"])
        logger.info("Successfully scraped post: %s", main_post["title"])
        return {
            "title": main_post["title"],
            "body": main_post.get("selftext", ""),
            "comments": comments,
        }

    def _extract_comments(self, comments):
        extracted = []
        for comment in comments:
            if isinstance(comment, dict) and comment.get("kind") == "t1":
                cdata = comment.get("data", {})
                entry = {
                    "author": cdata.get("author", ""),
                    "body": cdata.get("body", ""),
                    "score": cdata.get("score", ""),
                    "replies": [],
                }
                replies = cdata.get("replies", "")
                if isinstance(replies, dict):
                    entry["replies"] = self._extract_comments(
                        replies.get("data", {}).get("children", [])
                    )
                extracted.append(entry)
        return extracted

    # ── User Data ─────────────────────────────────────────────────────

    def scrape_user_data(self, username, limit=10):
        """Fetch a user's recent posts and comments."""
        logger.info("Scraping user data for %s (limit=%d)", username, limit)
        base_url = f"https://www.reddit.com/user/{username}/.json"
        params = {"limit": limit, "after": None}
        all_items, count = [], 0

        while count < limit:
            try:
                response = self.session.get(base_url, params=params, timeout=self.timeout)
                response.raise_for_status()
            except Exception as e:
                logger.warning("User data request failed: %s", e)
                break

            try:
                data = response.json()
            except ValueError:
                logger.warning("Failed to parse JSON for user %s", username)
                break

            items = data.get("data", {}).get("children", [])
            if not items:
                break

            for item in items:
                kind = item["kind"]
                idata = item["data"]
                if kind == "t3":
                    all_items.append({
                        "type": "post",
                        "title": idata.get("title", ""),
                        "subreddit": idata.get("subreddit", ""),
                        "url": f"https://www.reddit.com{idata.get('permalink', '')}",
                        "created_utc": idata.get("created_utc", ""),
                    })
                elif kind == "t1":
                    all_items.append({
                        "type": "comment",
                        "subreddit": idata.get("subreddit", ""),
                        "body": idata.get("body", ""),
                        "created_utc": idata.get("created_utc", ""),
                        "url": f"https://www.reddit.com{idata.get('permalink', '')}",
                    })
                count += 1
                if count >= limit:
                    break

            params["after"] = data["data"].get("after")
            if not params["after"]:
                break
            time.sleep(random.uniform(1, 2))

        logger.info("Scraped %d items for user %s", len(all_items), username)
        return all_items

    # ── Subreddit Posts ───────────────────────────────────────────────

    def fetch_subreddit_posts(self, subreddit, limit=10, category="hot", time_filter="all"):
        """
        Fetch posts from a subreddit.

        Parameters
        ----------
        subreddit : str
            Name of the subreddit (without ``r/``).
        limit : int
            Maximum number of posts to fetch.
        category : str
            One of ``hot``, ``top``, ``new``.
        time_filter : str
            Time window for ``top`` — ``hour``, ``day``, ``week``, ``month``, ``year``, ``all``.
        """
        logger.info("Fetching r/%s posts (limit=%d, category=%s)", subreddit, limit, category)
        if category not in ("hot", "top", "new"):
            raise ValueError("category must be 'hot', 'top', or 'new'")

        batch_size = min(100, limit)
        total_fetched = 0
        after = None
        all_posts = []

        while total_fetched < limit:
            url = f"https://www.reddit.com/r/{subreddit}/{category}.json"
            params = {
                "limit": batch_size,
                "after": after,
                "raw_json": 1,
                "t": time_filter,
            }

            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
            except Exception as e:
                logger.warning("Subreddit fetch failed for r/%s: %s", subreddit, e)
                break

            data = response.json()
            posts = data.get("data", {}).get("children", [])
            if not posts:
                break

            for post in posts:
                pd = post["data"]
                post_info = {
                    "title": pd["title"],
                    "author": pd.get("author", "[deleted]"),
                    "selftext": pd.get("selftext", ""),
                    "permalink": pd["permalink"],
                    "score": pd["score"],
                    "num_comments": pd["num_comments"],
                    "created_utc": pd["created_utc"],
                    "subreddit": pd.get("subreddit", subreddit),
                    "id": pd.get("id", ""),
                }
                # Optional image data
                if pd.get("post_hint") == "image" and "url" in pd:
                    post_info["image_url"] = pd["url"]
                elif "preview" in pd and "images" in pd["preview"]:
                    post_info["image_url"] = pd["preview"]["images"][0]["source"]["url"]
                if "thumbnail" in pd and pd["thumbnail"] not in ("self", "default", "nsfw", ""):
                    post_info["thumbnail_url"] = pd["thumbnail"]

                all_posts.append(post_info)
                total_fetched += 1
                if total_fetched >= limit:
                    break

            after = data["data"].get("after")
            if not after:
                break
            time.sleep(random.uniform(1, 2))

        logger.info("Fetched %d posts from r/%s", len(all_posts), subreddit)
        return all_posts
