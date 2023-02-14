import os
import sys
import re
import asyncio

import aioconsole

from dotenv import dotenv_values

from playwright.async_api import async_playwright, Playwright
from loguru import logger

class FailedToLogin(Exception):
    pass

class PlaywrightUtils:
    def __init__(self, context=None, page=None):
        self.context = context
        self.page = page

    async def get_element(self, selector, timeout=5000, state="visible"):
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout, state=state)
            return element
        except:
            return None

    async def handle_element(self, selector, action, timeout=5000, state="visible", **params):
        element = await self.get_element(selector, timeout=timeout, state=state)
        if element:
            await getattr(element, action)(**params)
            return True

    @staticmethod
    def get_proxy(proxy):
        username, password = proxy.split("@")[0].split(":")
        return {
            "server": f"http://{proxy.split('@')[1]}",
            "username": username,
            "password": password,
        }

class AccountGrabber:
    @staticmethod
    def get_accounts():
        return [account_info.split("|") for account_info in AccountGrabber.file_to_list("accounts.txt")]

    @staticmethod
    def file_to_list(file):
        with open(file, "r") as f:
            return f.read().splitlines()

class BrowserContext:
    def __init__(self, context):
        self.context = context
        self.page = None
        self.background = None

    async def new_page(self):
        self.page = await self.context.new_page()
        return self.page

    async def get_background(self):
        self.background = self.context.service_workers[0]
        if not self.background:
            self.background = await self.context.wait_for_event("serviceworker")
        return self.background

    async def close(self):
        await self.context.close()

class TwoCaptcha:
    def __init__(self, context):
        self.context = context
        self.background = None
        self.page = None

    async def get_background(self):
        self.background = await self.get_2captcha_popup()
        if not self.background:
            self.background = await self.context.wait_for_event("serviceworker")
        return self.background

    async def get_2captcha_popup(self):  # seems not working
        while True:
            # await asyncio.sleep(0.1)  #need to switch on############################################################
            if len(self.context.service_workers) > 0:
                print("Found captcha popup")
                return self.context.service_workers[0]
            print("Waiting for captcha popup")
            await asyncio.sleep(0.1)

    async def get_page(self):
        self.page = await self.context.new_page()
        return self.page

    async def get_extension_id(self):
        return self.background.url.split("/")[2]

    async def open_options_page(self):
        extension_id = await self.get_extension_id()
        await self.page.goto(f"chrome-extension://{extension_id}/options/options.html", wait_until="load")

    async def switch_on_auto_submit(self):
        await self.page.locator('input[id="autoSubmitForms"]').check()
        await self.page.locator('input[id="autoSolveRecaptchaV2"]').check()
        await self.page.locator('input[id="autoSolveHCaptcha"]').check()

    async def fill_api_key(self, api_key):
        await self.page.locator("input[name=apiKey]").fill(api_key)

    async def click_connect(self):
        await self.page.locator('button[id="connect"]').click()
        await self.page.wait_for_load_state("load")

class DropppIO(PlaywrightUtils):
    WALLET_SELECTOR = "div[class^=styles_lblAddress]"

    def __init__(self, page):
        super().__init__(page=page)

    async def is_logged_in(self, timeout=5000):
        return await self.get_element(DropppIO.WALLET_SELECTOR, timeout=timeout)

    async def login(self, email, password): # styles_lblAddress
        await self.handle_element("div[class^=styles_linkSignIn]", "click")
        for _ in range(3):
            try:
                await self.fill_login_form(email, password)
            except Exception as e:
                ...
                # print(e)
                # print("Login fill failed")  # not bad sometimes not all fields are required
            finally:
                # print("Login passed")
                if await self.is_logged_in(timeout=10000):
                    break
        if not await self.is_logged_in(timeout=20000):
            assert False, "Failed to login"

    async def fill_login_form(self, email: str, password: str, timeout=10000):
        await self.handle_element("input[name=email]", "fill", timeout=timeout, value=email)

        await self.handle_element("form button", "click", timeout=timeout)

        await self.handle_element("input[name=password]", "fill", timeout=timeout, value=password)

        await self.handle_element("form button", "click", timeout=timeout)

