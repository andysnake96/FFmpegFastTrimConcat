#!/usr/bin/python3
###Vid metadata gen--parse
from configuration import CONF,TMP_NOFULLVID

from json import load, loads, dumps
from multiprocessing.dummy import Pool
from subprocess import run
from random import shuffle
from sys import stderr


##probe helper
def ffprobeMetadataGen(vidPath, FFprobeJsonCmd="ffprobe -v quiet -print_format json -show_format -show_streams -show_error"):
    """generate metadata for item  at given path with subprocess.run
        @return: vid size, streams'metadata dictionaries (with vid stream at 0th pos), vid duration in secods (float), metdata generated frmo ffprobe
    """
    FFprobeJsonCmdSplitted = FFprobeJsonCmd.split(" ") + [vidPath]
    out = run(FFprobeJsonCmdSplitted, capture_output=True)
    metadataFull = loads(out.stdout.decode())
    if metadataFull.get("error")!=None and ["error"]!=None and len(metadataFull)==1: 
        print("error at ",vidPath,metadataFull ,file=stderr);return None,None,None,None
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

##ffmpeg's time spec conversion
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
    #size sort down to 0 if NO FULL VIDEO AVAIBLE 
    elif sortMethod == "size":
        itemsSrc.sort(key=lambda x: x.sizeB-x.sizeB*x.pathName.count(TMP_NOFULLVID), reverse=True)
    elif sortMethod == "sizeName":
        itemsSrc.sort(key=lambda x: (x.nameID,x.sizeB-x.sizeB*x.pathName.count(TMP_NOFULLVID)), reverse=True)

    elif sortMethod == "nameID":    itemsSrc.sort(key=lambda x: x.nameID)
    elif sortMethod == "segsReady&Size": itemsSrc.sort(key=lambda x: (len(x.segPaths),x.sizeB),reverse=True)
    elif sortMethod == "shuffle":   shuffle(itemsSrc)
    else:raise Exception("not founded sorting method")

##support var
def cleanPathname(name, disableExtensionForce=False, extensionTarget=".mp4"):
    #clean pathName return it like 'XXXXX.extensionTarget'
    if len(name)<3: return
    if name[0]!="'": name="'"+name
    if name[-1]!="'": name=name+"'"
    if not disableExtensionForce and extensionTarget not in name:
        name=name[:-1]+extensionTarget+"'"
    return name

lastPartPath=lambda fpath: fpath.split("/")[-1]

def unrollDictOfList(d):
    #return concat of lists as d's values
    out=list()
    for x in list(d.values()): out.extend(x)
    if CONF["DEBUG"]: print("unrolled:",len(out))
    return out

def to_tuple(lst):
    """convert the given list to a tuple recursivelly"""""
    for r in range(len(lst)):
        i=lst[r]
        if isinstance(i,list):      lst[r]= to_tuple(i)
        elif isinstance(i,tuple):   lst[r]= to_tuple(list(i))
        elif isinstance(i,dict):    lst[r]=tuple(i.items())
    return tuple(lst)

nnEmpty=lambda field: field!=None or field!=0
def isNamedtuple(obj): #check if obj is a std object using vars() builtin
    isTuple=False
    try:    vars(obj)
    except: isTuple=True
    return isTuple


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

