#!/usr/bin/env python
import logging
import os
import subprocess
import sys
import glob
import re

import time
import datetime
import math

from binascii import a2b_base64

from itertools import chain

import tornado.web
import tornado.websocket
import tornado.httpserver
import tornado.ioloop
import tornado.log
import tornado.escape

import json, csv, urllib
import numpy as np

from videoProcessing import readImageRGBA,loadScreenCapVideo,writeScreenCapOutputFrames,openScreenCapOutVideo,\
    closeScreenCapOutVideo,sendVideoFrame,sendVideoEnd
import global_variables
from participant import ParticipantData,TobiiData,sendParticipantInfo,ParticipantVideo,newParticipant

# TODO
# - Check Aaron's timestamps
# - Fix screen cap write out

# Where are we putting the output?
outputPrefix = "../FramesDataset/"

# Video frame extraction parameters
frameExtractFormat = "frame_{:08d}.png"
frameOutFormat = "frame_{:08d}_{:08d}.png"

# CSV File names
csvTempName = "gazePredictions.csv"
csvDoneName = "gazePredictionsDone.csv"

# Participant characteristics file
writeCSV = True

##################################################################
# Creating custom logger for CollectionHandler
collectionLogger = logging.getLogger('collection_logger')
collectionLogger.setLevel(logging.INFO)
collectionFileHandler = ""

def open_log_handler(ffile):
    with open(ffile, 'w') as fp:
        pass
    collectionFileHandler = logging.FileHandler(ffile)
    collectionFileHandler.setLevel(logging.INFO)
    collectionFormatter = logging.Formatter('%(message)s')
    collectionFileHandler.setFormatter(collectionFormatter)
    collectionLogger.addHandler(collectionFileHandler)
    collectionLogger.propagate = False

def close_log_handler(ffile):
    collectionLogger.removeHandler(collectionFileHandler)
    


##################################################################
# CSV header object field names
fmPosKeys = ['fmPos_%04d' % i for i in range(0, 468)]
eyeFeaturesKeys = ['eyeFeatures_%04d' % i for i in range(0, 120)]
fieldnames = (['participant','frameImageFile','frameTimeEpoch','frameNum','mouseMoveX','mouseMoveY',
               'mouseClickX','mouseClickY','keyPressed','keyPressedX','keyPressedY',
               'tobiiLeftScreenGazeX','tobiiLeftScreenGazeY','tobiiRightScreenGazeX','tobiiRightScreenGazeY',
               'webGazerX','webGazerY','error','errorPix'])
fieldnames.extend( fmPosKeys )
fieldnames.extend( eyeFeaturesKeys )


######################################################################################
# Processors for messages

