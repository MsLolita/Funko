import asyncio
from playwright.async_api import async_playwright
import os
import sys

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

    async def handle_element(self, selector, action, timeout=5000, state="visible"):
        element = await self.get_element(selector, timeout=timeout, state=state)
        if element:
            await getattr(element, action)()
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
        await asyncio.sleep(1)
        self.background = self.context.service_workers[0]
        if not self.background:
            self.background = await self.context.wait_for_event("serviceworker")
        return self.background

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
        await self.page.locator("input[name=email]").fill(email)
        if await self.is_logged_in(3000):
            return

        await self.page.locator("form button").click()
        if await self.is_logged_in(3000):
            return

        await self.page.locator("input[name=password]").fill(password)
        if await self.is_logged_in(3000):
            return

        await self.page.locator("form button").click()
        if not await self.is_logged_in(timeout=20000):
            assert False, "Failed to login"

class QueuePage(PlaywrightUtils):
    def __init__(self, page):
        super().__init__(page=page)

    async def click_queue_btn(self):
        queue_btn = await self.get_element("a.collection__header__button", timeout=0)
        redirect_btn_link = await queue_btn.get_attribute("href")
        await self.page.goto(redirect_btn_link)#, wait_until="load", timeout=40000)

    async def bypass_captcha(self):
        droppp_captcha = DropppCaptcha(self.page)
        await droppp_captcha.handle_droppp_captcha()

    async def handle_queue(self):
        await self.page.goto("file:///C:/Users/Denys/Downloads/Queue-it.html", wait_until="domcontentloaded")
        await self.wait_for_queue_page_load()
        print("Queue page loaded")
        left_wait_time = await self.get_left_wait_time()
        print(f"Left wait time: {left_wait_time} seconds")
        await self.close_long_wait_queue(left_wait_time, 30 * 60)  # if > 30 minutes: close

    async def wait_for_queue_page_load(self):
        print("Waiting for queue page load")
        await self.get_element("#MainPart_divProgressbarBox_Holder", timeout=0)

    async def get_left_wait_time(self):
        progress_info_el = await self.get_element("span#MainPart_lbWhichIsIn", timeout=5000)
        print(f"1Progress info el: {progress_info_el}")
        if not progress_info_el:
            progress_info_el = await self.get_element("div#defaultCountdown", timeout=5000)

        progress_info = await progress_info_el.text_content()
        raw_left_wait_time = progress_info.strip()
        print(f"Raw left wait time: {raw_left_wait_time}")
        time_number, time_type = raw_left_wait_time.split(" ")[:2]

        left_wait_time = QueuePage.convert_time(time_number.strip(), time_type.strip().lower())
        print(f"Left wait time: {left_wait_time} seconds")
        return left_wait_time

    @staticmethod
    def convert_time(time_number, time_type):
        time_number = int(time_number)
        if time_type.startswith("second"):
            return time_number
        elif time_type.startswith("minute"):
            return time_number * 60
        elif time_type.startswith("hour"):
            return time_number * 60 * 60

    async def close_long_wait_queue(self, left_wait_time: int, max_wait_time: int):
        if left_wait_time > max_wait_time:
            await self.page.close()

class DropppCaptcha(PlaywrightUtils):
    def __init__(self, page):
        super().__init__(page=page)

    async def handle_droppp_captcha(self):
        if await self.is_droppp_captcha_on():
            await self.bypass_droppp_captcha()

    async def is_droppp_captcha_on(self):
        return await self.get_element("div[class^=styles_formContainer]", timeout=30000)

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
    TWOCAPTCHA_API_KEY = "23086f2c5302c5d3c0e6e950fa8d1227"

    sale_link = None

    @staticmethod
    async def start():
        FunkoBot.sale_link = FunkoBot.ask_for_funko_sale_link()

        accounts = AccountGrabber.get_accounts()
        unsuccessful = []
        async with async_playwright() as playwright:
            for account in accounts:
                result = await FunkoBot.handle_account(account, playwright)
                if result:
                    logger.success(f"Successfully logged in to {account[0]}")
                else:
                    unsuccessful.append(account[0])

            if unsuccessful:
                logger.info(f"Failed to login to the following accounts: {unsuccessful}")
            else:
                logger.success("All accounts logged in successfully!")

            FunkoBot.ask_to_exit()
        logger.info("Finished!")

    @staticmethod
    async def handle_account(account, playwright):
                funko_profile = FunkoProfile(*account)
        # for _ in range(2):
        #     try:
                await funko_profile.get_context(playwright)
                await funko_profile.adjust_twocaptcha_extension()
                await funko_profile.visit_funko()
                await funko_profile.join_queue()
            # except FailedToLogin as e:
            #     logger.error(f"{account[0]} - failed to login. Trying again...")
            # except Exception as e:
            #     logger.error(f"{account[0]} - have unhandled error. Trying again...")
            #     await funko_profile.close()
            #     await asyncio.sleep(3)

    @staticmethod
    def ask_for_funko_sale_link():
        return 'https://digital.funko.com/drop/105/dc-teen-titans-go-series-1/'  # input("Enter a link to the Funko sale: ")

    @staticmethod
    def ask_to_exit():
        while True:
            is_exit = input("To exit press y: ")
            if is_exit.lower() == "y":
                return

class FunkoProfile:
    def __init__(self, email, password, proxy=None):
        self.email = email
        self.password = password
        self.proxy = proxy and PlaywrightUtils.get_proxy(proxy)

        self.profile_location = f"{FunkoBot.BASE_PROFILE_DIR}/{email}"
        self.context = None
        self.page = None

    async def get_context(self, playwright, headless=False):
        self.context = await playwright.chromium.launch_persistent_context(
            self.profile_location,
            headless=headless,
            args=[
                f"--disable-extensions-except={FunkoBot.TWOCAPTCHA_PATH}",
                f"--load-extension={FunkoBot.TWOCAPTCHA_PATH}",
                '--start-maximized',
                '--no-sandbox',
            ],
            ignore_default_args=["--enable-automation", "--no-startup-window"],  # --enable-automation off some functions
            no_viewport=True,
            proxy=self.proxy,
        )

    async def adjust_twocaptcha_extension(self):
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
        return await self.handle_droppp_io()

    async def handle_extra_pages(self):
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
                    logger.success(f"Successfully logged in {self.email}!")
                    return True
                except Exception as e:
                    logger.error(f"Failed to login {self.email}! Retrying...")
                    await self.page.goto(FunkoBot.sale_link, wait_until="load")
                    await self.page.wait_for_timeout(5000)
            raise FailedToLogin(f"Failed to login {self.email}!")
        return True

    async def join_queue(self):
        queue = QueuePage(page=self.page)
        await queue.click_queue_btn()
        # await queue.bypass_captcha()
        await queue.handle_queue()

    async def close(self):
        try:
            await self.context.close()
        except Exception as e:
            logger.error(f"Failed to close context {self.email}! {e}")

async def main():
    await FunkoBot.start()


if __name__ == "__main__":
    print("All crypto moves: @web3enjoyer_club")
    logger.remove(0)

    logger.add("out.log")
    logger.add(sys.stdout, colorize=True,
               format="<green>{time:HH:mm:ss.SSS}</green> <blue>{level}</blue> <level>{message}</level>")

    asyncio.run(main())