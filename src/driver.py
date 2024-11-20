from selenium import webdriver


__all__ = ("generate_driver",)


def _generate_options():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-dev-shm-usage")
    return options


def generate_driver():
    options = _generate_options()
    driver = webdriver.Chrome(options=options)
    return driver
