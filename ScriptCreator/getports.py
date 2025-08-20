import pywinctl as pwc

def getNames():
    titles = pwc.getAllTitles()
    return titles

### Returns all of the current ports with names of the characters associated with it
def returnAllPorts():
    ports = []
    for title in getNames():
        if "] - Phoenix Bot:" in title:
            splitTitle = title.split()
            name = splitTitle[2].replace("]", "")
            port = splitTitle[5].replace("Bot:", "")
            pid = pwc.getWindowsWithTitle(title)[0].getPID()
            ports.append([name, port, pid])

    return ports

### returns only 1 port
def returnCorrectPort(playerName):
    allPorts = returnAllPorts()
    for i in range(len(allPorts)):
        if playerName in allPorts[i]:
            return int(allPorts[i][1])

def returnCorrectPID(playerName):
    allPorts = returnAllPorts()
    for entry in allPorts:
        if playerName in entry:
            return int(entry[2])
