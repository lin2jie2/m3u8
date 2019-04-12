# coding: utf-8

# requirement pycrypto
# requirement app mpv

import m3u8
import sys

if __name__ == '__main__':
	# m3u8.play('http://110.80.136.9:2100/ppvod/OYffHoAi.m3u8')
	if len(sys.argv) != 2:
		print("usage: python3 dec.py <m3u8-url>")
	else:
		m3u8.play(sys.argv[1])