class QueuePage(PlaywrightUtils):
    QUEUE_BTN_SELECTOR = ".stack__packs__content a.button--black:not(.disabled)"

    max_long_queue: int = int(dotenv_values("config.txt")["max_long_queue"])

    def __init__(self, page):
        super().__init__(page=page)

    async def wait_for_queue_btn(self) -> None:  # reload page every 2 minutes to wait for queue button
        while not await self.get_element(QueuePage.QUEUE_BTN_SELECTOR, timeout=2 * 60 * 1000):  # 2 minutes
            print("Waiting for queue button")
            await self.page.reload()
        print("Queue button found")

    async def click_queue_btn(self):
        queue_btn = await self.get_element(QueuePage.QUEUE_BTN_SELECTOR, timeout=0)
        redirect_btn_link = await queue_btn.get_attribute("href")
        await self.page.goto(redirect_btn_link)#, wait_until="load", timeout=40000)

    async def bypass_captcha(self):
        droppp_captcha = DropppCaptcha(self.page)
        await droppp_captcha.handle_droppp_captcha()

    async def handle_queue(self, profile_id: int):
        # await self.page.goto(f"file:///C:/Users/Denys/Downloads/Queue-it_.html", wait_until="domcontentloaded")
        await self.wait_for_queue_page_load()
        # await asyncio.sleep(20)
        print("Queue page loaded")
        status = await self.queue_page_status_checker(timeout=900, delay=5)  # 15 minutes wait
        if status is None:
            print("Can't parse queue page timer")
        else:
            logger.success(f"{profile_id}. Queue page successfully handled")

    async def queue_page_status_checker(self, timeout: int, delay: int) -> bool:
        for _ in range(timeout // delay):
            left_wait_time = await self.get_left_wait_time_regex()  # await self.get_left_wait_time()
            if left_wait_time is not None:
                print(f"Left wait time: {left_wait_time} seconds")
                return await self.close_long_wait_queue(left_wait_time, QueuePage.max_long_queue * 60)  # if > some minutes: close
            print("Can't parse left wait time")
            await asyncio.sleep(delay)

    async def wait_for_queue_page_load(self):
        print("Waiting for queue page load")
        await self.get_element("#MainPart_pProgressbarBox_Holder_Larger", timeout=0)

    async def get_left_wait_time(self):
        progress_info_el = await self.get_element("span#MainPart_lbWhichIsIn", timeout=5000)
        # print(f"1Progress info el: {progress_info_el}")
        if not progress_info_el:
            progress_info_el = await self.get_element("div#defaultCountdown", timeout=5000)

        progress_info = await progress_info_el.text_content()
        raw_left_wait_time = progress_info.strip()
        # print(f"Raw left wait time: {raw_left_wait_time}")
        time_number, time_type = raw_left_wait_time.split(" ")[:2]

        left_wait_time = QueuePage.convert_time_seconds(time_number.strip(), time_type.strip().lower())
        # print(f"Left wait time: {left_wait_time} seconds")
        return left_wait_time

    @staticmethod
    def convert_time_seconds(time_number, time_type):
        time_number = int(time_number)
        if time_type.startswith("second"):
            return time_number
        elif time_type.startswith("minute"):
            return time_number * 60
        elif time_type.startswith("hour"):
            return time_number * 60 * 60
        return 0

    async def get_left_wait_time_regex(self):  # test
        progress_info_el = await self.get_element("#MainPart_divProgressbarBox_Holder", timeout=0)
        progress_info = await progress_info_el.inner_text()
        # print(f"Progress info: {progress_info}")

        if "less" in progress_info:  # less than a minute
            return 0
        elif "more" in progress_info:  # more than an hour
            return 99999

        left_wait_time = QueuePage.extract_time(progress_info.lower())
        # print(f"Left wait time: {left_wait_time} seconds")

        if not left_wait_time:  # if not found
             return None

        # convert to seconds
        left_wait_time_seconds = QueuePage.convert_time(left_wait_time)
        # print(f"Left wait time: {left_wait_time_seconds} seconds")
        return left_wait_time_seconds

    @staticmethod
    def is_time_extracted(left_wait_time):
        return left_wait_time

    @staticmethod
    def extract_time(text):  # test
        result = {}

        time_pattern = re.compile(r'(\d+) hours?|(\d+) minutes?|(\d+) seconds?')
        for match in time_pattern.finditer(text):
            if match.group(1):
                result['hours'] = int(match.group(1))
            elif match.group(2):
                result['minutes'] = int(match.group(2))
            elif match.group(3):
                result['seconds'] = int(match.group(3))
        return result

    @staticmethod
    def convert_time(left_wait_time: dict):  # test
        seconds = 0
        for time_type, time_value in left_wait_time.items():
            if time_type == "hours":
                seconds += time_value * 60 * 60
            elif time_type == "minutes":
                seconds += time_value * 60
            elif time_type == "seconds":
                seconds += time_value
        return seconds

    async def close_long_wait_queue(self, left_wait_time: int, max_wait_time: int):
        if left_wait_time > max_wait_time:
            await self.page.close()
            return True
        return False

class DropppCaptcha(PlaywrightUtils):
    def __init__(self, page):
        super().__init__(page=page)

    async def handle_droppp_captcha(self):
        if await self.is_droppp_captcha_on():
            await self.bypass_droppp_captcha()

    async def is_droppp_captcha_on(self):
        return await self.get_element("div[class^=styles_formContainer]", timeout=60000)

    async def bypass_droppp_captcha(self):
        answer = 1  # await self.get_droppp_captcha_answer()
        await self.page.locator("input[inputmode=numeric]").fill(str(answer))
        await self.handle_element("button", "click")

    async def get_droppp_captcha_answer(self):
        captcha_question = await (await self.get_element("div[class^=styles_description]")).text_content()

        first_number = captcha_question.split("What does ")[1].split(" ")[0]
        second_number = captcha_question.split(" equal?", 1)[0].split(" ")[-1]
        operation = captcha_question.split(" equal?", 1)[0].split(" ")[-2]

        answer = 0
        if operation == "plus":
            answer = int(first_number) + int(second_number)
        elif operation == "minus":
            answer = int(first_number) - int(second_number)

        # print(f"Answer: {answer}")

        return answer

class FunkoBot:
    TWOCAPTCHA_PATH = os.path.abspath("./2captcha-chrome")
    BASE_PROFILE_DIR = os.path.abspath("./profiles")
    TWOCAPTCHA_API_KEY = ""

    sale_link = dotenv_values("config.txt")["sale_link"]

    def __init__(self):
        self.accounts = AccountGrabber.get_accounts()

        self.playwright = None

    async def start(self):
        await self.handle_accounts()

        logger.info("Finished!")

    async def handle_accounts(self):
        accounts_task_manager = []
        async with async_playwright() as self.playwright:
            for profile_id, account in enumerate(self.accounts):
                accounts_task_manager.append(await self.handle_account(profile_id+1, account))

            print(accounts_task_manager)
            await asyncio.gather(*accounts_task_manager)
            print("Done")

            await FunkoBot.ask_to_exit()

    async def get_profile_worker(self, account):
        return

    async def handle_account(self, profile_id, account):
        logger.info(f"{profile_id}. {account[0]} - starting...")
        funko_profile = None
        # try:
        funko_profile = FunkoProfile(profile_id, *account)
        await funko_profile.get_context(self.playwright)
        await funko_profile.adjust_twocaptcha_extension()
        await funko_profile.visit_funko()
        await asyncio.sleep(1)
        return asyncio.ensure_future(funko_profile.join_queue())
        # except FailedToLogin as e:
        #     logger.error(f"{account[0]} - failed to login")
        # except Exception as e:
        #     logger.error(f"{account[0]} - have unhandled error")
        #     await funko_profile.close()
        #     await asyncio.sleep(3)
        # return a coroutine or an awaitable else will be error
        return asyncio.sleep(0)

    @staticmethod
    async def ask_to_exit():
        while True:
            is_exit = await aioconsole.ainput('To exit press y: ')
            if is_exit.lower() == "y":
                return

class FunkoProfile:
    def __init__(self, profile_id: int, email, password, proxy=None):
        self.profile_id = profile_id
        self.email = email
        self.password = password
        self.proxy = proxy and PlaywrightUtils.get_proxy(proxy)

        self.profile_location = f"{FunkoBot.BASE_PROFILE_DIR}/{email}"
        self.context = None
        self.page = None

    async def get_context(self, playwright: Playwright, headless: bool = False) -> None:
        self.context = await playwright.chromium.launch_persistent_context(
            self.profile_location,
            # channel="chrome",  # better use chromium
            headless=headless,
            ignore_default_args=["--enable-automation"],  # '--enable-automation' - off some functions
            args=[
                f"--disable-extensions-except={FunkoBot.TWOCAPTCHA_PATH}",
                f"--load-extension={FunkoBot.TWOCAPTCHA_PATH}",
                '--start-maximized',
                "--disable-blink-features=AutomationControlled"
            ],
            chromium_sandbox=True,
            no_viewport=True,
            proxy=self.proxy,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
                       " Chrome/109.0.0.0 Safari/537.36"
        )

    async def adjust_twocaptcha_extension(self) -> None:
        two_captcha = TwoCaptcha(self.context)
        await two_captcha.get_background()
        self.page = await two_captcha.get_page()
        await two_captcha.open_options_page()
        await two_captcha.switch_on_auto_submit()
        await two_captcha.fill_api_key(FunkoBot.TWOCAPTCHA_API_KEY)
        await two_captcha.click_connect()

    async def visit_funko(self) -> bool:
        await self.handle_extra_pages()
        await self.page.goto(FunkoBot.sale_link, wait_until="load")
        await self.page.wait_for_load_state("load")  # not sure if needed
        return await self.handle_droppp_io()

    async def handle_extra_pages(self) -> None:
        if len(self.context.pages) > 1:
            await self.context.pages[0].close()

    async def handle_droppp_io(self) -> bool:
        return await self.enter_account()

    async def enter_account(self) -> bool:
        droppp_io = DropppIO(self.page)
        if not await droppp_io.is_logged_in():
            for _ in range(2):
                try:
                    await droppp_io.login(self.email, self.password)
                    logger.success(f"{self.profile_id}. Successfully logged in {self.email}!")
                    return True
                except Exception as e:
                    logger.error(f"{self.profile_id}. Failed to login {self.email}! Retrying...")
                    await self.page.goto(FunkoBot.sale_link, wait_until="load")
                    await self.page.wait_for_timeout(5000)
            raise FailedToLogin(f"{self.profile_id}. Failed to login {self.email}!")
        return True

    async def join_queue(self) -> None:
        queue = QueuePage(page=self.page)
        await queue.wait_for_queue_btn()
        await queue.click_queue_btn()
        # await self.page.goto("file:///C:/Users/Denys/Downloads/Reserve%20Packs%20-%20Droppp.html?") #######################
        await queue.bypass_captcha()
        await queue.handle_queue(self.profile_id)

    async def close(self) -> None:
        try:
            await self.context.close()
        except Exception as e:
            logger.error(f"Failed to close context {self.email}! {e}")

async def main() -> None:
    await FunkoBot().start()


if __name__ == "__main__":
    print("Main <crypto/> moves: https://t.me/+tdC-PXRzhnczNDli")
    logger.remove(0)

    logger.add("out.log")
    logger.add(sys.stdout, colorize=True,
               format="<green>{time:HH:mm:ss.SSS}</green> <blue>{level}</blue> <level>{message}</level>")

    asyncio.run(main())
