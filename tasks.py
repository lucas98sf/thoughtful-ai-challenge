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


def is_timestamp_within_last_x_months(timestamp_ms: float, X: int) -> bool:
    timestamp_dt = datetime.fromtimestamp(timestamp_ms / 1000.0, pytz.UTC)
    current_time = datetime.now(pytz.UTC)
    date_x_months_ago = current_time - relativedelta(months=X)
    is_within_last_x_months = date_x_months_ago <= timestamp_dt <= current_time
    return is_within_last_x_months


def str_contains_money(str: str) -> bool:
    pattern = r"(\$\d{1,3}(,\d{3})*(\.\d{1,2})?)|(\d{1,3}(,\d{3})*(\.\d{1,2})?\s?(dollars|USD|usd))"
    match = re.search(pattern, str, re.IGNORECASE)
    return bool(match)


def get_workitem_variables() -> dict:
    library = WorkItems()
    library.get_input_work_item()
    variables = library.get_work_item_variables()
    return variables


@task
def search_latimes_news():
    driver = Selenium()

    variables = get_workitem_variables()

    driver.open_browser(
        "https://www.latimes.com/",
        service_log_path=os.devnull,
        browser="headlessfirefox",
    )
    driver.find_element("xpath://button[@data-element='search-button']").click()
    driver.find_element("xpath://input[@data-element='search-form-input']").send_keys(
        variables["phrase"].lower()
    )
    driver.find_element("xpath://button[@data-element='search-submit-button']").click()
    driver.find_element("css:.see-all-text").click()

    # sort by newest
    driver.set_element_attribute(
        "css:.select-input > option:nth-child(2)", "selected", "selected"
    )

    categories = driver.find_elements(
        "css:.search-filter-menu > li > div > div.checkbox-input > label > span"
    )
    for category in categories:
        if variables["category"].lower() in category.text.lower():
            driver.find_element(category).click()
            # logging.info(f"{category.text} selected")
            break

    if not (OUTPUT_DIR / "images").exists():
        os.makedirs(OUTPUT_DIR / "images")
    else:
        # clear images folder
        for file in os.listdir(OUTPUT_DIR / "images"):
            os.remove(OUTPUT_DIR / "images" / file)

    news = []
    within_last_x_months = True
    page = 1
    news_timestamps = driver.find_elements("css:.promo-timestamp")
    while within_last_x_months:
        for idx, timestamp in enumerate(news_timestamps):
            timestamp_value = float(timestamp.get_attribute("data-timestamp"))
            titles = driver.find_elements("css:.promo-title")
            descriptions = driver.find_elements("css:.promo-description")
            images = driver.find_elements("css:.promo-media > a > picture > img")
            if is_timestamp_within_last_x_months(
                timestamp_value, variables["last_months"]
            ):
                news_id = shortuuid.uuid()
                title = titles[idx].text

                logging.info(
                    f"Processing news page {page}, item {idx + 1} with ID: {news_id} and Title: '{title}'"
                )

                description = descriptions[idx].text

                date = datetime.fromtimestamp(
                    timestamp_value / 1000.0, pytz.UTC
                ).strftime("%Y-%m-%d")

                picture_filename = f"{news_id}.jpg"
                picture_url = images[idx].get_attribute("src")
                # download image
                urllib.request.urlretrieve(
                    picture_url, OUTPUT_DIR / "images" / picture_filename
                )

                search_phrase_count = title.lower().count(
                    variables["phrase"].lower()
                ) + description.lower().count(variables["phrase"].lower())

                contains_money = str_contains_money(description) or str_contains_money(
                    title
                )

                news.append(
                    {
                        "title": title,
                        "date": date,
                        "description": description,
                        "picture_filename": picture_filename,
                        "search_phrase_count": search_phrase_count,
                        "contains_money": contains_money,
                    }
                )
            else:
                within_last_x_months = False
                break
        driver.find_element("css:.search-results-module-next-page").click()
        page += 1
        news_timestamps = driver.find_elements("css:.promo-timestamp")

    excel = Excel()
    excel.create_workbook(OUTPUT_DIR / "news.xlsx")
    excel.append_rows_to_worksheet(
        content={
            "Title": [item["title"] for item in news],
            "Date": [item["date"] for item in news],
            "Description": [item["description"] for item in news],
            "Picture Filename": [item["picture_filename"] for item in news],
            "Search Phrase Count": [item["search_phrase_count"] for item in news],
            "Contains Money": [item["contains_money"] for item in news],
        },
        header=True,
    )
    excel.save_workbook()
    logging.info(f"News written to {OUTPUT_DIR / 'news.xlsx'}")
    driver.close_browser()
