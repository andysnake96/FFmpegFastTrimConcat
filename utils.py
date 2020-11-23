#!/usr/bin/python3
###Vid metadata gen--parse
from json import load, loads, dumps
from multiprocessing.dummy import Pool
from subprocess import run
from random import shuffle
from sys import stderr


def to_tuple(lst):
    """convert the given list to a tuple recursivelly"""""
    for r in range(len(lst)):
        i=lst[r]
        if isinstance(i,list):      lst[r]= to_tuple(i)
        elif isinstance(i,tuple):   lst[r]= to_tuple(list(i))
        elif isinstance(i,dict):    lst[r]=tuple(i.items())
    return tuple(lst)

def ffprobeMetadataGen(vidPath, FFprobeJsonCmd="ffprobe -v quiet -print_format json -show_format -show_streams -show_error"):
    """generate metadata for item  at given path with subprocess.run
        @return: vid size, streams'metadata dictionaries (with vid stream at 0th pos), vid duration in secods (float), metdata generated frmo ffprobe
    """
    FFprobeJsonCmdSplitted = FFprobeJsonCmd.split(" ") + [vidPath]
    out = run(FFprobeJsonCmdSplitted, capture_output=True)
    metadataFull = loads(out.stdout.decode())
    if metadataFull.get("error")!=None and ["error"]!=None and len(metadataFull)==1: 
        print("error at ",vidPath,file=stderr);return None,None,None,None
    return (*extractMetadataFFprobeJson(metadataFull),metadataFull)     #python3 required


def extractMetadataFFprobeJson(metadata):
    """
    @param metadata: list of stream's metadata dictionary
    @return: vid size, streams'metadata dictionaries (with vid stream at 0th pos), vid duration in secods (float), metdata generated frmo ffprobe
            None,None,None if misformed metadata
    """
    try:
        fileSize = int(metadata["format"]["size"])
        streamsDictMetadata = metadata["streams"]
        # make sure video stream is at the first position in metadata.streams
        for s in range(len(streamsDictMetadata)):
            if "video" in streamsDictMetadata[s]["codec_type"].lower() and s != 0:  # swap vid stream at 0th pos
                streamsDictMetadata[0], streamsDictMetadata[s] = streamsDictMetadata[s], streamsDictMetadata[0]
                break
        dur = streamsDictMetadata[0].get("duration", 0)
        return fileSize, streamsDictMetadata, float(dur)
    except Exception as e:
        print("Misformed metdata",e,file=stderr)
        return 0,None,None


def parseMultimedialStreamsMetadata(fname):
    """
    @param fname: vid file name of json serialized metadata from ffprobe (list of streas metadata)
    @return: vid size, streams'metadata dictionaries (with vid stream at 0th pos), vid duration in secods (float)
    """
    fileMetadata = open(fname)
    metadata = load(fileMetadata)
    fileMetadata.close()
    return extractMetadataFFprobeJson(metadata)


def parseTimeOffset(timeStr, convertToSec=False):
    """
    parse time specification string (valid for ffmpeg), validating it, eventually converting it to seconds
    @param timeStr: time string like [HH]:MM:SS.dec. If not in the given format excpetion raied
    @param convertToSec: if True @param timeStr parsed and converted to seconds, else just str validation
    @return: validated timeStr, if convertToSec string converted to second
    """
    if type(timeStr) != str:  raise Exception("invalid time specification string type, expected str")
    secOffs = 0
    if ":" in timeStr:
        timeFields = timeStr.split(":")
        if len(timeFields) not in [1, 2, 3]:
            raise Exception("invalid num of time fields in the time specification string, expected[HH]:[mm]:sec")
        
        for f in range(len(timeFields)):    #convert to second
            field = timeFields[len(timeFields) - 1 - f]  # secs, min, hour field of timeStr
            if f == 0: secOffs += (float(field))#sec
            else:      secOffs += ((60 ** f) * float(field))# min||hour
    else:        secOffs= float(timeStr) #just ammount of seconds given 

    if not convertToSec: return timeStr
    return secOffs


### worker pool functions
def _stabMapFunc(args):  
    # stub to call a function with @args, unpacked if list
    
    item, function, errStr = args
    try:
        if type(item)==type(tuple()):    out = function(*item)
        else:                            out = function(item)
    except Exception as e:
        print(errStr , " " , item, e)
        out = None
    return out
def concurrentPoolProcess(workQueue, function, errStr, poolSize, poolStart=None):
    """
    concurrently with a worker pool apply function to workQueue, using an errStr if error occurr
    @param workQueue: args list where to apply function concurrently
    @param function:  func args(if list unpacked in _stabMapFunc) -> out to apply concurrently
    @param errStr:    err str to print if some exception ryse during the functions evaluation
    @param poolStart: previusly created worker pool to reuse
    @return: iterable of either [(function(target)] or None if error occurred
    """
    pool = poolStart
    if poolStart == None:    pool = Pool(poolSize)
    mapArgs = list()
    for item in workQueue: mapArgs.append((item, function, errStr))
    out = pool.map(_stabMapFunc, mapArgs)  # TODO PARTITIONIING MANUAL?
    if poolStart == None:   #also close if not reused previous pooNoneNoneNoneNoneNonel
        pool.close()
        pool.terminate
        pool.join()
    return out
