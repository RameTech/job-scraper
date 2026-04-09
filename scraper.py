"""LinkedIn and Indeed job scrapers using Playwright."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import AsyncGenerator

from patchright.async_api import BrowserContext, Page, async_playwright

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
    """Start Playwright and return (playwright, browser, context)."""
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


async def scrape_indeed(
    context: BrowserContext,
    keyword: str,
    location: str,
    max_results: int = 25,
) -> list[RawListing]:
    """Scrape Indeed for job listings."""
    page = await context.new_page()
    results: list[RawListing] = []

    query = keyword.replace(" ", "+")
    loc = location.replace(" ", "+")
    url = f"https://www.indeed.com/jobs?q={query}&l={loc}&sort=date"

    try:
        await page.goto(url, timeout=30000)
        await page.wait_for_selector("[data-jk]", timeout=10000)

        cards = await page.query_selector_all("[data-jk]")
        for card in cards[:max_results]:
            jk = await card.get_attribute("data-jk") or ""
            title_el = await card.query_selector("h2 a span")
            company_el = await card.query_selector("[data-testid='company-name']")
            location_el = await card.query_selector("[data-testid='text-location']")

            title = (await title_el.inner_text()).strip() if title_el else ""
            company = (await company_el.inner_text()).strip() if company_el else ""
            loc_text = (await location_el.inner_text()).strip() if location_el else ""

            if not title or not jk:
                continue

            results.append(
                RawListing(
                    source="indeed",
                    external_id=jk,
                    title=title,
                    company=company,
                    location=loc_text,
                    url=f"https://www.indeed.com/viewjob?jk={jk}",
                )
            )
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
    """Scrape LinkedIn Jobs (public, no auth required for basic listings)."""
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

            results.append(
                RawListing(
                    source="linkedin",
                    external_id=job_id,
                    title=title,
                    company=company,
                    location=loc_text,
                    url=href or "",
                )
            )
    except Exception as e:
        print(f"[linkedin] Error scraping '{keyword}' in '{location}': {e}")
    finally:
        await page.close()

    return results


async def run_scrapers(config: Config, context: BrowserContext) -> list[RawListing]:
    """Run all configured scrapers and return combined results."""
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

    return all_results
