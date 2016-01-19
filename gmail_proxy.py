#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
__version__ = '0.1'

import sys
import socket
import logging

"""
設定
"""
HOST     = '64.233.187.27'	# Google MX
#HOST     = 'localhost'
PORT     = 25
MYDOMAIN = 'ncad.co.jp'
MYADDR   = 'mtaneda@ncad.co.jp'
BUFSIZ   = 1024
LOGFILE  = '/home/mtaneda/OreNoFile.log'

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

    def send_and_recv(self, s, offline_flag, data, okstcode):
        """ コマンドを送って、結果を受信する

        Keyword arguments:
        s -- ソケット
        offline_flag -- 現在のオフライン状態: True なら何もしない
        data -- 送りたいコマンド
        okstcode -- このコマンドが期待する応答コード (ASCII 数字 3桁)

        Return value:
        更新されたoffline_flag
        """
	if not offline_flag:
		s.send(data)
		logging.debug('SEND: ' + data.strip())

		buf = s.recv(BUFSIZ)
		if not buf:
                        logging.error('Receive error')
			offline_flag = True
		else:
			logging.debug('RECV: ' + buf.strip())
                        stcode = buf.split(' ')[0]
			if stcode != okstcode:
				logging.error('Status error: ' + stcode + ' required was ' + okstcode)
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
	STATE_FIRST_LINE,	# From 行
	STATE_HEADER,		# ヘッダ
	STATE_BODY,		# ヘッダが終わった後の行
        ) = range(0, 3)

    def __init__(self):
        """ __init__
        """
        pass

    def do_proxy(self):
        """ 本体
        """
	mail_from = ''
        su = StreamUtil()

	s = None
	for res in socket.getaddrinfo(HOST, PORT, socket.AF_UNSPEC, socket.SOCK_STREAM):
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
		logging.error('Can\'t connect to: ' + HOST)
	else:
            	logging.debug('Connected to: ' + HOST)
		offline = False

        # TODO メソッド抽出
	if not offline:
		buf = s.recv(BUFSIZ)
		if not buf:
                        logging.error('Receive error')
			offline = True
		else:
			logging.debug('RECV: ' + buf.strip())
                        stcode = buf.split(' ')[0]
			if stcode != '220':
				logging.error('Status error: ' + stcode + ' required was ' + okstcode)
				offline = True
        # TODO メソッド抽出
	if not offline:
            	ehlomsg = 'EHLO ' + MYDOMAIN + '\r\n'
                s.send(ehlomsg)
                logging.debug('SEND: ' + ehlomsg.strip())
                buf = su.readline(s)
                logging.debug('RECV: ' + buf.strip())
                # TODO エラー処理強化
                while buf.split(' ')[0] != '250':
                        buf = su.readline(s)
                        logging.debug('RECV: ' + buf.strip())

	state = self.STATE_FIRST_LINE
	for line in iter(sys.stdin.readline, ""):
                # procmail のため標準出力に出す
            	sys.stdout.write(line)

		if state == self.STATE_FIRST_LINE:
			mail_from = line.split(' ')[1]
			state = self.STATE_HEADER
                        offline = su.send_and_recv(s, offline, 'MAIL FROM:<' + mail_from + '>\r\n', '250')
                        offline = su.send_and_recv(s, offline, 'RCPT TO:<' + MYADDR + '>\r\n', '250')
                        offline = su.send_and_recv(s, offline, 'DATA\r\n', '354')

		if state == self.STATE_HEADER:
			if not offline:
				s.send(line)
				logging.debug('SEND: ' + line.strip())
			if line == '\n':
				state = self.STATE_BODY

		if state == self.STATE_BODY:
			if not offline:
				s.send(line)
				logging.debug('SEND: ' + line.strip())

        offline = su.send_and_recv(s, offline, '\r\n.\r\n', '250')
        offline = su.send_and_recv(s, offline, 'QUIT\r\n', '221')

def main():
    """ メイン関数
    """

    logging.basicConfig(filename = LOGFILE, level = logging.DEBUG)

    gmail = Gmail()
    gmail.do_proxy()

    sys.exit(0)

if __name__ == '__main__':
    main()
