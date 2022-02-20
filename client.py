import sys
import socket
import pickle
import time
import threading
from threading import Thread

BUFF_SIZE = 1024

C2C_CONNECTIONS = {}

CLIENT_PEERS = [7001, 7002, 7003]

class ClientConnections(Thread):
	def __init__(self, client_id, connection):
		Thread.__init__(self)
		self.client_id = client_id
		self.connection = connection

	def run(self):		
		while True:	
			try:		
				response = self.connection.recv(BUFF_SIZE)
				data = pickle.loads(response)
				print("Recieved")
			except:
				print("Connection closed with " + self.client_id)
				C2C_CONNECTIONS[self.client_id].close()
				del C2C_CONNECTIONS[self.client_id]


class AcceptConnections(Thread):
	def __init__(self, ip, listen_port):
		Thread.__init__(self)
		self.listen_port = listen_port
		self.ip = ip

	def run(self):		
		print('Waiting for Connections...')

		client2client = socket.socket()
		client2client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		client2client.bind((self.ip, self.listen_port))
		client2client.listen(5)

		while True:			
			connection, client_address = client2client.accept()
			print('Connected to: ' + client_address[0] + ':' + str(client_address[1]))
			C2C_CONNECTIONS[client_address[1]] = connection
			new_client = ClientConnections(client_address[1], connection)
			new_client.daemon = True
			new_client.start()



def sleep():
	time.sleep(3)

class Client:
	def __init__(self, listen_port, pid):
		#Thread.__init__(self)
		self.listen_port = listen_port
		self.pid = pid
		self.ip = '127.0.0.1'
		self.start_client()

	def start_client(self):
		#ip = '127.0.0.1'
		
		acceptConn = AcceptConnections(self.ip, self.listen_port)
		acceptConn.daemon = True
		acceptConn.start()
		self.connect_to_peers()
		self.start_console()

	def connect_to_peers(self):

		for client_id in CLIENT_PEERS:
			if client_id != self.listen_port:
				client2client = socket.socket()
				client2client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
				#client2client.bind((ip, 7032))
				
				try:
					client2client.connect((self.ip, client_id))
					print('Connected to: ' + self.ip + ':' + str(client_id))
					C2C_CONNECTIONS[client_id] = client2client
					new_connection = ClientConnections(client2client)
					new_connection.daemon = True
					new_connection.start()
				

				

	def start_console(self):
		while True:
			user_input = raw_input()
			if user_input == "Q":
				for key in C2C_CONNECTIONS:
					print(str(key))
					C2C_CONNECTIONS[key].shutdown(0)
					C2C_CONNECTIONS[key].close()
				sys.exit()



if __name__ == "__main__":
	listen_port = 0
	pid = 0

	if sys.argv[1] == "p1":
		listen_port = 7001
		pid = 1
	elif sys.argv[1] == "p2":
		listen_port = 7002
		pid = 2
	elif sys.argv[1] == "p3":
		listen_port = 7003
		pid = 3
	elif sys.argv[1] == "p4":
		listen_port = 7004
		pid = 4
	elif sys.argv[1] == "p5":
		listen_port = 7005
		pid = 5

	Client(listen_port, pid)