# p = participant
def writeDataToCSV( p, msg ):

    ###########################################################################################################
    # Store current WebGazer prediction from browser
    global_variables.wgCurrentX = float( msg["webGazerX"] )
    global_variables.wgCurrentY = float( msg["webGazerY"] )
    wgError = float( msg["error"] )
    wgErrorPix = float( msg["errorPix"] )


    ###########################################################################################################
    # Find the closest Tobii timestamp to our current video timestamp
    #
    # As time only goes forwards, tobiiListPos is a counter which persists over GET requests.
    # The videos arrive in non-chronological order, however, so we have to reset tobiiListPos on each new video
    frameTimeEpoch = int( msg["frameTimeEpoch"] )
    while p.tobiiListPos < len(p.tobiiList)-2 and frameTimeEpoch - p.tobiiList[p.tobiiListPos].timestamp > 0:
        p.tobiiListPos = p.tobiiListPos + 1

    if p.tobiiListPos == len(p.tobiiList):
        # We've come to the end of the list and there are no more events...
        print( "Error: at end of Tobii event list; no matching timestamp" )
        global_variables.tobiiCurrentX = -1
        global_variables.tobiiCurrentY = -1
    else:
        # TobiiList
        diffCurr = frameTimeEpoch - p.tobiiList[p.tobiiListPos].timestamp
        diffNext = frameTimeEpoch - p.tobiiList[p.tobiiListPos+1].timestamp

        # Pick the one which is closest in time
        if abs(diffCurr) < abs(diffNext):
            td = p.tobiiList[p.tobiiListPos]
        else:
            td = p.tobiiList[p.tobiiListPos+1]

        # Check validity for return value
        if td.rightEyeValid == 1 and td.leftEyeValid == 1:
            global_variables.tobiiCurrentX = (td.leftScreenGazeX + td.rightScreenGazeX) / 2.0
            global_variables.tobiiCurrentY = (td.leftScreenGazeY + td.rightScreenGazeY) / 2.0
        elif td.rightEyeValid == 1 and td.leftEyeValid == 0:
            global_variables.tobiiCurrentX = td.rightScreenGazeX
            global_variables.tobiiCurrentY = td.rightScreenGazeY
        elif td.rightEyeValid == 0 and td.leftEyeValid == 1:
            global_variables.tobiiCurrentX = td.leftScreenGazeX
            global_variables.tobiiCurrentY = td.leftScreenGazeY
        else:
            # Neither is valid, so we could either leave it as the previous case,
            # which involves doing nothing, or set it to -1.
            global_variables.tobiiCurrentX = -1
            global_variables.tobiiCurrentY = -1

    ###################################################
    # Work out what to write out to CSV
    out = msg
    del out['msgID']
    out['participant'] = p.directory
    pv = p.videos[p.videosPos]
    out['frameImageFile'] = pv.frameFilesList[ pv.frameFilesPos ]
    
    out["tobiiLeftScreenGazeX"] = td.leftScreenGazeX
    out["tobiiLeftScreenGazeY"] = td.leftScreenGazeY
    out["tobiiRightScreenGazeX"] = td.rightScreenGazeX
    out["tobiiRightScreenGazeY"] = td.rightScreenGazeY

    out['error'] = wgError
    out['errorPix'] = wgErrorPix

    # Turn fmPos and eyeFeatures into per-column values
    fmPosDict = dict(zip( fmPosKeys, list(chain.from_iterable( out["fmPos"] )) ) )
    eyeFeaturesDict = dict(zip( eyeFeaturesKeys, out["eyeFeatures"] ))
    out.update( fmPosDict )
    out.update( eyeFeaturesDict )
    del out['fmPos']
    del out['eyeFeatures']

    if writeCSV:

        # A reminder of what the desired field name outputs are.
        # fieldnames = (['participant','frameImageFile','frameTimeEpoch','frameNum','mouseMoveX','mouseMoveY','mouseClickX','mouseClickY','keyPressed','keyPressedX','keyPressedY',
        #                'tobiiLeftScreenGazeX','tobiiLeftScreenGazeY','tobiiRightScreenGazeX','tobiiRightScreenGazeY','webGazerX','webGazerY','fmPos','eyeFeatures','wgError','wgErrorPix'])

        # Target dir for output
        outDir = outputPrefix + global_variables.participant.directory + '/' + \
            global_variables.participant.videos[global_variables.participant.videosPos].filename \
            + "_frames" + '/'
        # Target gaze predictions csv
        gpCSV = outputPrefix + global_variables.participant.directory + '_'  + pv.filename + '_' + csvTempName 

        with open( gpCSV, 'a', newline='' ) as f:
            # Note no quotes between fmTracker and eyeFeatures
            # f.write( "\"" + participant.directory + "\",\"" + fname + "\",\"" + str(frameTimeEpoch) + "\",\"" + str(frameNum) + "\",\"" + str(mouseMoveX) + "\",\"" + str(mouseMoveY) + "\",\"" + str(mouseClickX) + "\",\"" + str(mouseClickY) + "\",\"" + keyPressed + "\",\"" + str(keyPressedX) + "\",\"" + str(keyPressedY) + "\",\"" + str(td.leftScreenGazeX) + "\",\"" + str(td.leftScreenGazeY) + "\",\"" + str(td.rightScreenGazeX) + "\",\"" + str(td.rightScreenGazeY) + "\",\"" + str(wgCurrentX) + "\",\"" + str(wgCurrentY) + "\"," + str(fmPos) + "," + str(eyeFeatures) + "\n")
            writer = csv.DictWriter(f, fieldnames=fieldnames,delimiter=',',quoting=csv.QUOTE_ALL)
            writer.writerow( out )

    return frameTimeEpoch

