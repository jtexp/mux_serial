#! /usr/bin/env python

import sys, os
import select, socket, serial

_default_host = 'localhost'
_default_port = 23200

_default_device = '/dev/ttyS0'
_default_baudrate = 9600
_default_width = serial.EIGHTBITS
_default_parity = serial.PARITY_NONE
_default_stopbits = serial.STOPBITS_ONE
_default_xon = 0
_default_rtc = 0

_READ_ONLY = select.POLLIN | select.POLLPRI

class MuxServer(object):
	def __init__(self,
				host=_default_host,
				port=_default_port,
				device = _default_device,
				baudrate=_default_baudrate,
				width = _default_width,
				parity = _default_parity,
				stopbits = _default_stopbits,
				xon = _default_xon,
				rtc = _default_rtc,):
		self.host = host
		self.port = port
		self.device = device
		self.baudrate = baudrate
		self.width = width
		self.parity = parity
		self.stopbits = stopbits
		self.xon = xon
		self.rtc = rtc

		self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.server.setblocking(0)

		self.poller = select.poll()

		self.fd_to_socket = {}
		self.clients = []

	def close(self):
		print('\nMUX > Closing...', file=sys.stderr)

		for client in self.clients:
			client.close()
		self.tty.close()
		self.server.close()

		print('MUX > Done! =)', file=sys.stderr)

	def add_client(self, client):
		print('MUX > New connection from', client.getpeername(), file=sys.stderr)
		client.setblocking(0)
		self.fd_to_socket[client.fileno()] = client
		self.clients.append(client)
		self.poller.register(client, _READ_ONLY)

	def remove_client(self, client, why='?'):
		try:
			name = client.getpeername()
		except:
			name = 'client %d' % client.fileno()
		print('MUX > Closing %s: %s' % (name, why), file=sys.stderr)
		self.poller.unregister(client)
		self.clients.remove(client)
		client.close()

	def run(self):
		try:
			self.tty = serial.Serial(self.device, self.baudrate,
									self.width, self.parity, self.stopbits,
									1, self.xon, self.rtc)
			self.tty.flushInput()
			self.tty.flushOutput()
			self.poller.register(self.tty, _READ_ONLY)
			self.fd_to_socket[self.tty.fileno()] = self.tty
			print('MUX > Serial port: %s @ %s' % (self.device, self.baudrate), file=sys.stderr)

			self.server.bind((self.host, self.port))
			self.server.listen(5)
			self.poller.register(self.server, _READ_ONLY)
			self.fd_to_socket[self.server.fileno()] = self.server
			print('MUX > Server: %s:%d' % self.server.getsockname(), file=sys.stderr)

			print('MUX > Use ctrl+c to stop...\n', file=sys.stderr)

			while True:
				events = self.poller.poll(500)
				for fd, flag in events:
					# Get socket from fd
					s = self.fd_to_socket[fd]

					if flag & select.POLLHUP:
						self.remove_client(s, 'HUP')

					elif flag & select.POLLERR:
						self.remove_client(s, 'Received error')

					elif flag & (_READ_ONLY):
						# A readable server socket is ready to accept a connection
						if s is self.server:
							connection, client_address = s.accept()
							self.add_client(connection)

						# Data from serial port
						elif s is self.tty:
							data = s.read(80)
							for client in self.clients:
								client.send(data)

						# Data from client
						else:
							data = s.recv(80)

							# Client has data
							if data: self.tty.write(data)

							# Interpret empty result as closed connection
							else: self.remove_client(s, 'Got no data')

		except serial.SerialException as e:
			print('\nMUX > Serial error: "%s". Closing...' % e, file=sys.stderr)

		except socket.error as e:
			print('\nMUX > Socket error: %s' % e.strerror, file=sys.stderr)

		except (KeyboardInterrupt, SystemExit):
			pass

		finally:
			self.close()


if __name__ == '__main__':
	import optparse

	# Option parsing, duh
	parser = optparse.OptionParser()
	parser.add_option('-d',
					'--device',
					help = 'Serial port device',
					dest = 'device',
					default = _default_device)
	parser.add_option('-b',
					'--baud',
					help = 'Baud rate',
					dest = 'baudrate',
					type = 'int',
					default = _default_baudrate)
	parser.add_option('-p',
					'--port',
					help = 'Host port',
					dest = 'port',
					type = 'int',
					default = _default_port)
	(opts, args) = parser.parse_args()

	s = MuxServer(port = opts.port,
				device = opts.device,
				baudrate = opts.baudrate)
	s.run()
