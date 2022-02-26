import os
import sys
import socket
import pickle
import time
import threading
from threading import Thread
from common import *


BUFF_SIZE = 1024
C2C_CONNECTIONS = {}
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
						self.handleAppendEntry_Leader(data)
						print("append entry leader")
					elif data.req_type == "RESP_APPEND_ENTRY":
						print("resp append entry leader")
						self.handleRespAppendEntry_Leader(data)
					elif data.req_type == "CLIENT_REQ":
						print("Client req leader")
						self.handleClientReq_Leader(data)

				elif CLIENT_STATE.curr_state == "FOLLOWER":
					if data.req_type == "REQ_VOTE":
						print("req vote follower")
						self.handleReqVote_Follower(data)
					elif data.req_type == "APPEND_ENTRY":
						print("append entry follower")
						self.handleAppendEntry_Follower(data)

				elif CLIENT_STATE.curr_state == "CANDIDATE":
					if data.req_type == "REQ_VOTE":
						print("req vote candidate")
						self.handleReqVote_Follower(data)
					elif data.req_type == "RESP_VOTE":
						print("resp vote candidate")
						self.handleRespVote_Candidate(data)
					elif data.req_type == "APPEND_ENTRY":
						print("append entry candidate")
						self.handleAppendEntry_Follower(data)
	
	def handleClientReq_Leader(self, data):

		entries = []
		newEntry = LogEntry(CLIENT_STATE.curr_term, len(CLIENT_STATE.logs), data.message)
		entries.append(newEntry)
		CLIENT_STATE.logEntryCounts[newEntry.index] = set()
		CLIENT_STATE.logEntryCounts[newEntry.index].add(CLIENT_STATE.pid)
		
		appendEntry = AppendEntry("APPEND_ENTRY", CLIENT_STATE.curr_term, CLIENT_STATE.pid, \
								CLIENT_STATE.logs[-1].index, CLIENT_STATE.logs[-1].term, \
								entries, CLIENT_STATE.commitIndex)
		CLIENT_STATE.logs.append(newEntry)
		CLIENT_STATE.leaderHeartbeat = time.time()
		
		for client in CLIENT_STATE.port_mapping:
			if CLIENT_STATE.activeLink[client] == True:
				print("New log entry for index|term " + str(newEntry.index) + "|" + str(CLIENT_STATE.curr_term) + " sent to " + str(client))
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[client]].send(pickle.dumps(appendEntry))
		for entry in CLIENT_STATE.logs:
			print(str(entry))

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

		else:
			if data.term > CLIENT_STATE.curr_term:
				CLIENT_STATE.curr_term = data.term
				CLIENT_STATE.votedFor = 0
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
					print("BECAME LEADER")
					CLIENT_STATE.curr_state = "LEADER"
					for key in CLIENT_STATE.nextIndex:
						CLIENT_STATE.nextIndex[key] = CLIENT_STATE.logs[-1].index + 1

					index = CLIENT_STATE.commitIndex + 1
					while index <= CLIENT_STATE.logs[-1].index:
						CLIENT_STATE.logEntryCounts[index] = set()
						CLIENT_STATE.logEntryCounts[index].add(CLIENT_STATE.pid)
						index += 1
					#CLIENT_STATE.leaderHeartbeat = time.time()
					heartBeatThread = HeartBeat()
					heartBeatThread.start()

	
	def handleAppendEntry_Follower(self, data):

		CLIENT_STATE.last_recv_time = time.time()

		if data.term < CLIENT_STATE.curr_term:
			response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, \
				CLIENT_STATE.curr_term, False))
			C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
		else:
			CLIENT_STATE.curr_state = "FOLLOWER"
			if data.term > CLIENT_STATE.curr_term:
				CLIENT_STATE.curr_term = data.term
				CLIENT_STATE.votedFor = 0
			if data.prevLogIndex < len(CLIENT_STATE.logs) and CLIENT_STATE.logs[data.prevLogIndex].term == data.prevLogTerm:
				if len(data.entries) > 0:
					for entry in data.entries:
						CLIENT_STATE.logs.append(entry)
					for entry in CLIENT_STATE.logs:
						print(str(entry))
				CLIENT_STATE.commitIndex = data.commitIndex
				response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, \
					CLIENT_STATE.curr_term, True))
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
			else:
				# del mismatched log
				response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, \
					CLIENT_STATE.curr_term, False))
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)


	def handleAppendEntry_Leader(self, data):

		if data.term <= CLIENT_STATE.curr_term:
			response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, \
				CLIENT_STATE.curr_term, False))
			C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
		else:
			CLIENT_STATE.curr_state = "FOLLOWER"
			CLIENT_STATE.curr_term = data.term
			CLIENT_STATE.votedFor = 0
			if data.prevLogIndex < len(CLIENT_STATE.logs) and CLIENT_STATE.logs[data.prevLogIndex].term == data.prevLogTerm:
				if len(data.entries) > 0:
					for entry in data.entries:
						CLIENT_STATE.logs.append(entry)
					for entry in CLIENT_STATE.logs:
						print(str(entry))
				CLIENT_STATE.commitIndex = data.commitIndex
				response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, \
					CLIENT_STATE.curr_term, True))
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
			else:
				# del mismatched log
				response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, \
					CLIENT_STATE.curr_term, False))
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)


	def handleRespAppendEntry_Leader(self, data):
		if data.success == True:  
			CLIENT_STATE.nextIndex[data.pid] = CLIENT_STATE.logs[-1].index + 1
			index = CLIENT_STATE.commitIndex + 1
			while index <= CLIENT_STATE.logs[-1].index:	
				CLIENT_STATE.logEntryCounts[index].add(data.pid)			
				if len(CLIENT_STATE.logEntryCounts[index]) >= 3:
					if CLIENT_STATE.logs[index].term == CLIENT_STATE.curr_term:
						CLIENT_STATE.commitIndex = index
					#elif: check leaders term is present in majority - may not be needed I think code automatically takes care
				else: 
					break
				index += 1
		else:
			if data.term > CLIENT_STATE.curr_term:
				CLIENT_STATE.curr_state = "FOLLOWER"
				CLIENT_STATE.curr_term = data.term
				CLIENT_STATE.votedFor = 0
			else:
				CLIENT_STATE.nextIndex[data.pid] -= 1
				entries = CLIENT_STATE.logs[CLIENT_STATE.nextIndex[data.pid]:]
				appendEntry = AppendEntry("APPEND_ENTRY", CLIENT_STATE.curr_term, CLIENT_STATE.pid, \
								CLIENT_STATE.logs[CLIENT_STATE.nextIndex[data.pid] - 1].index, \
								CLIENT_STATE.logs[CLIENT_STATE.nextIndex[data.pid] - 1].term, \
								entries, CLIENT_STATE.commitIndex)
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.pid]].send(pickle.dumps(appendEntry))


