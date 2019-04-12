# coding: utf-8

import requests
from Crypto.Cipher import AES
from multiprocessing.dummy import Pool as ThreadPool
import re
from hashlib import md5
import os, os.path
import subprocess


def play(url, cache_file = None):
	entry = url if cache_file is None else cache_file
	result = load(url)
	if result is not False:
		layer, data = result
		if layer == 1:
			if len(data) == 1:
				id, bandwidth, resolution, uri = data[0]
				play(uri, entry)
			else:
				print("streams:")
				for stream in data:
					id, bandwidth, resolution, uri = stream
					print("  {}. {} {} b/s".format(id, resolution, bandwidth))
				index = 0
				while True:
					index = int(input("please select: "))
					if index > 0 and index <= len(data):
						break
				play(data[index - 1][3], entry)
		elif layer == 2:
			refresh, playlist = data
			filename = "{}.mp4".format(md5(entry.encode('utf-8')).hexdigest())
			if not os.path.exists(filename):
				files = cache(playlist)
				merge(files, filename)
			print(filename)
			subprocess.call("mpv {}".format(filename), shell=True)


def load(url):
	lines = fetch(url)
	if lines is False:
		return False
	return parse(lines, url)


def parse(lines, referrer):
	if lines[0] == '#EXTM3U':
		if lines[1][0:18] == '#EXT-X-STREAM-INF:':
			return [1, parse_layer_1(lines, referrer)]
		else:
			return [2, parse_layer_2(lines, referrer)]
	else:
		return [0, "Invalid m3u8 file"]


def parse_layer_1(lines, referrer):
	streams = []

	i = 1
	while i < len(lines):
		line = lines[i]
		if line[0:18] == '#EXT-X-STREAM-INF:':
			id = None
			bandwidth = None
			resolution = None
			uri = None
			for kv in line[18:].split(","):
				k, v = kv.split('=', 1)
				if k == 'PROGRAM-ID':
					id = v
				elif k == 'BANDWIDTH':
					bandwidth = int(v)
				elif k == 'RESOLUTION':
					resolution = v
			i = i + 1
			uri = lines[i]
			streams.append([id, bandwidth, resolution, gen_url(referrer, uri)])
		else:
			print(line)
		i = i + 1

	return streams


def parse_layer_2(lines, referrer):
	method = None
	key = None
	iv = None

	playlist = []
	refresh = True

	i = 1
	while i < len(lines):
		line = lines[i]
		tmp = line.split(':', 1)
		tag = tmp[0]
		d = tmp[1] if len(tmp) > 1 else None
		if tag == '#EXT-X-KEY':
			for kv in d.split(","):
				k, v = kv.split('=', 1)
				if k == 'METHOD':
					method = v
					key = None
					iv = None
				elif k == 'URI':
					key_uri = v[1:-1]
					r = requests.get(gen_url(referrer, key_uri))
					if r.status_code == requests.codes.OK:
						key = r.text.strip()
				elif k == 'IV':
					iv = v
		elif tag == '#EXTINF':
			duration, title = d.split(',', 1)
			i += 1
			uri = lines[i]
			playlist.append([gen_url(referrer, uri), method, key, iv])
		elif tag == '#EXT-X-ENDLIST':
			refresh = False
			break
		i = i + 1

	return [refresh, playlist]


def gen_url(referrer, uri):
	regex = re.compile("^https?:\/\/")
	if re.match(regex, uri) is None:
		scheme, t1 = referrer.split('://', 1)
		domain, t2 = t1.split('/', 1)

		if uri[0] == '/':
			return "{}://{}{}".format(scheme, domain, uri)

		t3 = t2.split('?', 1)
		path = t3[0]
		paths = path.split('/')
		paths.pop()

		t4 = uri.split('?', 1)
		t5 = t4[0].split('/')

		for d in t5:
			if d == '.':
				pass
			elif d == '..':
				paths.pop()
			else:
				paths.append(d)
		url = "{}://{}/{}".format(scheme, domain, '/'.join(paths))
		if len(t4) == 2:
			url = "{}?{}".format(url, t4[1])
		return url
	else:
		return uri


def fetch(url):
	r = requests.get(url)
	if r.status_code == requests.codes.OK:
		return r.text.strip().split("\n")
	else:
		print(url, r.status_code, "fetch fail!")
		return False


def cache(playlist, threads = 10):
	pools = ThreadPool(threads)
	files = pools.map(cache_ts, playlist)
	pools.close()
	pools.join()
	return files


def merge(files, to, delete = True):
	processed = 0
	with open(to, "wb") as outfile:
		for filename in files:
			with open(filename, 'rb') as infile:
				outfile.write(infile.read())
				infile.close()
				processed = processed + 1
			if delete:
				os.unlink(filename)
		outfile.close()
	return len(files) == processed


def cache_ts(ts):
	url, method, key, iv = ts
	filename = "{}.ts".format(md5(url.encode('utf-8')).hexdigest())

	if os.path.exists(filename):
		return filename

	content = download(url, method, key, iv)
	if content is False:
		print(url, "download fail!")
	else:
		with open(filename, 'wb') as f:
			f.write(content)
			f.close()
			return filename
	return False


def download(url, method = None, key = None, iv = None):
	r = requests.get(url)
	if r.status_code == requests.codes.OK:
		if method is None or method == 'NONE':
			return r.content
		elif key is None:
			return r.content
		elif iv is None:
			cipher = AES.new(key, AES.MODE_CBC, key)
			return cipher.decrypt(r.content)
		else:
			cipher = AES.new(key, AES.MODE_CBC, iv)
			return cipher.decrypt(r.content)
	else:
		return False
