import os
import sys
import socket
import pickle
import time
import rsa
import threading
from threading import Thread
from common import *


BUFF_SIZE = 20480
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

				if data.req_type == "FIX_LINK":
					CLIENT_STATE.activeLink[data.dest] = True
				elif data.req_type == "FAIL_LINK":
					CLIENT_STATE.activeLink[data.dest] = False

				elif CLIENT_STATE.curr_state == "LEADER":
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
		newEntry = LogEntry(CLIENT_STATE.curr_term, len(CLIENT_STATE.logs), data)
		entries.append(newEntry)
		CLIENT_STATE.logEntryCounts[newEntry.index] = set()
		CLIENT_STATE.logEntryCounts[newEntry.index].add(CLIENT_STATE.pid)
		
		appendEntry = AppendEntry("APPEND_ENTRY", CLIENT_STATE.curr_term, CLIENT_STATE.pid, \
								CLIENT_STATE.logs[-1].index, CLIENT_STATE.logs[-1].term, \
								entries, CLIENT_STATE.commitIndex)
		CLIENT_STATE.logs.append(newEntry)
		#CLIENT_STATE.logs[newEntry.index] = newEntry
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

		if data.term < CLIENT_STATE.curr_term:
			response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, \
				CLIENT_STATE.curr_term, False))
			C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
		else:
			CLIENT_STATE.last_recv_time = time.time()
			CLIENT_STATE.curr_leader = data.leaderId
			CLIENT_STATE.curr_state = "FOLLOWER"
			if data.term > CLIENT_STATE.curr_term:
				CLIENT_STATE.curr_term = data.term
				CLIENT_STATE.votedFor = 0
			if data.prevLogIndex < len(CLIENT_STATE.logs) and CLIENT_STATE.logs[data.prevLogIndex].term == data.prevLogTerm:
				if len(data.entries) > 0:
					for entry in data.entries:
						#CLIENT_STATE.logs[entry.index] = entry
						CLIENT_STATE.logs.append(entry)
					CLIENT_STATE.logs = CLIENT_STATE.logs[0:data.entries[-1].index+1]
				elif data.prevLogIndex < len(CLIENT_STATE.logs) - 1:
					CLIENT_STATE.logs = CLIENT_STATE.logs[0:data.prevLogIndex+1]
				for entry in CLIENT_STATE.logs:
					print(str(entry))
				CLIENT_STATE.commitIndex = data.commitIndex
				response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, \
					CLIENT_STATE.curr_term, True))
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
			else:
				response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, \
					CLIENT_STATE.curr_term, False))
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)


	def handleAppendEntry_Leader(self, data):

		if data.term <= CLIENT_STATE.curr_term:
			response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, \
				CLIENT_STATE.curr_term, False))
			C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
		else:
			CLIENT_STATE.last_recv_time = time.time()

			CLIENT_STATE.curr_leader = data.leaderId
			CLIENT_STATE.curr_state = "FOLLOWER"
			CLIENT_STATE.curr_term = data.term
			CLIENT_STATE.votedFor = 0
			if data.prevLogIndex < len(CLIENT_STATE.logs) and CLIENT_STATE.logs[data.prevLogIndex].term == data.prevLogTerm:
				if len(data.entries) > 0:
					for entry in data.entries:
						#CLIENT_STATE.logs[entry.index] = entry
						CLIENT_STATE.logs.append(entry)
					CLIENT_STATE.logs = CLIENT_STATE.logs[0:data.entries[-1].index + 1]
				elif data.prevLogIndex < len(CLIENT_STATE.logs) - 1:
					CLIENT_STATE.logs = CLIENT_STATE.logs[0:data.prevLogIndex+1]

				for entry in CLIENT_STATE.logs:
					print(str(entry))
				CLIENT_STATE.commitIndex = data.commitIndex
				response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, \
					CLIENT_STATE.curr_term, True))
				C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
			else:
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
	def __init__(self, timeout = 20):
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
		CLIENT_STATE.curr_leader = CLIENT_STATE.pid
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

	def broadcast(self, appendEntry):
		if CLIENT_STATE.curr_state == "LEADER":
			MessageQueue.append(appendEntry)
		else:
			C2C_CONNECTIONS[CLIENT_STATE.port_mapping[CLIENT_STATE.curr_leader]].send(pickle.dumps(appendEntry))
			
	def encryptPvtKey(self, private_key, public_key):
		encKey = []
		encKey.append(rsa.encrypt(str(private_key.n).encode(), public_key))
		encKey.append(rsa.encrypt(str(private_key.e).encode(), public_key))
		encKey.append(rsa.encrypt(str(private_key.d).encode(), public_key))
		encKey.append(rsa.encrypt(str(private_key.p).encode(), public_key))
		encKey.append(rsa.encrypt(str(private_key.q).encode(), public_key))
		return encKey

	def decryptPvtKey(self, enc_key, my_key):
		pvtKey = enc_key 
		n = int(rsa.decrypt(enc_key[0], my_key).decode())
		e = int(rsa.decrypt(enc_key[1], my_key).decode())
		d = int(rsa.decrypt(enc_key[2], my_key).decode())
		p = int(rsa.decrypt(enc_key[3], my_key).decode())
		q = int(rsa.decrypt(enc_key[4], my_key).decode())
		privateKey = rsa.PrivateKey(n, e, d, p, q)
		return privateKey

	def start_console(self):

		global CLIENT_STATE

		with open(self.filePath, 'rb') as file: 
			if os.stat(self.filePath).st_size != 0:
				print("loading saved state") 
				CLIENT_STATE = pickle.loads(file.read())
				CLIENT_STATE.last_recv_time = time.time()
				for entry in CLIENT_STATE.logs:
					print(str(entry))
				file.close()
			
		while True:
			user_input = input()
			#if user_input.startswith("createGroup"):
			if user_input.startswith("cg"):
				print("Create Group")
				req, group_id, client_ids = user_input.split(" ", 2)
				public_key, private_key = rsa.newkeys(256)
				encPvtKeys = {}
				for client in client_ids.split(" "):
					encPvtKeys[int(client)] = self.encryptPvtKey(private_key, CLIENT_STATE.publicKeys[int(client)]) 
					#rsa.encrypt(private_key.encode(), CLIENT_STATE.publicKeys[client])
				clientReq = ClientRequest("CLIENT_REQ", "CREATE_GRP", group_id, "", encPvtKeys, public_key)
				self.broadcast(clientReq)

			elif user_input.startswith("add"):
				print("Add")
				req, group_id, client_id = user_input.split(" ")
				#traverse log get private key. public key and encPvtKeys
				private_key = None
				public_key = None
				encPvtKeys = {}
				for log in CLIENT_STATE.logs[::-1]:
					if log.message != None and log.message.group_id == group_id:
						if CLIENT_STATE.pid in log.message.encPvtKeys:
							public_key = log.message.publicKey
							encPvtKeys = log.message.encPvtKeys
						break
					
				if public_key != None:
					private_key = self.decryptPvtKey(encPvtKeys[CLIENT_STATE.pid], CLIENT_STATE.privateKey)
					encPvtKeys[int(client_id)] = self.encryptPvtKey(private_key, CLIENT_STATE.publicKeys[int(client_id)])
					clientReq = ClientRequest("CLIENT_REQ", "ADD_USER", group_id, "", encPvtKeys, public_key)
					self.broadcast(clientReq)
				else:
					print("You are not part of group " + str(group_id))

			elif user_input.startswith("kick"):
				print("Kick")
				req, group_id, client_id = user_input.split(" ")
				#traverse log get encPvtKeys
				new_public_key, new_private_key = rsa.newkeys(256)

				new_encPvtKeys = {}
				private_key = None
				public_key = None
				encPvtKeys = {}
				for log in CLIENT_STATE.logs[::-1]:
					if log.message != None and log.message.group_id == group_id:
						if CLIENT_STATE.pid in log.message.encPvtKeys:
							public_key = log.message.publicKey
							encPvtKeys = log.message.encPvtKeys
						break

				if public_key != None:
					for client in encPvtKeys:
						if client != int(client_id):
							new_encPvtKeys[client] = self.encryptPvtKey(new_private_key, CLIENT_STATE.publicKeys[client]) 

					clientReq = ClientRequest("CLIENT_REQ", "KICK_USER", group_id, "", new_encPvtKeys, new_public_key)
					self.broadcast(clientReq)
				else:
					print("You are not part of group " + str(group_id))
	
			elif user_input.startswith("writeMessage"):
				print("Write Message")
				req, group_id, message = user_input.split(" ", 2)
				public_key = None
				encPvtKeys = {}
				for log in CLIENT_STATE.logs[::-1]:
					if log.message != None and log.message.group_id == group_id:
						public_key = log.message.publicKey
						encPvtKeys = log.message.encPvtKeys
						break
				encMessage = rsa.encrypt(message.encode(), public_key)
				clientReq = ClientRequest("CLIENT_REQ", "WRITE_MESSAGE", group_id, encMessage, encPvtKeys, public_key)
				self.broadcast(clientReq)

			#elif user_input.startswith("printGroup"):
			elif user_input.startswith("pg"):
				print("Print Group")
				req, group_id = user_input.split(" ")
				for log in CLIENT_STATE.logs:
					if log.message != None and log.message.group_id == group_id and log.message.message_type == "WRITE_MESSAGE":
						if CLIENT_STATE.pid in log.message.encPvtKeys:
							public_key = log.message.publicKey
							encPvtKeys = log.message.encPvtKeys
							msg_private_key = self.decryptPvtKey(encPvtKeys[CLIENT_STATE.pid], CLIENT_STATE.privateKey)
							msg = rsa.decrypt(log.message.encMessage, msg_private_key).decode()
							print(msg)
				
			elif user_input.startswith("failLink"):
				print("Fail Link")
				req, src, dest = user_input.split(" ")
				src = int(src)
				dest = int(dest)
				# print(str(src))
				# print(str(dest))
				networkLinkDest = NetworkLink("FAIL_LINK", src, dest)
				networkLinkSrc = NetworkLink("FAIL_LINK", dest, src)
				if int(src) == CLIENT_STATE.pid:
					CLIENT_STATE.activeLink[dest] = False
					C2C_CONNECTIONS[CLIENT_STATE.port_mapping[dest]].send(pickle.dumps(networkLinkSrc))
				elif int(dest) == CLIENT_STATE.pid:
					CLIENT_STATE.activeLink[src] = False
					C2C_CONNECTIONS[CLIENT_STATE.port_mapping[src]].send(pickle.dumps(networkLinkDest))
				else:
					C2C_CONNECTIONS[CLIENT_STATE.port_mapping[src]].send(pickle.dumps(networkLinkDest))
					C2C_CONNECTIONS[CLIENT_STATE.port_mapping[dest]].send(pickle.dumps(networkLinkSrc))

			elif user_input.startswith("fixLink"):
				print("Fix Link")
				req, src, dest = user_input.split(" ")
				src = int(src)
				dest = int(dest)
				networkLinkDest = NetworkLink("FIX_LINK", src, dest)
				networkLinkSrc = NetworkLink("FIX_LINK", dest, src)
				if src == pid:
					CLIENT_STATE.activeLink[dest] = True
					C2C_CONNECTIONS[CLIENT_STATE.port_mapping[dest]].send(pickle.dumps(networkLinkSrc))
				elif dest == pid:
					CLIENT_STATE.activeLink[src] = True
					C2C_CONNECTIONS[CLIENT_STATE.port_mapping[src]].send(pickle.dumps(networkLinkDest))
				else:
					C2C_CONNECTIONS[CLIENT_STATE.port_mapping[src]].send(pickle.dumps(networkLinkDest))
					C2C_CONNECTIONS[CLIENT_STATE.port_mapping[dest]].send(pickle.dumps(networkLinkSrc))
			elif user_input.startswith("failProcess"):
				sys.exit()	
			elif user_input == "Q":
				# for key in C2C_CONNECTIONS:
				# 	print(str(key))
				# 	C2C_CONNECTIONS[key].close()
				sys.exit()
			elif user_input == "C":
				for key in C2C_CONNECTIONS:
					print(str(key))
			elif user_input == "SV":
				file = open(self.filePath, 'wb')
				file.write(pickle.dumps(CLIENT_STATE))
				file.close()
			elif user_input == "ENC":
				message = "arjun encrypted"
				encMessage = rsa.encrypt(message.encode(), CLIENT_STATE.publicKeys[self.pid])
				
				print("original string: ", message)
				print("encrypted string: ", encMessage)
				
				decMessage = rsa.decrypt(encMessage, CLIENT_STATE.privateKey).decode()
				
				print("decrypted string: ", decMessage)				
			else:
				client_msg = ClientMessage("CLIENT_REQ", user_input)
				MessageQueue.append(client_msg)



