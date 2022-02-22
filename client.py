import sys
import socket
import pickle
import time
import threading
from threading import Thread
from common import *

BUFF_SIZE = 1024

C2C_CONNECTIONS = {}

#port_mapping = { 12:7012, 13: 7013, 14: 7014, 15:7015, 21:7012, 23:7023, 
#24:7024, 25: 7025, 31:7013, 32:7023, 34:7034, 35:7035, 41:7014, 42:7024, 
#43:7034, 45:7045, 51:7015, 52:7025, 53:7035, 54:7045}


CLIENT_STATE = None

MessageQueue = []



def sleep():
	time.sleep(3)


class Server(Thread):
	def __init__(self):
		Thread.__init__(self)

	def run(self):
		while True:
			if len(MessageQueue) != 0:
				data = MessageQueue.pop(0)
				if CLIENT_STATE.curr_state == "LEADER":
					if data.req_type == "REQ_VOTE":
						print("Request vote leader")
						self.handleReqVote_Leader(data)
					elif data.req_type == "APPEND_ENTRY":
						print("append entry")
					elif data.req_type == "RESP_APPEND_ENTRY":
						print("resp append entry")

				elif CLIENT_STATE.curr_state == "FOLLOWER":
					if data.req_type == "REQ_VOTE":
						self.handleReqVote_Follower(data)
					elif data.req_type == "APPEND_ENTRY":
						self.handleAppendEntry_Follower(data)

				elif CLIENT_STATE.curr_state == "CANDIDATE":
					if data.req_type == "REQ_VOTE":
						print("req vote candidate")
						self.handleReqVote_Follower(data)
					elif data.req_type == "RESP_VOTE":
						print("resp vote")
						self.handleRespVote_Candidate(data)
					elif data.req_type == "APPEND_ENTRY":
						print("append entry")
	
	def handleReqVote_Leader(self, data):

		if data.term <= CLIENT_STATE.curr_term:
			deny = pickle.dumps(ResponseVote("RESP_VOTE", CLIENT_STATE.curr_term, False))
			print("Rejected leader " + str(data.candidateId) + " for term " + str(data.term))
			C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.candidateId]].send(deny)
		else:
			CLIENT_STATE.curr_state = "FOLLOWER"
			CLIENT_STATE.curr_term = data.term
			CLIENT_STATE.votedFor = data.candidateId
			CLIENT_STATE.last_recv_time = time.time()

			accept = pickle.dumps(ResponseVote("RESP_VOTE", CLIENT_STATE.curr_term, True))
			print("Accepted leader " + str(data.candidateId) + " for term " + str(data.term))
			C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.candidateId]].send(accept)


	def handleReqVote_Follower(self, data):
		
		vote = False

		if data.term < CLIENT_STATE.curr_term:
			vote = False

		elif data.term > CLIENT_STATE.curr_term:
			vote = True
	
		else:
			if CLIENT_STATE.votedFor == 0 or CLIENT_STATE.votedFor == data.candidateId: 
				if CLIENT_STATE.logs[-1].term < data.lastLogTerm:
					vote = True
				elif CLIENT_STATE.logs[-1].term == data.lastLogTerm and CLIENT_STATE.logs[-1].index <= data.lastLogIndex:
					vote = True
				else:
					vote = False			
			else:
				vote = False

		if vote == True:
			CLIENT_STATE.curr_state = "FOLLOWER"
			CLIENT_STATE.curr_term = data.term
			CLIENT_STATE.votedFor = data.candidateId
			CLIENT_STATE.last_recv_time = time.time()
			accept = pickle.dumps(ResponseVote("RESP_VOTE", CLIENT_STATE.curr_term, True))
			print("Accepted leader " + str(data.candidateId) + " for term " + str(data.term))
			C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.candidateId]].send(accept)
		else:
			deny = pickle.dumps(ResponseVote("RESP_VOTE", CLIENT_STATE.curr_term, False))
			print("Rejected leader " + str(data.candidateId) + " for term " + str(data.term))
			C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.candidateId]].send(deny)

	def handleRespVote_Candidate(self, data):
		if data.term > CLIENT_STATE.curr_term:
			CLIENT_STATE.curr_state = "FOLLOWER"
			CLIENT_STATE.curr_term = data.term
			CLIENT_STATE.votedFor = 0 
			CLIENT_STATE.last_recv_time = time.time()
		else:
			if data.voteGranted == True:
				key = str(CLIENT_STATE.pid) + "|" + str(data.term)
				CLIENT_STATE.voteCounts[key] += 1
				if CLIENT_STATE.voteCounts[key] >= 3:
					CLIENT_STATE.curr_state = "LEADER"
					#append entries heartbeat

	

	'''def handleAppendEntry_Follower(self, data):

		if data.term < CLIENT_STATE.curr_term:
			response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.curr_term, False))
			C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
		else:
			if data.term > CLIENT_STATE.curr_term:
				CLIENT_STATE.curr_term = data.term
				CLIENT_STATE.votedFor = 0
			CLIENT_STATE.last_recv_time = time.time()
			if CLIENT_STATE.logs[data.prevLogIndex] != None and CLIENT_STATE.logs[data.prevLogIndex].term == data.prevLogTerm:
				CLIENT_STATE.logs.append(data.entries) # to do
				response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", data.term, True))
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
			else:
				response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", data.term, False))
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)'''

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
		CLIENT_STATE.voteCounts[str(CLIENT_STATE.pid) + "|" + str(CLIENT_STATE.curr_term)] = 1
		
		for client in CLIENT_STATE.port_mapping:
			if CLIENT_STATE.activeLink[client] == True:
				print("Request Vote for " + str(CLIENT_STATE.pid) + "|" + str(CLIENT_STATE.curr_term) + " sent to " + str(client))
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[client]].send(pickle.dumps(request_vote))


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
				print("Recieved from " + str(self.client_id))
				MessageQueue.append(data)
			except:
				print("Error: Closing connection with " + str(self.client_id))
				CLIENT_STATE.activeLink[self.client_id] = False
				self.connection.close()
				break

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
			new_client = ClientConnections(client, connection)
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
		
		acceptConn = AcceptConnections(self.ip, self.listen_port)
		acceptConn.daemon = True
		acceptConn.start()
		
		self.connect_to_peers()
		
		serverThread = Server()
		serverThread.daemon = True
		serverThread.start()
		
		self.start_console()

	def connect_to_peers(self):

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
				new_connection = ClientConnections(client_id, client2client)
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
					#CLIENT_STATE.activeLink[self.port_mapping[key]] = False
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
		timer = Timer(5)
	elif sys.argv[1] == "p2":
		listen_port = 7002
		pid = 2
		port_mapping = { 1:7012, 3:7023, 4:7024, 5:7025}
		timer = Timer(10)
	elif sys.argv[1] == "p3":
		listen_port = 7003
		pid = 3
		port_mapping = { 1:7013, 2:7023, 4:7034, 5:7035}
		timer = Timer(15)
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
	timer.daemon = True
	timer.start()

	Client(listen_port, pid, port_mapping)