################################################################################################

class WebSocketHandler(tornado.websocket.WebSocketHandler):

    def open(self):

        global_variables.participantPos = -1
        newParticipant( self )

 
    def on_message(self, message):
        #######################################################################################
        # Video requested from client
        # 
        msg = tornado.escape.json_decode( message )
        if msg['msgID'] == '1':
            
            #######################################
            # Extract video frames and find timestamps
            # TODO: Refactor, but be careful. Prickly code
            #
            global_variables.participant.videosPos = global_variables.participant.videosPos + 1
            pv = global_variables.participant.videos[global_variables.participant.videosPos]
            video = global_variables.participant.directory + '/' + pv.filename
            print( "Processing video: " + video )

            #
            # Make dir for output video frames
            outDir = outputPrefix +  video + "_frames" + '/'
            if not os.path.isdir( outDir ):
                os.makedirs( outDir )


            # We may have already processed this video...
            gpCSVDone = outputPrefix + global_variables.participant.directory + '_' + pv.filename + '_' + csvDoneName
            gpCSV = outputPrefix + global_variables.participant.directory + '_'  + pv.filename + '_' + csvTempName
            if os.path.isfile(gpCSVDone ):
                print( "    " + gpCSVDone + " already exists and completed; moving on to next video...")
                sendVideoEnd( self )
                return
            elif os.path.isfile( gpCSV ):
                print( "    " + gpCSV + " exists but does not have an entry for each file; deleting csv and starting this video again...")
                os.remove(gpCSV)

                # Write the header for the new gazePredictions.csv file
                if writeCSV:
                    with open(gpCSV, 'w', newline='' ) as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames,delimiter=',',quoting=csv.QUOTE_ALL)
                        writer.writeheader()            

            # If we're not done, we need to extract the video frames (using ffmpeg).
            # If this is already done, we write 'framesExtracted.txt'
            #
            framesDoneFile = outDir + '/' + "framesExtracted.txt"
            if not os.path.isfile( framesDoneFile ):
                print( "    Extracting video frames (might take a few minutes)... " + str(video) )
                completedProcess = subprocess.run('ffmpeg -i "./' + video + '" -vf showinfo "' + outDir + 'frame_%08d.png"'\
                    , stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, shell=True)

                nFrames = len(glob.glob( outDir + '*.png' ))
                if nFrames == 0:
                    print( "    Error extracting video frames! Moving on to next video..." )
                    sendVideoEnd( self )
                    return

                # Collect the timestamps of the video frames
                allPts = np.ones(nFrames, dtype=np.int64) * -1
                ptsTimebase = -1
                framerate = -1
                lines = completedProcess.stderr.splitlines()
                for l in lines:
                    if l.startswith( "[Parsed_showinfo_0 @" ):
                        timebase = l.find( "config in time_base:" )
                        fr = l.find( ", frame_rate:" )
                        nStart = l.find( "n:" )
                        ptsStart = l.find( "pts:" )
                        pts_timeStart = l.find( "pts_time:" )
                        if nStart >= 0 and ptsStart >= 0:
                            frameNum = int(l[nStart+2:ptsStart-1].strip())
                            pts = int(l[ptsStart+4:pts_timeStart].strip())
                            allPts[frameNum] = pts
                        elif timebase >= 0:
                            ptsTimebase = l[timebase+20:fr].strip()
                            framerate = l[fr+13:].strip()
                            sl = framerate.find("/")
                            if sl > 0:
                                frPre = framerate[0:sl]
                                frPost = framerate[sl+1:]
                                framerate = float(frPre) / float(frPost)
                            else:
                                framerate = float(framerate)

                            if ptsTimebase != "1/1000":
                                print( "ERROR ERROR Timebase in webm is not in milliseconds" )
                    # if l.startswith( "frame=" ):
                        # This is written out at the end of the file, and looks like this:
                        # frame=  454 fps= 51 q=24.8 Lsize=N/A time=00:00:15.13 bitrate=N/A dup=3 drop=1 speed=1.71x -  refers to decoding 

                # Some of the presentation times (pts) will not have been filled in, and will be -1s
                # Let's just assume the framerate is good (yea right) and add on the frame time to the last good
                prev = 0
                for i in range(0, nFrames):
                    if allPts[i] == -1:
                        allPts[i] = prev + int(1000/framerate)
                    prev = allPts[i]
                
                # TODO Write out this data to a pts file?

                # Rename the files based on their frame number and timestamp
                for i in range(0, nFrames):
                    inputFile = outDir + frameExtractFormat.format(i+1) # Catch that the output framenumbers from extraction start from 1 and not 0
                    outputFile = outDir + frameOutFormat.format(i, allPts[i])
                    os.rename( inputFile, outputFile )
                    
                
                with open( framesDoneFile, 'w' ) as f:
                    f.write( "Done." )


            # Populate list with video frames
            pv.frameFilesList = sorted(glob.glob( outDir + '*.png' ))
            pv.frameFilesPos = 0
            

            ########################################
            # Send the first video frame + timestamp
            #
            sendVideoFrame( self, pv.frameFilesList[pv.frameFilesPos], pv )
        # 
        # End NEW VIDEO
        #######################################################################################
        

        #######################################################################################
        # Feedback from CLIENT which contains the webgazer + interaction metadata we need...
        # 
        elif msg['msgID'] == '3':
            # Parse, manipulate the data and write to CSV
            frameTimeEpoch = writeDataToCSV( global_variables.participant, msg )

            if global_variables.writeScreenCapVideo:
                writeScreenCapOutputFrames( global_variables.participant, frameTimeEpoch )

            ##################################
            # Send the next frame of the video
            pv = global_variables.participant.videos[global_variables.participant.videosPos]
            pv.frameFilesPos = pv.frameFilesPos + 1
            
            # If the video frame is the last available video frame, send a message to this effect
            if pv.frameFilesPos >= len(pv.frameFilesList):

                if global_variables.writeScreenCapVideo:
                    closeScreenCapOutVideo( global_variables.participant )

                outDir = outputPrefix + global_variables.participant.directory + '/' + pv.filename + "_frames" + '/'
                gpCSV = outputPrefix + global_variables.participant.directory + '_' + pv.filename +'_' + csvTempName 
                gpCSVDone = outputPrefix + global_variables.participant.directory + '_'  + pv.filename + '_' + csvDoneName
                if os.path.isfile( gpCSV ):
                    os.rename( gpCSV, gpCSVDone )

                sendVideoEnd( self )

            else:
                sendVideoFrame( self, pv.frameFilesList[pv.frameFilesPos], pv )


    def on_close(self):
        pass

