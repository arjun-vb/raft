import sys
import socket
import pickle
import time
import threading
from threading import Thread
from common import *

BUFF_SIZE = 1024

C2C_CONNECTIONS = {}

CLIENT_PEERS = [7001, 7002]

#port_mapping = { 12:7012, 13: 7013, 14: 7014, 15:7015, 21:7012, 23:7023, 
#24:7024, 25: 7025, 31:7013, 32:7023, 34:7034, 35:7035, 41:7014, 42:7024, 
#43:7034, 45:7045, 51:7015, 52:7025, 53:7035, 54:7045}


CLIENT_STATE = None

MessageQueue = []

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
				MessageQueue.append(data)
				print("Recieved")
			#except EOFError:
				#print("Connection closed with " + str(self.client_id))
				#for key in C2C_CONNECTIONS:
				#	print(str(key))
				#if self.client_id in C2C_CONNECTIONS:
				#	C2C_CONNECTIONS[self.client_id].close()
				#	del C2C_CONNECTIONS[self.client_id]
			except:
				a = 1


def sleep():
	time.sleep(3)

class Timer(Thread):
	def __init__(self, timeout):
		Thread.__init__(self)
		self.timeout = timeout

	def run(self):
		while True:
			if time.time() - CLIENT_STATE.last_recv_time > self.timeout and CLIENT_STATE.curr_state != "LEADER":
				CLIENT_STATE.last_recv_time = time.time()
				print("Starting Leader Election....")
				self.start_election()
				
	def start_election(self):
		CLIENT_STATE.curr_state = "CANDIDATE"
		CLIENT_STATE.curr_term += 1
		CLIENT_STATE.votedFor = CLIENT_STATE.pid
		request_vote = RequestVote( "REQ_VOTE", CLIENT_STATE.pid, CLIENT_STATE.curr_term, CLIENT_STATE.logs[-1].index, CLIENT_STATE.logs[-1].term)
		
		for client in CLIENT_STATE.port_mapping:
			if CLIENT_STATE.activeLink[client] == True:
				print("Request Vote for " + str(CLIENT_STATE.pid) + "|" + str(CLIENT_STATE.curr_term) + " sent to " + str(client))
				print(str(CLIENT_STATE.port_mapping[client]))
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[client]].send(pickle.dumps(request_vote))


# class Candidate:
# 	def __init__(self):
# 		print("Init")

# 	def 



class Server(Thread):
	def __init__(self):
		Thread.__init__(self)

	def run(self):
		while True:
			if len(MessageQueue) != 0:
				data = MessageQueue.pop(0)
				if CLIENT_STATE.curr_state == "LEADER":
					print("")
				elif CLIENT_STATE.curr_state == "FOLLOWER":
					if data.req_type == "REQ_VOTE":
						self.handleReqVoteFollower(data)
				elif CLIENT_STATE.curr_state == "CANDIDATE":
					print("")

	def handleReqVoteFollower(self, data):
		if data.term < CLIENT_STATE.curr_term:
			response = ResponseVote("RESP_VOTE", data.term, False)
			C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.candidateId]].send(pickle.dumps(response))
		elif data.term > CLIENT_STATE.curr_term:
			CLIENT_STATE.curr_term = data.term
			CLIENT_STATE.votedFor = data.candidateId
			response = ResponseVote("RESP_VOTE", data.term, True)
			CLIENT_STATE.last_recv_time = time.time()
			print("Accepted leader " + str(data.candidateId) + " for term " + str(data.term))
			C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.candidateId]].send(pickle.dumps(response))
		else:
			if CLIENT_STATE.votedFor!=None or CLIENT_STATE.votedFor!=data.candidateId:
				response = ResponseVote("RESP_VOTE", data.term, False)
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.candidateId]].send(pickle.dumps(response))
			else:
				if CLIENT_STATE.logs[-1].term<=data.lastLogTerm and CLIENT_STATE.logs[-1].index <= data.lastLogIndex:
					CLIENT_STATE.votedFor = data.candidateId
					response = ResponseVote("RESP_VOTE", data.term, True)
					CLIENT_STATE.last_recv_time = time.time()
					C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.candidateId]].send(pickle.dumps(response))
			#check queue
			# append entry
			#	term has to be greater or equal
			#	set state to follower
			#	add entry to log
			#	send ack
			#
			# req vote
			#	if not voted do the checks
			#	compare last terms
			#	vote or deny
			#
			# client msg //if im leader
			#	update log
			# 	send append entries
			#
			# append entry response
			#	keep track of majority
			#	chk if prev entry can be commited
			#	update commit index
			#
			# vote response
			#	track majorty
			#	convert to leader or follower

			# if self.state == "FOLLOWER":
			# 	print("Listen")

			# if self.state == "LEADER":
			# 	print("Heartbeat")

			# if self.state == "CANDIDATE":
			# 	pritn("Request vote")


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
			temp = client_address[1] 
			one = temp % 10
			two = int(temp / 10)
			two = two % 10
			client = one + two - CLIENT_STATE.pid
			CLIENT_STATE.activeLink[client] = True
			new_client = ClientConnections(client_address[1], connection)
			new_client.daemon = True
			new_client.start()

