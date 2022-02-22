class LogEntry:
	def __init__(self, term, index, message):
		self.term = term
		self.index = index
		self.message = message

class Persistent:
	def __init__(self):
		self.currentTerm = 0
		self.votedFor = 0
		self.logs = []

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

class AppendEntryResponse:
	def __init__(self, req_type, term, success):
		self.term = term
		self.req_type =req_type
		self.success = success

class ClientState:
	def __init__(self, pid, port_mapping):
		self.pid = pid
		self.port_mapping = port_mapping
		self.curr_leader = 1
		self.curr_term = 1
		self.curr_state = "FOLLOWER"
		self.last_recv_time = 0		
		self.votedFor = 0
		self.logs = []
		self.activeLink = {1: True, 2: True, 3: True, 4: True, 5: True}