if __name__ == "__main__":
	listen_port = 0
	pid = 0
	#filePath = '/home/arjun/ucsb/cs271_distributed_systems/raft/logs/'
	filePath = ""

	if sys.argv[1] == "p1":
		listen_port = 7001
		pid = 1
		port_mapping = { 2:7012, 3:7013, 4:7014, 5:7015}
		filePath = os.path.join(os.getcwd(), 'logs/c1.txt')
		timer = Timer(30)
	elif sys.argv[1] == "p2":
		listen_port = 7002
		pid = 2
		port_mapping = { 1:7012, 3:7023, 4:7024, 5:7025}
		filePath = os.path.join(os.getcwd(), 'logs/c2.txt')
		timer = Timer(35)
	elif sys.argv[1] == "p3":
		listen_port = 7003
		pid = 3
		port_mapping = { 1:7013, 2:7023, 4:7034, 5:7035}
		filePath = os.path.join(os.getcwd(), 'logs/c3.txt')
		timer = Timer(40)
	elif sys.argv[1] == "p4":
		listen_port = 7004
		pid = 4
		port_mapping = { 1:7014, 2:7024, 3:7034, 5:7045}
		filePath = os.path.join(os.getcwd(), 'logs/c4.txt')
		timer = Timer(45)
	elif sys.argv[1] == "p5":
		listen_port = 7005
		pid = 5
		port_mapping = { 1:7015, 2:7025, 3:7035, 4:7045}
		filePath = os.path.join(os.getcwd(), 'logs/c5.txt')
		timer = Timer(50)
		
	os.makedirs(os.path.dirname(filePath), exist_ok=True)


	CLIENT_STATE = ClientState(pid, port_mapping)
	timer.daemon = True
	timer.start()

	for i in range(1,6):
		keyPath = os.path.join(os.getcwd(), 'keys/pub'+str(i)+'.pem')
		with open(keyPath) as f:
			CLIENT_STATE.publicKeys[i] = rsa.PublicKey.load_pkcs1(f.read().encode('utf8'))
			f.close()
		if i == pid:
			keyPath = os.path.join(os.getcwd(), 'keys/pvt'+str(i)+'.pem')
			with open(keyPath) as f:
				CLIENT_STATE.privateKey = rsa.PrivateKey.load_pkcs1(f.read().encode('utf8'))
				f.close()
			

	client = Client(listen_port, pid, port_mapping, filePath)
	client.start_client()