class Client:
	def __init__(self, listen_port, pid, port_mapping):
		self.listen_port = listen_port
		self.pid = pid
		self.ip = '127.0.0.1'
		self.port_mapping = port_mapping
		self.start_client()

	def start_client(self):
		#ip = '127.0.0.1'
		
		acceptConn = AcceptConnections(self.ip, self.listen_port)
		acceptConn.daemon = True
		acceptConn.start()
		
		self.connect_to_peers()
		
		serverThread = Server()
		serverThread.start()
		
		self.start_console()
		#start master

	def connect_to_peers(self):

		'''for client_id in CLIENT_PEERS:
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
				except:
					a = 1'''

		for client_id in self.port_mapping:
			port = self.port_mapping[client_id]
			#print(str(port))
			client2client = socket.socket()
			client2client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			client2client.bind((self.ip, port))
			
			try:
				connect_to = 7000 + client_id
				client2client.connect((self.ip, connect_to))
				print('Connected to: ' + self.ip + ':' + str(port))
				C2C_CONNECTIONS[port] = client2client
				CLIENT_STATE.activeLink[client_id] = True
				new_connection = ClientConnections(client2client)
				new_connection.daemon = True
				new_connection.start()
			except:
				a = 1


	def start_console(self):
		while True:
			user_input = raw_input()
			if user_input == "Q":
				for key in C2C_CONNECTIONS:
					print(str(key))
					#C2C_CONNECTIONS[key].shutdown(0)
					C2C_CONNECTIONS[key].close()
				sys.exit()
			if user_input == "C":
				for key in C2C_CONNECTIONS:
					print(str(key))



if __name__ == "__main__":
	listen_port = 0
	pid = 0

	if sys.argv[1] == "p1":
		listen_port = 7001
		pid = 1
		port_mapping = { 2:7012, 3:7013, 4:7014, 5:7015}
		timer = Timer(7)
	elif sys.argv[1] == "p2":
		listen_port = 7002
		pid = 2
		port_mapping = { 1:7012, 3:7023, 4:7024, 5:7025}
		timer = Timer(15)
	elif sys.argv[1] == "p3":
		listen_port = 7003
		pid = 3
		port_mapping = { 1:7013, 2:7023, 4:7034, 5:7035}
		timer = Timer(7)
	elif sys.argv[1] == "p4":
		listen_port = 7004
		pid = 4
		port_mapping = { 1:7014, 2:7024, 3:7034, 5:7045}
		timer = Timer(5)
	elif sys.argv[1] == "p5":
		listen_port = 7005
		pid = 5
		port_mapping = { 1:7015, 2:7025, 3:7035, 4:7045}
		timer = Timer(5)
		

	CLIENT_STATE = ClientState(pid, port_mapping)
	timer.start()

	Client(listen_port, pid, port_mapping)
