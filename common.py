import time

class LogEntry:
	def __init__(self, term, index, message):
		self.term = term
		self.index = index
		self.message = message
	
	def __str__(self):
		return str(self.term) + "|" + str(self.index) + "|" + str(self.message)

class RequestVote:
	def __init__(self, req_type, candidateId, term, lastLogIndex, lastLogTerm):
		self.candidateId = candidateId
		self.req_type =req_type
		self.term = term
		self.lastLogIndex = lastLogIndex
		self.lastLogTerm = lastLogTerm

class ResponseVote:
	def __init__(self, req_type, term, voteGranted):
		self.term = term
		self.req_type =req_type
		self.voteGranted = voteGranted

class AppendEntry:
	def __init__(self, req_type, term, leaderId, prevLogIndex, prevLogTerm, entries, commitIndex):
		self.term = term
		self.req_type =req_type
		self.leaderId = leaderId
		self.prevLogIndex = prevLogIndex
		self.prevLogTerm = prevLogTerm
		self.entries = entries
		self.commitIndex = commitIndex

class ResponseAppendEntry:
	def __init__(self, req_type, pid, term, success):
		self.term = term
		self.pid = pid
		self.req_type =req_type
		self.success = success

class ClientState:
	def __init__(self, pid, port_mapping):
		self.pid = pid
		self.port_mapping = port_mapping
		self.curr_leader = 0
		self.curr_term = 0
		self.curr_state = "FOLLOWER"
		self.last_recv_time = time.time()		
		self.votedFor = 0
		self.logs = [LogEntry(0,0,"msg")]
		self.commitIndex = 0
		self.activeLink = {1: False, 2: False, 3: False, 4: False, 5: False}
		self.voteCounts = {}
		self.leaderHeartbeat = time.time()
		self.nextIndex = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
		self.logEntryCounts = {}
		self.publicKeys = {}
		self.privateKey = None

class ClientMessage:
	def __init__(self, req_type, message):
		self.req_type = req_type
		self.message = message

class NetworkLink:
	def __init__(self, req_type, src, dest):
		self.req_type = req_type
		self.src = src
		self.dest = dest