##COLORED TERM TEXT
CRED= '\33[31m';CBLUEBG= '\33[44m';CEND= '\33[0m';CBOLD= '\33[1m'
BEST_HIGHLIGHT=CRED+CBOLD+CBLUEBG
#print highlighted @s [dflt red color font]
hlTermPrint=lambda s,prefix=CRED,file=stderr: print(prefix+s+CEND,file=file) 
#var
printList = lambda l: list(map(print, l))  # basic print list, return [None,...]
TKINTER_COLORS= ['snow', 'ghost white', 'white smoke', 'gainsboro', 'floral white', 'old lace',
    'linen', 'antique white', 'papaya whip', 'blanched almond', 'bisque', 'peach puff',
    'navajo white', 'lemon chiffon', 'mint cream', 'azure', 'alice blue', 'lavender',
    'lavender blush', 'misty rose', 'light grey', 'midnight blue', 'navy', 'cornflower blue', 'dark slate blue',
    'slate blue', 'medium slate blue', 'light slate blue', 'medium blue', 'royal blue',
    'dodger blue', 'deep sky blue', 'sky blue', 'light sky blue', 'steel blue', 'light steel blue',
    'light blue', 'powder blue', 'pale turquoise', 'dark turquoise', 'medium turquoise', 'turquoise',
    'cyan', 'light cyan', 'cadet blue', 'medium aquamarine', 'aquamarine', 'dark green', 'dark olive green',
    'dark sea green', 'sea green', 'medium sea green', 'light sea green', 'pale green', 'spring green',
    'lawn green', 'medium spring green', 'green yellow', 'lime green', 'yellow green',
    'forest green', 'olive drab', 'dark khaki', 'khaki', 'pale goldenrod', 'light goldenrod yellow',
    'light yellow', 'yellow', 'gold', 'light goldenrod', 'goldenrod', 'dark goldenrod', 'rosy brown',
    'indian red', 'saddle brown', 'sandy brown',
    'dark salmon', 'salmon', 'light salmon', 'orange', 'dark orange',
    'coral', 'light coral', 'tomato', 'orange red', 'red', 'hot pink', 'deep pink', 'pink', 'light pink',
    'pale violet red', 'maroon', 'medium violet red', 'violet red',
    'medium orchid', 'dark orchid', 'dark violet', 'blue violet', 'purple', 'medium purple',
    'thistle', 'snow2', 'snow3',
    'snow4', 'seashell2', 'seashell3', 'seashell4', 'AntiqueWhite1', 'AntiqueWhite2',
    'AntiqueWhite3', 'AntiqueWhite4', 'bisque2', 'bisque3', 'bisque4', 'PeachPuff2',
    'PeachPuff3', 'PeachPuff4', 'NavajoWhite2', 'NavajoWhite3', 'NavajoWhite4',
    'LemonChiffon2', 'LemonChiffon3', 'LemonChiffon4', 'cornsilk2', 'cornsilk3',
    'cornsilk4', 'ivory2', 'ivory3', 'ivory4', 'honeydew2', 'honeydew3', 'honeydew4',
    'LavenderBlush2', 'LavenderBlush3', 'LavenderBlush4', 'MistyRose2', 'MistyRose3',
    'MistyRose4', 'azure2', 'azure3', 'azure4', 'SlateBlue1', 'SlateBlue2', 'SlateBlue3',
    'SlateBlue4', 'RoyalBlue1', 'RoyalBlue2', 'RoyalBlue3', 'RoyalBlue4', 'blue2', 'blue4',
    'DodgerBlue2', 'DodgerBlue3', 'DodgerBlue4', 'SteelBlue1', 'SteelBlue2',
    'SteelBlue3', 'SteelBlue4', 'DeepSkyBlue2', 'DeepSkyBlue3', 'DeepSkyBlue4',
    'SkyBlue1', 'SkyBlue2', 'SkyBlue3', 'SkyBlue4', 'LightSkyBlue1', 'LightSkyBlue2',
    'LightSkyBlue3', 'LightSkyBlue4', 'LightSteelBlue1', 'LightSteelBlue2', 'LightSteelBlue3',
    'LightSteelBlue4', 'LightBlue1', 'LightBlue2', 'LightBlue3', 'LightBlue4',
    'LightCyan2', 'LightCyan3', 'LightCyan4', 'PaleTurquoise1', 'PaleTurquoise2',
    'PaleTurquoise3', 'PaleTurquoise4', 'CadetBlue1', 'CadetBlue2', 'CadetBlue3',
    'CadetBlue4', 'turquoise1', 'turquoise2', 'turquoise3', 'turquoise4', 'cyan2', 'cyan3',
    'cyan4','aquamarine2', 'aquamarine4', 'DarkSeaGreen1', 'DarkSeaGreen2', 'DarkSeaGreen3',
    'DarkSeaGreen4', 'SeaGreen1', 'SeaGreen2', 'SeaGreen3', 'PaleGreen1', 'PaleGreen2',
    'PaleGreen3', 'PaleGreen4', 'SpringGreen2', 'SpringGreen3', 'SpringGreen4',
    'green2', 'green3', 'green4', 'chartreuse2', 'chartreuse3', 'chartreuse4',
    'OliveDrab1', 'OliveDrab2', 'OliveDrab4', 'DarkOliveGreen1', 'DarkOliveGreen2',
    'DarkOliveGreen3', 'DarkOliveGreen4', 'khaki1', 'khaki2', 'khaki3', 'khaki4',
    'LightGoldenrod1', 'LightGoldenrod2', 'LightGoldenrod3', 'LightGoldenrod4',
    'LightYellow2', 'LightYellow3', 'LightYellow4', 'yellow2', 'yellow3', 'yellow4',
    'gold2', 'gold3', 'gold4', 'goldenrod1', 'goldenrod2', 'goldenrod3', 'goldenrod4',
    'DarkGoldenrod1', 'DarkGoldenrod2', 'DarkGoldenrod3', 'DarkGoldenrod4',
    'RosyBrown1', 'RosyBrown2', 'RosyBrown3', 'RosyBrown4', 'IndianRed1', 'IndianRed2',
    'IndianRed3', 'IndianRed4', 'sienna1', 'sienna2', 'sienna3', 'sienna4', 'burlywood1',
    'burlywood2', 'burlywood3', 'burlywood4', 'wheat1', 'wheat2', 'wheat3', 'wheat4', 'tan1',
    'tan2', 'tan4', 'chocolate1', 'chocolate2', 'chocolate3', 'firebrick1', 'firebrick2',
    'firebrick3', 'firebrick4', 'brown1', 'brown2', 'brown3', 'brown4', 'salmon1', 'salmon2',
    'salmon3', 'salmon4', 'LightSalmon2', 'LightSalmon3', 'LightSalmon4', 'orange2',
    'orange3', 'orange4', 'DarkOrange1', 'DarkOrange2', 'DarkOrange3', 'DarkOrange4',
    'coral1', 'coral2', 'coral3', 'coral4', 'tomato2', 'tomato3', 'tomato4', 'OrangeRed2',
    'OrangeRed3', 'OrangeRed4', 'red2', 'red3', 'red4', 'DeepPink2', 'DeepPink3', 'DeepPink4',
    'HotPink1', 'HotPink2', 'HotPink3', 'HotPink4', 'pink1', 'pink2', 'pink3', 'pink4',
    'LightPink1', 'LightPink2', 'LightPink3', 'LightPink4', 'PaleVioletRed1',
    'PaleVioletRed2', 'PaleVioletRed3', 'PaleVioletRed4', 'maroon1', 'maroon2',
    'maroon3', 'maroon4', 'VioletRed1', 'VioletRed2', 'VioletRed3', 'VioletRed4',
    'magenta2', 'magenta3', 'magenta4', 'orchid1', 'orchid2', 'orchid3', 'orchid4', 'plum1',
    'plum2', 'plum3', 'plum4', 'MediumOrchid1', 'MediumOrchid2', 'MediumOrchid3',
    'MediumOrchid4', 'DarkOrchid1', 'DarkOrchid2', 'DarkOrchid3', 'DarkOrchid4',
    'purple1', 'purple2', 'purple3', 'purple4', 'MediumPurple1', 'MediumPurple2',
    'MediumPurple3', 'MediumPurple4', 'thistle1', 'thistle2', 'thistle3', 'thistle4',"black"]
shuffle(TKINTER_COLORS)