################################################################################################

# CollectionWrite listens on localhost:8000/collection
# Set check_origin to return True for cross site access

class CollectionWriter:

    def file_write(self, msg):
        collectionLogger.info(msg)

    def read_eyevalues(self, ffile, socket_server):
        # Initialize the lists for X and Y values
        x_values = []
        y_values = []

        # Open the file and read the lines
        with open(ffile, 'r') as file:
            lines = file.readlines()
            # Skip the first line (header)
            for line in lines[1:]:
                values = line.split()
                if len(values) == 2:  # Split each line into values
                    x_values.append(float(values[0]))  # Append the X value
                    y_values.append(float(values[1]))  # Append the Y value

        # Calculate and print the average standard deviation
        x_std_dev = np.std(x_values)
        y_std_dev = np.std(y_values)
        avg_std_dev = (x_std_dev + y_std_dev) / 2
        print(f'Average standard deviation: {avg_std_dev}')
        self.clear_files(ffile, socket_server)
        socket_server.write_message({"percentage" : avg_std_dev})

    def clear_files(self, ffile , socket_server):
        close_log_handler(ffile)
        # current_filename = os.getcwd() + "/eyevalues.txt"
        # with open(current_filename, 'w') as fp:
        #     pass
        # timestamped_filename = os.getcwd() + "/" + time.strftime("%Y%m%d-%H%M%S") + ".log"
        # os.rename(current_filename, timestamped_filename)
        socket_server.new_log_file = True
    

