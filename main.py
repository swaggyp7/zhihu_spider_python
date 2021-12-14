# This is a sample Python script.
import csv
import json
import threading
import time
import re

import requests
import xlsxwriter
from DecryptLogin import login
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys


# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.
class Zhihu:
    def __init__(self, is_do_login):
        self.driver = webdriver.Chrome()
        self.login_session = None
        self.login_infos = None
        self.domain = 'https://www.zhihu.com/'
        self.is_do_login = is_do_login
        self.is_login = False

    def do_login(self):
        lg = login.Login()
        infos, session = lg.zhihu()
        self.login_infos = infos
        self.login_session = session
        print(f'登录成功：, {infos}')  # Press ⌘F8 to toggle the breakpoint.

    def close_login_modal(self):
        close_btn = self.driver.find_element_by_xpath("//button[@class='Button Modal-closeButton Button--plain']")
        close_btn.click()

    def is_element_exist(self, xpath):
        flag = True
        browser = self.driver
        try:
            ele = browser.find_element_by_xpath(xpath)
            return ele
        except:
            flag = False
            return flag


class People(Zhihu):
    # 回答
    answers = []
    # 想法
    thinks = []
    # 点赞
    likes = []

    def __init__(self, is_do_login):
        super(People, self).__init__(is_do_login)
        self.people_url = 'people/'
        self.url = self.domain + self.people_url
        self.page_count = 1
        self.article_count = 0

    def get_user_info(self, user_id, max_page=1):
        url = self.url + user_id
        self.driver.get(url)
        if self.is_login is False:
            time.sleep(2)
            self.close_login_modal()
        self.__open_user_details()
        # 双线程，一个线程翻页，一个线程找文章
        thread_load_page = threading.Thread(target=self.__load_all_page, args=(max_page,))
        thread_open_article = threading.Thread(target=self.__open_all_article)
        thread_load_page.start()
        thread_open_article.start()
        thread_open_article.join()
        user_dic = self.__get_info()
        user_dic['id'] = user_id
        user_xlsx = xlsxwriter.Workbook(f"{user_id}.xlsx")
        sht_user = user_xlsx.add_worksheet("基本信息")
        for i, key in enumerate(user_dic):
            sht_user.write_row(f'A{i + 1}', [key, user_dic[key]])
            # if key == 'avatar':
            #     sht_user.insert_image(i, 1, user_dic[key], {'x_scale': 0.1, 'y_scale': 0.1})
        read_threads = [threading.Thread(target=self.__iter_articles, args=(1,)),
                        threading.Thread(target=self.__iter_articles, args=(2,)),
                        threading.Thread(target=self.__iter_articles, args=(3,))]
        for read_thread in read_threads:
            read_thread.start()
            read_thread.join()
        # 所有读线程结束后开始写入xlsx
        write_threads = [threading.Thread(target=self.write_article_sheet, args=(user_xlsx, 1)),
                         threading.Thread(target=self.write_article_sheet, args=(user_xlsx, 2)),
                         threading.Thread(target=self.write_article_sheet, args=(user_xlsx, 3))]
        for write_thread in write_threads:
            write_thread.start()
            write_thread.join()
        user_xlsx.close()

    def write_article_sheet(self, xlsx, type):
        type_str_dict = {1: "回答", 2: "想法", 3: "点赞的文章"}
        iter_arr = []
        if type == 1:
            iter_arr = self.answers
        elif type == 2:
            iter_arr = self.thinks
        elif type == 3:
            iter_arr = self.likes
        sht = xlsx.add_worksheet(type_str_dict[type])
        for i, item in enumerate(iter_arr):
            sht.write_row(f'A{i + 1}', [item['content']])

    def __load_all_page(self, max_page):
        while self.page_count < max_page:
            print(f'翻页中。。。当前第{self.page_count}页,当前程序设置最大翻页数为：{max_page}')
            js = f"document.documentElement.scrollTop={self.page_count * 10000}"
            self.driver.execute_script(js)
            self.page_count += 1
            # 等待一秒加载完毕
            time.sleep(1)

    def __open_all_article(self):
        """遍历打开当前页面所有文章"""
        while True:
            open_btn = self.is_element_exist("//button[@class='Button ContentItem-more Button--plain']")
            if open_btn is not False:
                self.article_count += 1
                print(f"找到阅读全文按钮，点击打开详情，当前共{self.article_count}篇文章,一秒后继续找。。。")
                self.driver.execute_script("arguments[0].click();", open_btn)
                time.sleep(0.5)
            elif open_btn is False:
                print("当前页面文章已全打开，未找到按钮，退出寻找")
                break

    def __open_user_details(self):
        """点击查看用户详细资料"""
        open_details_btn = self.driver.find_element_by_xpath(
            "//button[@class='Button ProfileHeader-expandButton Button--plain']")
        self.driver.execute_script("arguments[0].click();", open_details_btn)

    def __iter_articles(self, type):
        """遍历所有文章
            :type 1回答 2想法 3点赞
        """
        xpath = {1: "//div[@class='ContentItem AnswerItem']", 2: "//div[@class='ContentItem PinItem']",
                 3: "//div[@class='ContentItem ArticleItem']"}
        type_str_dict = {1: "回答", 2: "想法", 3: "点赞的文章"}
        articles = self.driver.find_elements_by_xpath(xpath[type])
        for article in articles:
            data_dict = {}
            if type == 1:
                json_str = article.get_attribute('data-zop')
                data_dict = json.loads(json_str)
            # 查找内容
            data_dict['type'] = type_str_dict[type]
            # content = article.find_element_by_xpath(
            #     "//span[@class='RichText ztext CopyrightRichText-richText css-hnrfcf']").text
            data_dict['content'] = re.sub("\u8d5e\u540c [0-9]*([\s\S]*)*\u7ee7\u7eed",'',article.text)
            if type == 1:
                self.answers.append(data_dict)
            elif type == 2:
                self.thinks.append(data_dict)
            elif type == 3:
                self.likes.append(data_dict)
            print(f"找到一篇发表的{type_str_dict[type]}，当前共{len(self.answers)}篇")

    def __get_info(self):
        """获取用户基本信息"""
        user_dict = {}
        try:
            avatar = self.driver.find_element_by_xpath(
                "//img[@class='Avatar Avatar--large UserAvatar-inner']").get_attribute("src");
            user_dict['avatar'] = avatar
            name = self.driver.find_element_by_xpath("//span[@class='ProfileHeader-name']");
            user_dict['name'] = name.text
            headline = self.driver.find_element_by_xpath("//span[@class='ztext ProfileHeader-headline']");
            user_dict['headline'] = headline.text
            return user_dict
        except:
            return user_dict


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    # lg = login.Login()
    # infos, session = lg.zhihu()
    # print(f'infos, {infos}')  # Press ⌘F8 to toggle the breakpoint.
    # print(f'session,{session}')
    URL = 'https://www.zhihu.com/people/ma-wen-jia-38'
    driver = webdriver.Chrome()
    driver.get(URL)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    html_file = open('pulling.txt', 'w+')
    beauty_html = soup.prettify()
    html_file.write(beauty_html)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    people = People(1)
    people.get_user_info('ma-wen-jia-38')

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
