#!/usr/bin/env python
# -*- coding: utf-8 ; tab-width: 8 -*-
""" gmail proxy

.forward に書いておくと、gmailに転送してくれるプロクシコマンド

[簡単な使い方]
 .forward に以下を書いておく
  |/Dokoka/gmail_proxy.py

 もし procmail も使っているなら、
  "|IFS=' ' && exec /Dokoka/gmail_proxy.py | /usr/bin/procmail -f- || exit 75 #mtaneda"
 みたいにする。

Copyright (C) 2016 TANEDA M.
This code was designed and coded by TANEDA M.
"""
__author__  = 'TANEDA M.'
__version__ = '0.4'

import sys
import socket
import logging
import logging.handlers
import os.path
import smtplib
import settings
from datetime import datetime
from email.message import Message
from email.parser import Parser
from email.header import decode_header
from email.header import Header
from email.mime.text import MIMEText

"""
設定
"""
BUFSIZ   = 1024

class StreamUtil:
    """
    ソケットストリームを便利にするクラス
    """

    def __init__(self):
        """ __init__
        """
        pass

    def readline(self, s):
        """ ソケットから一行読む

        Keyword arguments:
        s -- ソケット

        Return value:
        文字列
        """
        chars = []
        str = ''
        while True:
            a = s.recv(1)
            chars.append(a)
            if a == "\n" or a == "":
                str = ''.join(chars)
                break
        return str

    def send_and_recv(self, s, offline_flag, data, okstcode, outstcode):
        """ コマンドを送って、結果を受信する

        Keyword arguments:
        s -- ソケット
        offline_flag -- 現在のオフライン状態: True なら何もしない
        data -- 送りたいコマンド
        okstcode -- このコマンドが期待する応答コード (ASCII 数字 3桁)
        outstcode -- 実際の応答コード

        Return value:
        更新されたoffline_flag
        """
        if not offline_flag:
            s.send(data)
            logger.debug('SEND: ' + data.strip())

            buf = s.recv(BUFSIZ)
            if not buf:
                logger.error('Receive error')
                offline_flag = True
            else:
                logger.debug('RECV: ' + buf.strip())
                outstcode = buf.split(' ')[0]
                if outstcode != okstcode:
                    logger.error('Status error: ' + outstcode + ' required was ' + okstcode)
                    offline_flag = True

        return offline_flag