######
printList = lambda l: list(map(print, l))  # basic print list, return [None,...]

def truncString(longStr,prefixToShow=9,suffixPatternToShowSep="/"):
    if longStr==None:                  return ""
    elif len(longStr)<=2*prefixToShow: return longStr
    
    endPattern=longStr[-prefixToShow:]
    if suffixPatternToShowSep!=None and longStr.find(suffixPatternToShowSep) != -1:
        endPattern=longStr.split(suffixPatternToShowSep)[-1]
    return longStr[:prefixToShow]+"..."+endPattern

TurtleImported=False
def drawSegmentsTurtle(itemSegmentList, SCREEN_W=400, LINE_WIDTH_SEG=3, SEGS_FNAME=None):
    """
    draw a line on canvas s.t. a part in green for each segment allocated, the rest in black
    each new line will be drawn down of 2 unit
    the size of each line will be proportional to corresponding element normalized to the longest item
    @param itemSegmentList: Vid item list with cutpoints list fild avaible
    @param SCREEN_W: width of turtle screen alocated
    @param LINE_WIDTH_SEG:  width of each segments drawed in each line
    @param SEGS_FNAME:  if not None: path of file where save turtle screen with drawed segments in .eps file (dflt None)
    """
    import turtle
    sc = turtle.Screen()
    turtle.tracer(0, 0)
    LINE_SIZE = 15
    SCREEN_H = len(itemSegmentList * LINE_SIZE)
    SCREEN_PADDING_X, SCREEN_PADDING_Y = 8, 8
    FONT = ("Arial", 6, "normal")
    sc.setup(SCREEN_W + SCREEN_PADDING_X, SCREEN_H + SCREEN_PADDING_Y)
    sc.setworldcoordinates(0, SCREEN_H,  SCREEN_W,0)  # coordinate of standard paper to start drawing from the top
    END_X = SCREEN_W
    turtle.setpos(SCREEN_PADDING_X / 2,
                  SCREEN_PADDING_Y / 2)  # start position at top left moved of half padding in both x , y
    turtle.speed(0)
    maxDur = max([i.duration for i in itemSegmentList])
    turtle.up()
    for item in itemSegmentList:
        # item duration line draw
        turtle.down()
        pos = turtle.pos()  # start of item's line
        turtle.color("black")
        turtle.width(1)
        turtle.forward((item.duration / maxDur) * SCREEN_W)  # draw the duration line (not yet segments)
        # item segments draw
        turtle.setpos(pos)  # reset to the start of curr line to draw segments
        turtle.color("green")
        turtle.width(LINE_WIDTH_SEG)
        for s in item.cutPoints:
            if type(s[0]) == str: s[0] = parseTimeOffset(s[0], True)
            if type(s[1]) == str: s[1] = parseTimeOffset(s[1], True)
            # seek at segment start then draw the segment with pen down up to seg end
            turtle.up()
            turtle.forward((((s[0]) / maxDur) * SCREEN_W))
            turtle.down()
            turtle.forward(((s[1] - s[0]) / maxDur) * SCREEN_W)
        # move down for next line
        turtle.up()
        turtle.setpos(pos)
        turtle.sety(pos[1] + LINE_SIZE)
    # save rappresentation of  segments generated and freeze image
    if SEGS_FNAME != None: turtle.getscreen().getcanvas().postscript(file=SEGS_FNAME)
    turtle.done()
    turtle.Terminator()
    #turtle.update()

def vidItemsSorter(itemsSrc, sortMethod):
    if sortMethod == "duration":
        itemsSrc.sort(key=lambda x: float(x.duration), reverse=True)
    elif sortMethod == "size":
        itemsSrc.sort(key=lambda x: int(x.sizeB), reverse=True)
    elif sortMethod == "sizeName":
        itemsSrc.sort(key=lambda x: (x.nameID, int(x.sizeB)), reverse=True)
    elif sortMethod == "nameID":
        itemsSrc.sort(key=lambda x: x.nameID)
    elif sortMethod == "shuffle":
        shuffle(itemsSrc)
    else:
        raise Exception("not founded sorting method")


def cleanPathname(name, disableExtensionForce=False, extensionTarget=".mp4"):
    #clean pathName return it like 'XXXXX.extensionTarget'
    if len(name)<3: return
    if name[0]!="'": name="'"+name
    if name[-1]!="'": name=name+"'"
    if not disableExtensionForce and extensionTarget not in name:
        name=name[:-1]+extensionTarget+"'"
    return name

if __name__=="__main__":
    ## FULL COVERAGE AUTO FUNCS CALL
    import sys
    thismodule = sys.modules[__name__]
    emptyF=lambda x:x
    print("module attributes")
    for x in dir(): print(x,type(getattr(thismodule,x)))
    print("calling all functions")
    functions=[getattr(thismodule,x) for x in dir() if type(getattr(thismodule,x)) == type(emptyF)]
    for f in functions: 
        try: f()
        except: print()

#var
printList = lambda l: list(map(print, l))  # basic print list, return [None,...]