class HeartBeat(Thread):
	def __init__(self, timeout = 15):
		Thread.__init__(self)
		self.timeout = timeout

	def run(self):
		entry = []
		appendEntry = AppendEntry("APPEND_ENTRY", CLIENT_STATE.curr_term, CLIENT_STATE.pid, \
								CLIENT_STATE.logs[-1].index, CLIENT_STATE.logs[-1].term, entry, CLIENT_STATE.commitIndex)
		while CLIENT_STATE.curr_state == "LEADER":
			if time.time() - CLIENT_STATE.leaderHeartbeat > self.timeout:
				CLIENT_STATE.leaderHeartbeat = time.time() 
				appendEntry.prevLogIndex = CLIENT_STATE.logs[-1].index
				appendEntry.prevLogTerm = CLIENT_STATE.logs[-1].term
				appendEntry.commitIndex = CLIENT_STATE.commitIndex
				for client in CLIENT_STATE.port_mapping:
					if CLIENT_STATE.activeLink[client] == True:
						print("HeartBeat for " + str(CLIENT_STATE.pid) + "|" + str(CLIENT_STATE.curr_term) + " sent to " + str(client))
						C2C_CONNECTIONS[CLIENT_STATE.port_mapping[client]].send(pickle.dumps(appendEntry))


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
		CLIENT_STATE.voteCounts[str(CLIENT_STATE.pid) + "|" + str(CLIENT_STATE.curr_term)] = 1
		
		for client in CLIENT_STATE.port_mapping:
			if CLIENT_STATE.activeLink[client] == True:
				request_vote = RequestVote( "REQ_VOTE", CLIENT_STATE.pid, CLIENT_STATE.curr_term, \
					CLIENT_STATE.logs[CLIENT_STATE.nextIndex[client] - 1].index, \
					CLIENT_STATE.logs[CLIENT_STATE.nextIndex[client] - 1].term)
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
	def __init__(self, listen_port, pid, port_mapping, filePath):
		self.listen_port = listen_port
		self.pid = pid
		self.ip = '127.0.0.1'
		self.port_mapping = port_mapping
		self.filePath = filePath

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
		#print(os.getcwd())
		#filePath = "'" + os.getcwd()+"/logs/c1.txt'"
		#print(str(filePath)) 
		global CLIENT_STATE
		#filePath = '/home/arjun/ucsb/cs271_distributed_systems/raft/logs/c1.txt'

		if os.path.exists(self.filePath):
			file = open(self.filePath) 
			if os.stat(self.filePath).st_size != 0: 
				CLIENT_STATE = pickle.loads(file.read())
				CLIENT_STATE.last_recv_time = time.time()
				file.close()
		else:
			print("Prev state does not exist")
			
		while True:
			user_input = raw_input()
			if user_input == "Q":
				for key in C2C_CONNECTIONS:
					print(str(key))
					#C2C_CONNECTIONS[key].shutdown(0)
					#CLIENT_STATE.activeLink[self.port_mapping[key]] = False
					C2C_CONNECTIONS[key].close()
				sys.exit()
			elif user_input == "C":
				for key in C2C_CONNECTIONS:
					print(str(key))
			elif user_input == "SV":
				file = open(self.filePath, 'w')
				file.write(pickle.dumps(CLIENT_STATE))
				file.close()
			else:
				client_msg = ClientMessage("CLIENT_REQ", user_input)
				MessageQueue.append(client_msg)