class Gmail:
    """
    本体
    """

    offline = True
    """
    ステータス列挙体
    """
    state = (
        STATE_FIRST_LINE,       # From 行
        STATE_HEADER,           # ヘッダ
        STATE_BODY,             # ヘッダが終わった後の行
    ) = range(0, 3)

    def __init__(self):
        """ __init__
        """
        pass

    def do_proxy(self):
        """ 本体
        """
        mail_from = ''
        mail_header_buf = ''
        mail_body_buf = ''
        su = StreamUtil()

        s = None
        connected_flag = False
        received_stcode = ''
        for res in socket.getaddrinfo(settings.HOST, settings.PORT, socket.AF_UNSPEC, socket.SOCK_STREAM):
            af, socktype, proto, canonname, sa = res
            try:
                s = socket.socket(af, socktype, proto)
            except socket.error, msg:
                s = None
                continue
            try:
                s.connect(sa)
            except socket.error, msg:
                s.close()
                s = None
                continue
            break

        if s is None:
            logger.error('Can\'t connect to: ' + settings.HOST)
        else:
            logger.debug('Connected to: ' + settings.HOST)
            offline = False
            connected_flag = True

        # TODO メソッド抽出
        if not offline:
            buf = s.recv(BUFSIZ)
            if not buf:
                logger.error('Receive error')
                offline = True
            else:
                logger.debug('RECV: ' + buf.strip())
                stcode = buf.split(' ')[0]
                if stcode != '220':
                    logger.error('Status error: ' + stcode + ' required was ' + okstcode)
                    offline = True
        # TODO メソッド抽出
        if not offline:
            ehlomsg = 'EHLO ' + settings.MYDOMAIN + '\r\n'
            s.send(ehlomsg)
            logger.debug('SEND: ' + ehlomsg.strip())
            buf = su.readline(s)
            logger.debug('RECV: ' + buf.strip())
            # TODO エラー処理強化
            while buf.split(' ')[0] != '250':
                buf = su.readline(s)
                logger.debug('RECV: ' + buf.strip())

        state = self.STATE_FIRST_LINE
        for line in iter(sys.stdin.readline, ""):
            # procmail のため標準出力に出す
            sys.stdout.write(line)

            if state == self.STATE_FIRST_LINE:
                mail_from = line.split(' ')[1]
                state = self.STATE_HEADER
                offline = su.send_and_recv(s, offline, 'MAIL FROM:<' + mail_from + '>\r\n', '250', received_stcode)
                offline = su.send_and_recv(s, offline, 'RCPT TO:<' + settings.MYADDR + '>\r\n', '250', received_stcode)
                offline = su.send_and_recv(s, offline, 'DATA\r\n', '354', received_stcode)

            if state == self.STATE_HEADER:
                mail_header_buf += line
                if not offline:
                    s.send(line)
                    logger.debug('SEND: ' + line.strip())
                if line == '\n':
                    state = self.STATE_BODY

            if state == self.STATE_BODY:
                mail_body_buf += line
                if not offline:
                    s.send(line)
                    logger.debug('SEND: ' + line.strip())

        offline = su.send_and_recv(s, offline, '\r\n.\r\n', '250', received_stcode)
        if received_stcode == '552-5.7.0': # もし gmail からの応答が BlockedMessage だったら、
                                           # offline フラグを強制的に偽にして、エラーメール通知を送らなくする
            logger.error('gmail says BlockedMessage, so don\'t notify with mail.')
            offline = False
        offline = su.send_and_recv(s, offline, 'QUIT\r\n', '221', received_stcode)

        # ヘッダーから件名を取得してログに出しておく
        p = Parser()
        header = p.parsestr(mail_header_buf, True)  # True=headeronly
        subject_enc = decode_header(header['Subject'])[0]
        subject = subject_enc[0]
        logger.info("Subject: " + subject);
        if subject_enc[1] is not None:
            logger.info("Subject-Encoding: " + subject_enc[1])

        if connected_flag and offline:
            logger.debug("Failed proxy to gmail")

            # エラーになったときの失敗を通知する処理
            # TODO: harre-orz氏に作ってもらった機能は、これだけのために smtplib を使っているのでいずれ統一する。
            msg = MIMEText('「' + subject + '」のメールの送信に失敗しました。', 'plain', 'utf-8')
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From'] = header['From']
            msg['To'] = header['To']
            msg['Date'] = header['Date']

            smtp = smtplib.SMTP(settings.HOST, settings.PORT)
            smtp.sendmail(mail_from, settings.MYADDR, msg.as_string())

            errmailfile = os.path.join(settings.ERRMAILDIR, datetime.now().strftime("%Y%m%d%H%M%S.eml"))
            f = open(errmailfile, 'w')
            f.write(mail_header_buf)
            f.write(mail_body_buf)
            f.close()
        else:
            logger.debug("Success proxy to gmail")

def main():
    """ メイン関数
    """

    global logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    rfh = logging.handlers.RotatingFileHandler(filename = settings.LOGFILE, maxBytes = 1099511627776, backupCount = 99)
    rfh.setLevel(logging.DEBUG)
    logger.addHandler(rfh)
    now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    logger.info('start gmail_proxy (ver ' + __version__ + ') at ' + now)

    gmail = Gmail()
    gmail.do_proxy()
    logger.info('complete gmail_proxy (ver ' + __version__ + ')')

    sys.exit(0)

if __name__ == '__main__':
    main()