class CollectionSocketHandler(tornado.websocket.WebSocketHandler):

    def open(self):
        self.collectionWrite = CollectionWriter()
        self.new_log_file = True
        self.timestamped_filename = ''
        print("Open for collection x,y coordinates from calibration and collision")

    def check_origin(self, origin):
        return True    

    def on_message(self, message):
        msg, formatted_msg = {}, ""
        if message:
            msg = tornado.escape.json_decode( message )
            if msg.get('type') in ["calibration", "collision", "readtext"]:
                if self.new_log_file:
                    self.timestamped_filename = os.getcwd() + "/" + time.strftime("%Y%m%d-%H%M%S") + ".log"
                    open_log_handler(self.timestamped_filename)
                    self.new_log_file = False
                formatted_msg = self.format_msg(msg)
                print(formatted_msg)
                if formatted_msg:    
                    self.collectionWrite.file_write(formatted_msg) 
            else:
                print("finished recieved")
                self.collectionWrite.read_eyevalues(self.timestamped_filename, self)
        
    def on_close(self):
        pass

    def format_msg(self, msg):
        # return "%sms %s %s\n" % (msg.get("clock"), msg.get("x"), msg.get("y")) 
        return "%s %s\n" % (msg.get("x"), msg.get("y")) 


################################################################################################        

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r'/websocket', WebSocketHandler),
            (r'/collection', CollectionSocketHandler),
            (r'/(.*)', tornado.web.StaticFileHandler, {'path': '.', 'default_filename': ''}),
        ]
 
        settings = {
            'template_path': 'templates'
        }
        tornado.web.Application.__init__(self, handlers, **settings)


def main():
    global_variables.init()

    ###########################################################################################################
    # Enumerate all P_ subdirectories if not yet done
    regex = re.compile('P_[0-9][0-9]')

    
    global_variables.participantDirList = []
    for root, dirs, files in os.walk('.'):
        for d in dirs:
            if regex.match(d):
               global_variables.participantDirList.append(d)

    global_variables.participantDirList = sorted( global_variables.participantDirList )

    # NOTE: This would be the point to filter any participants from the processing

    ###########################################################################################################
    # Setup webserver
    #
    listen_address = ''
    listen_port = 8000
    try:
        if len(sys.argv) == 2:
            listen_port = int(sys.argv[1])
        elif len(sys.argv) == 3:
            listen_address = sys.argv[1]
            listen_port = int(sys.argv[2])
        assert 0 <= listen_port <= 65535
    except (AssertionError, ValueError):
        raise ValueError('Port must be a number between 0 and 65535')

    args = sys.argv
    args.append("--log_file_prefix=myapp.log")
    tornado.log.enable_pretty_logging()
    tornado.options.parse_command_line(args)
    
    ws_app = Application()
    #http_server = tornado.httpserver.HTTPServer(ws_app)
    http_server = tornado.httpserver.HTTPServer(ws_app, ssl_options={
        "certfile": "cert.pem",
        "keyfile": "privkey.pem",
    })
    http_server.listen(listen_port)

    # Logging
    logging.info('Listening on %s:%s' % (listen_address or '[::]' if ':' not in listen_address else '[%s]' % listen_address, listen_port))
    # [James]
    # Uncomment these lines to suppress normal webserver output
    #logging.getLogger('tornado.access').disabled = True
    #logging.getLogger('tornado.application').disabled = True
    #logging.getLogger('tornado.general').disabled = True

    # Message
    print( "WebGazer ETRA2018 Dataset Extractor server started; please open http://localhost:8000/webgazerExtractClient.html" )

    #################################
    # Start webserver
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()
