"""LinkedIn and Indeed job scrapers using Playwright."""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

from patchright.async_api import BrowserContext, async_playwright

from config_schema import Config


@dataclass
class RawListing:
    source: str
    external_id: str
    title: str
    company: str
    location: str = ""
    url: str = ""
    description: str = ""
    salary: str = ""
    posted_at: str = ""


async def create_browser_context(headless: bool = True) -> tuple:
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=headless)
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    )
    return pw, browser, context


# ---------------------------------------------------------------------------
# Description fetchers — visit each job page to get the full text
# ---------------------------------------------------------------------------

async def _fetch_indeed_description(context: BrowserContext, url: str, sem: asyncio.Semaphore) -> str:
    async with sem:
        page = await context.new_page()
        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_selector("#jobDescriptionText", timeout=8000)
            el = await page.query_selector("#jobDescriptionText")
            return (await el.inner_text()).strip() if el else ""
        except Exception:
            return ""
        finally:
            await page.close()
            await asyncio.sleep(random.uniform(0.5, 1.2))


async def _fetch_linkedin_description(context: BrowserContext, url: str, sem: asyncio.Semaphore) -> str:
    async with sem:
        page = await context.new_page()
        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_selector(".description__text", timeout=8000)
            el = await page.query_selector(".description__text")
            return (await el.inner_text()).strip() if el else ""
        except Exception:
            return ""
        finally:
            await page.close()
            await asyncio.sleep(random.uniform(0.5, 1.2))


async def _enrich_descriptions(
    listings: list[RawListing],
    context: BrowserContext,
    concurrency: int = 4,
) -> None:
    """Fetch full descriptions for all listings in-place, with rate limiting."""
    sem = asyncio.Semaphore(concurrency)

    fetchers = {
        "indeed": _fetch_indeed_description,
        "linkedin": _fetch_linkedin_description,
    }

    tasks = []
    for listing in listings:
        fetch = fetchers.get(listing.source)
        if fetch and listing.url:
            tasks.append((listing, fetch(context, listing.url, sem)))
        else:
            tasks.append((listing, None))

    total = len([t for _, t in tasks if t is not None])
    print(f"  Fetching {total} job descriptions...", flush=True)

    done = 0
    for listing, coro in tasks:
        if coro is None:
            continue
        listing.description = await coro
        done += 1
        if done % 10 == 0 or done == total:
            print(f"  {done}/{total} descriptions fetched", flush=True)


# ---------------------------------------------------------------------------
# Card scrapers
# ---------------------------------------------------------------------------

async def scrape_indeed(
    context: BrowserContext,
    keyword: str,
    location: str,
    max_results: int = 25,
) -> list[RawListing]:
    page = await context.new_page()
    results: list[RawListing] = []

    query = keyword.replace(" ", "+")
    loc = location.replace(" ", "+")
    url = f"https://uk.indeed.com/jobs?q={query}&l={loc}&sort=date"

    try:
        await page.goto(url, timeout=30000)
        await page.wait_for_selector(".tapItem", timeout=10000)

        cards = await page.query_selector_all(".tapItem")
        for card in cards[:max_results]:
            link_el = await card.query_selector("a[id^='job_']")
            if not link_el:
                continue
            raw_id = await link_el.get_attribute("id") or ""
            jk = raw_id.removeprefix("job_")

            title_el = await card.query_selector("[id^='jobTitle']")
            company_el = await card.query_selector("[data-testid='company-name']")
            location_el = await card.query_selector("[data-testid='text-location']")
            salary_el = await card.query_selector("[data-testid='attribute_snippet_testid']")

            title = (await title_el.inner_text()).strip() if title_el else ""
            company = (await company_el.inner_text()).strip() if company_el else ""
            loc_text = (await location_el.inner_text()).strip() if location_el else ""
            salary = (await salary_el.inner_text()).strip() if salary_el else ""

            if not title or not jk:
                continue

            results.append(RawListing(
                source="indeed",
                external_id=jk,
                title=title,
                company=company,
                location=loc_text,
                salary=salary,
                url=f"https://uk.indeed.com/viewjob?jk={jk}",
            ))
    except Exception as e:
        print(f"[indeed] Error scraping '{keyword}' in '{location}': {e}")
    finally:
        await page.close()

    return results


async def scrape_linkedin(
    context: BrowserContext,
    keyword: str,
    location: str,
    max_results: int = 25,
) -> list[RawListing]:
    page = await context.new_page()
    results: list[RawListing] = []

    query = keyword.replace(" ", "%20")
    loc = location.replace(" ", "%20")
    url = f"https://www.linkedin.com/jobs/search/?keywords={query}&location={loc}&sortBy=DD"

    try:
        await page.goto(url, timeout=30000)
        await page.wait_for_selector(".job-search-card", timeout=10000)

        cards = await page.query_selector_all(".job-search-card")
        for card in cards[:max_results]:
            job_id = await card.get_attribute("data-entity-urn") or ""
            job_id = job_id.split(":")[-1]

            title_el = await card.query_selector("h3.base-search-card__title")
            company_el = await card.query_selector("h4.base-search-card__subtitle")
            location_el = await card.query_selector(".job-search-card__location")
            link_el = await card.query_selector("a.base-card__full-link")

            title = (await title_el.inner_text()).strip() if title_el else ""
            company = (await company_el.inner_text()).strip() if company_el else ""
            loc_text = (await location_el.inner_text()).strip() if location_el else ""
            href = await link_el.get_attribute("href") if link_el else ""

            if not title or not job_id:
                continue

            results.append(RawListing(
                source="linkedin",
                external_id=job_id,
                title=title,
                company=company,
                location=loc_text,
                url=href or "",
            ))
    except Exception as e:
        print(f"[linkedin] Error scraping '{keyword}' in '{location}': {e}")
    finally:
        await page.close()

    return results


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

async def run_scrapers(config: Config, context: BrowserContext) -> list[RawListing]:
    """Scrape cards from all sources, then enrich with full descriptions."""
    all_results: list[RawListing] = []
    max_per = config.scraper.max_listings_per_run

    tasks = []
    for keyword in config.search.keywords:
        for location in config.search.locations:
            if "linkedin" in config.search.sources:
                tasks.append(scrape_linkedin(context, keyword, location, max_per))
            if "indeed" in config.search.sources:
                tasks.append(scrape_indeed(context, keyword, location, max_per))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, list):
            all_results.extend(r)

    # Deduplicate by (source, external_id) before fetching descriptions
    seen: set[tuple[str, str]] = set()
    unique: list[RawListing] = []
    for l in all_results:
        key = (l.source, l.external_id)
        if key not in seen:
            seen.add(key)
            unique.append(l)

    await _enrich_descriptions(unique, context, concurrency=config.scraper.description_concurrency)
    return unique