if __name__ == "__main__":
	listen_port = 0
	pid = 0
	filePath = '/home/arjun/ucsb/cs271_distributed_systems/raft/logs/'

	if sys.argv[1] == "p1":
		listen_port = 7001
		pid = 1
		port_mapping = { 2:7012, 3:7013, 4:7014, 5:7015}
		filePath += 'c1.txt'
		timer = Timer(20)
	elif sys.argv[1] == "p2":
		listen_port = 7002
		pid = 2
		port_mapping = { 1:7012, 3:7023, 4:7024, 5:7025}
		filePath += 'c2.txt'
		timer = Timer(30)
	elif sys.argv[1] == "p3":
		listen_port = 7003
		pid = 3
		port_mapping = { 1:7013, 2:7023, 4:7034, 5:7035}
		filePath += 'c3.txt'
		timer = Timer(25)
	elif sys.argv[1] == "p4":
		listen_port = 7004
		pid = 4
		port_mapping = { 1:7014, 2:7024, 3:7034, 5:7045}
		filePath += 'c4.txt'
		timer = Timer(35)
	elif sys.argv[1] == "p5":
		listen_port = 7005
		pid = 5
		port_mapping = { 1:7015, 2:7025, 3:7035, 4:7045}
		filePath += 'c5.txt'
		timer = Timer(40)
		

	CLIENT_STATE = ClientState(pid, port_mapping)
	timer.daemon = True
	timer.start()

	client = Client(listen_port, pid, port_mapping, filePath)
	client.start_client()