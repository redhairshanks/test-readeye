
def main():
	f = open("eyevalues.txt", "r")
	lines = f.readlines()
	for line in lines:
		splitter = line.split(' ')
		if len(splitter) == 3:
			print("clock = %s | x = %s | y = %s" % (splitter[0], splitter[1], splitter[2]))
	f.close()

if __name__ == '__main__':
    main()