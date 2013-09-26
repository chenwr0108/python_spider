#! /usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import urllib2
import gzip
import re
import Queue
import sqlite3
import logging
from StringIO import StringIO
from urlparse import urlparse
from BeautifulSoup import BeautifulSoup
from threading import Thread

class SaveHtml():
    def __init__(self, dbfile):
        self.dbfile = dbfile

        self.conn = sqlite3.connect(dbfile, check_same_thread = False)
        #设置支持中文存储
        self.conn.text_factory = str
        self.cmd = self.conn.cursor()
        self.cmd.execute('''
            create table if not exists data(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deep INTEGER,
                url text,
                html text
            )
        ''')
        self.conn.commit()

    def save(self, deep, url, html):
        try:
            self.cmd.execute("insert into data (deep, url, html) values (?,?,?)", (deep, url, html))
            self.conn.commit()
        except Exception,e:
            print e

    def close(self):
        self.conn.close()

class WorkerGetHtml(Thread):
    def __init__(self, queueUrl, queueHtml, dbfile, deep):
        Thread.__init__(self)
        self.queueUrl = queueUrl
        self.queueHtml = queueHtml
        self.deep = deep
        self.save_html = SaveHtml(dbfile)

    def run(self):
        while True:
            url = self.queueUrl.get()
            logging.debug("[get] {0} {1}".format(url[0], url[1]))
            response = urllib2.urlopen(url[1], timeout=5)

            if response.info().get('Content-Encoding') == 'gzip':
                buf = StringIO(response.read())
                f = gzip.GzipFile(fileobj=buf)
                html = f.read()
            else:
                html = response.read()
            
            if(url[0] <= self.deep):
                self.save_html.save(url[0], url[1], html)
                self.queueHtml.put([url[0], html])

            self.queueUrl.task_done()

class WorkerParserHtml(Thread):
    def __init__(self, queueHtml, queueUrl):
        Thread.__init__(self)
        self.queueHtml = queueHtml
        self.queueUrl = queueUrl

    def run(self):
        while True:
            html = self.queueHtml.get()
            deep = html[0] + 1
            soup = BeautifulSoup(html[1])
            count = 0
            for link in soup.findAll('a', attrs={'href': re.compile("^http://")}):
                href = link.get('href')
                count = count + 1
                self.queueUrl.put([deep, href])
                logging.debug("[href] {0} {1}".format(deep, href))
            print count
            self.queueHtml.task_done()

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-u', dest="url", default="http://www.sina.com.cn", help="")
    parser.add_argument("-d", type=int, dest="deep", default=1, help="")  
    parser.add_argument("--thread", type=int, dest="thread", default=10, help="")  
    parser.add_argument('--dbfile', dest="dbfile", default="page.db", help="")
    parser.add_argument('--key', dest="key", default="", help="")
    parser.add_argument('-f', dest="logfile", default="spider.log", help="")
    parser.add_argument('-l', dest="loglevel", default="5", type=int, help="")
    parser.add_argument('--testself', dest="key", default="", help="")
    args = parser.parse_args()

    LEVELS = {
        1:logging.CRITICAL,
        2:logging.ERROR,
        3:logging.WARNING,
        4:logging.INFO,
        5:logging.DEBUG
    }
    level = LEVELS[args.loglevel]
    logging.basicConfig(filename=args.logfile,level=level)

    queueUrl = Queue.Queue()
    queueUrl.put([0, args.url])
    queueHtml = Queue.Queue()

    t = WorkerGetHtml(queueUrl, queueHtml, args.dbfile, args.deep)
    t.setDaemon(True)
    t.start()

    t1 = WorkerParserHtml(queueHtml, queueUrl)
    t1.setDaemon(True)
    t1.start()

    queueUrl.join()
    queueHtml.join()

if __name__ == "__main__":
    main()
