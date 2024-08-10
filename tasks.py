import logging
import os
import pytz
import re
import shortuuid
import urllib
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path
from robocorp.tasks import task
from RPA.Browser.Selenium import Selenium
from RPA.Excel.Files import Files as Excel
from RPA.Robocorp.WorkItems import WorkItems

logging.basicConfig(level=logging.INFO)
OUTPUT_DIR = Path(os.getenv("ROBOT_ARTIFACTS", "output"))


class TimeUtils:
    @staticmethod
    def is_timestamp_within_last_x_months(timestamp_ms: float, X: int) -> bool:
        timestamp_dt = datetime.fromtimestamp(timestamp_ms / 1000.0, pytz.UTC)
        current_time = datetime.now(pytz.UTC)
        date_x_months_ago = current_time - relativedelta(months=X)
        return date_x_months_ago <= timestamp_dt <= current_time


class StringUtils:
    @staticmethod
    def contains_money(text: str) -> bool:
        pattern = r"(\$\d{1,3}(,\d{3})*(\.\d{1,2})?)|(\d{1,3}(,\d{3})*(\.\d{1,2})?\s?(dollars|USD|usd))"
        match = re.search(pattern, text, re.IGNORECASE)
        return bool(match)


class WorkItemManager:
    def __init__(self):
        self.library = WorkItems()
        logging.info("Initialized WorkItems library.")

    def get_variables(self) -> dict:
        self.library.get_input_work_item()
        variables = self.library.get_work_item_variables()
        logging.info("Retrieved work item variables.")
        return variables


class LATimesNewsSearch:
    def __init__(self, variables):
        self.variables = variables
        self.driver = Selenium()
        self.news = []
        logging.info("Initialized LATimesNewsSearch with given variables.")

    def open_browser(self):
        logging.info("Opening LATimes website.")
        self.driver.open_browser(
            "https://www.latimes.com/",
            service_log_path=os.devnull,
            browser="headlessfirefox",
        )

    def perform_search(self):
        logging.info(f"Performing search for phrase: '{self.variables['phrase']}'.")
        self.driver.find_element(
            "xpath://button[@data-element='search-button']"
        ).click()
        self.driver.find_element(
            "xpath://input[@data-element='search-form-input']"
        ).send_keys(self.variables["phrase"].lower())
        self.driver.find_element(
            "xpath://button[@data-element='search-submit-button']"
        ).click()
        self.driver.find_element("css:.see-all-text").click()
        # Sort news by newest
        self.driver.set_element_attribute(
            "css:.select-input > option:nth-child(2)", "selected", "selected"
        )

    def filter_category(self):
        logging.info(f"Filtering results by category: '{self.variables['category']}'.")
        categories = self.driver.find_elements(
            "css:.search-filter-menu > li > div > div.checkbox-input > label > span"
        )
        for category in categories:
            if self.variables["category"].lower() in category.text.lower():
                self.driver.find_element(category).click()
                break

    def collect_news(self):
        logging.info("Starting to collect news items.")
        within_last_x_months = True
        page = 1
        while within_last_x_months:
            logging.info(f"Processing page {page}.")
            news_timestamps = self.driver.find_elements("css:.promo-timestamp")
            titles = self.driver.find_elements("css:.promo-title")
            descriptions = self.driver.find_elements("css:.promo-description")
            images = self.driver.find_elements("css:.promo-media > a > picture > img")

            for idx, timestamp in enumerate(news_timestamps):
                timestamp_value = float(timestamp.get_attribute("data-timestamp"))
                if TimeUtils.is_timestamp_within_last_x_months(
                    timestamp_value, self.variables["last_months"]
                ):
                    self.process_news_item(
                        idx, timestamp_value, titles, descriptions, images
                    )
                else:
                    logging.info(
                        "News item is outside the specified time range. Stopping collection."
                    )
                    within_last_x_months = False
                    break
            self.driver.find_element("css:.search-results-module-next-page").click()
            page += 1

    def process_news_item(self, idx, timestamp_value, titles, descriptions, images):
        news_id = shortuuid.uuid()
        title = titles[idx].text
        description = descriptions[idx].text
        date = datetime.fromtimestamp(timestamp_value / 1000.0, pytz.UTC).strftime(
            "%Y-%m-%d"
        )
        picture_filename = f"{news_id}.jpg"
        picture_url = images[idx].get_attribute("src")

        logging.info(
            f"Processing news item {idx + 1} with ID: {news_id} and Title: '{title}'."
        )

        urllib.request.urlretrieve(picture_url, OUTPUT_DIR / picture_filename)
        logging.info(f"Image downloaded to {OUTPUT_DIR / picture_filename}.")

        search_phrase_count = title.lower().count(
            self.variables["phrase"].lower()
        ) + description.lower().count(self.variables["phrase"].lower())

        contains_money = StringUtils.contains_money(
            description
        ) or StringUtils.contains_money(title)

        self.news.append(
            {
                "title": title,
                "date": date,
                "description": description,
                "picture_filename": picture_filename,
                "search_phrase_count": search_phrase_count,
                "contains_money": contains_money,
            }
        )
        logging.info(f"News item {news_id} processed and added to the list.")

    def close_browser(self):
        logging.info("Closing the browser.")
        self.driver.close_browser()

    def save_to_excel(self):
        logging.info("Saving collected news to Excel.")
        excel = Excel()
        excel.create_workbook(OUTPUT_DIR / "news.xlsx")
        excel.append_rows_to_worksheet(
            content={
                "Title": [item["title"] for item in self.news],
                "Date": [item["date"] for item in self.news],
                "Description": [item["description"] for item in self.news],
                "Picture Filename": [item["picture_filename"] for item in self.news],
                "Search Phrase Count": [
                    item["search_phrase_count"] for item in self.news
                ],
                "Contains Money": [item["contains_money"] for item in self.news],
            },
            header=True,
        )
        excel.save_workbook()
        logging.info(f"News written to {OUTPUT_DIR / 'news.xlsx'}")


@task
def search_latimes_news():
    logging.info("Starting the LATimes news search task.")
    work_item_manager = WorkItemManager()
    variables = work_item_manager.get_variables()

    latimes_news_search = LATimesNewsSearch(variables)
    latimes_news_search.open_browser()
    latimes_news_search.perform_search()
    latimes_news_search.filter_category()
    latimes_news_search.collect_news()
    latimes_news_search.save_to_excel()
    latimes_news_search.close_browser()
    logging.info("LATimes news search task completed.")
