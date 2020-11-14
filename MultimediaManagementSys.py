#!/usr/bin/python3
# Copyright Andrea Di Iorio 2020
# This file is part of FFmpegFastTrimConcat
# FFmpegFastTrimConcat is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# FFmpegFastTrimConcat is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with FFmpegFastTrimConcat.  If not, see <http://www.gnu.org/licenses/>.

"""
This module define a struct for videos in class Vid,VidTuple
Video struct fields:
is identified by name ID that is a truncation of the file name up to first or last "."
several field concerning metadatas and tumbnail preview 
   separatelly stored in files with the same nameID but different extension (.json,.jpg,.gif)

it's supported to store/get metadata as a json list of dict with infos per multimedial stream.
    also supported run time generation of metadata for a given video with subprocess.run method

Main Exported Function:
GetItems                ->      recursive search from a start dir, files relative to Vid items
GetGroups               ->      gruop Vids, with a groupping function
TrimSegmentsIterative   ->      play items and prompt for selection and segmentation 
________________________________________________________________________________________________________________________
ENVIRON OVERRIDE OPTIONS
DISABLE_GUI      [F] if True gui is disabled
NameIdFirstDot   [T] filename truncated to first dot to extract file nameID/extension
MIN_GROUP_SIZE   min group size, bellow that the group will be filtered away
MIN_GROUP_LEN    min group len in seconds, bellow that the group will be filtered away
POOL_TRESHOLD    [15] min jobs num to invoke pool map in place of standard map to avoid pickle/spawn/pool overhead on few data
POOL_SIZE        worker pool size
FORCE_METADATA_GEN  (dflt True) force metadata generation for items
"""
from configuration import  *
from grouppingFunctions import *
from scriptGenerator import GenTrimReencodinglessScriptFFmpeg
from utils import * #concurrentPoolProcess, parseMultimedialStreamsMetadata,ffprobeMetadataGen, parseTimeOffset,vidItemsSorter

from collections import namedtuple
from os import environ,walk,path,system
from sys import argv,stderr
from subprocess import run,Popen,DEVNULL
from argparse import ArgumentParser
from json import loads, dumps, dump
from time import perf_counter



if not DISABLE_GUI:  # try to enable GUI importing GUI module (with its tkinter dependencies ...)
    try:
        from GUI import *
        print("GUI imported")
    except Exception as e:
        print("not importable GUI module", e)
        DISABLE_GUI = True

attributes = ["nameID","pathName", "sizeB", "gifPath","imgPath","metadataPath",\
     "metadata","duration", "extension","cutPoints"]
VidTuple = namedtuple("Vid", attributes)

class Vid:
    """Video items attributes plus useful operation on an item"""
    def __init__(self, multimediaNameK,path=None):
        self.nameID = multimediaNameK  # AS UNIQUE ID -> MULTIMEDIA NAME (no path and no suffix)
        #default init of other fields
        self.pathName =path
        self.sizeB = 0
        self.gifPath = None
        self.imgPath = None
        self.metadataPath = None
        self.metadata =None #list of vid's strams metadata (ffprobe output)
        self.duration = 0  # num of secs for the duration
        self.extension = None
        #cut times for segment generation as [[start,end],...]  (support for SelectItemPlay)
        self.cutPoints = list()  

    def __str__(self):
        outS="Item: id:"+self.nameID+" path: " + truncString(self.pathName) + \
            "size: " + str(self.sizeB) + " imgPath: " + truncString(self.imgPath)
        if self.gifPath!=None: outS+=" gifPath: "+truncString(self.gifPath)
        if not AUDIT_VIDINFO: outS="Item: "+ self.nameID
        return outS

    def genMetadata(self):
        assert self.pathName!=None,"missing vid to gen metadata"
        self.sizeB,self.metadata,self.duration,metadataFull=ffprobeMetadataGen(self.pathName)
        if SAVE_GENERATED_METADATA: self.saveFullMetadata(metadataFull)
        else:                       return metadataFull

    def play(self, playBaseCmd="ffplay -autoexit -fs "):
        """play the Vid with the given playBaseCmd given """
        cmd = playBaseCmd +"'"+self.pathName+"'"
        # run(cmd.split())
        # out=Popen(cmd.split(),stderr=DEVNULL,stdout=DEVNULL)
        print("play: ", self.pathName,cmd)
        #out = Popen(cmd.split(), stderr=DEVNULL, stdout=DEVNULL)
        out = system(cmd+" 1>/dev/null 2>/dev/null &\n")

    def remove(self,confirm=True):
        #remove this item, if confirm ask confirmation onthe backed terminal
        #return True if item actually removed
        cmd = "rm "
        if self.pathName!=None: cmd+=" "+ self.pathName
        if self.imgPath!=None: cmd+=" " + self.imgPath
        if self.metadataPath!=None: cmd+=" " + self.metadataPath
        print(cmd)
        if confirm and "Y" in input(cmd+" ???(y||n)\t").upper():
            # out = Popen(cmd.split(), stderr=DEVNULL, stdout=DEVNULL).wait()
            out = run(cmd.split())
            print("rm returned:",out.returncode)
            return out.returncode==0
        return False

    def fromJson(self, serializedDict, deserializeDictJson=False):
        """
        @param  serializedDict:  dict attributes if this class
        @param  deserializeDictJson: if true serializedDict is json serialized string
        @return:current VidI object with overwritten attributes
        """
        deserializedDict = serializedDict
        if deserializeDictJson: deserializedDict = loads(serializedDict)
        for k, v in deserializedDict.items(): setattr(self, k, v)
        return self

    def saveFullMetadata(self,metadata):
        dst = self.metadataPath
        if dst == None: dst = "/tmp/" + self.pathName.split("/")[-1] + ".json"
        dstFp = open(dst, "w")

        dump(metadata, dstFp)
        dstFp.close()
    
    def toTupleList():
        return VidTuple(self.nameID,self.pathName,self.sizeB,self.gifPath,self.imgPath,\
         self.metadataPath,self.metadata,self.duration,self.extension,self.cutPoints)


### (de) serialization of Vids list
def SerializeSelectionSegments(selectedItems, filename=None):
    """
        trivial serialization given selectedItems in json using __dict__
        if filename given output will be written to file
        return serialized json string
    """
    outList = list()
    for i in selectedItems: outList.append(i.__dict__)
    serialization = dumps(outList, indent=2)
    if filename != None:
        f = open(filename, "w")
        f.write(serialization)
        f.close()
    return serialization


def DeserializeSelectionSegments(serializedItemsStr):
    """ deserialize json list of Vid.__dict__ into list of vid items"""
    deserialized = loads(serializedItemsStr)
    out = list()
    for i in deserialized:      out.append(Vid("").fromJson(i))
    print("deserialized: ", len(out), " items")
    return out

### Vid Item gather from filesystem
def extractExtension(filename, PATH_ID,nameIdFirstDot=NameIdFirstDot):
    """
    extract the extension and nameID from filename
    @param filename: filepath 
    @param PATH_ID: consider nameID=filepath without the extension, otherwise
        consider just filename without extension
    @param nameIdFirstDot:  if true nameId will be extracted up to the first Dot
    @return: extension,nameId
    """
    #extract filename from the given path
    fnameIdx = filename.rfind("/") +1  #idx of start of fname (last "/") -> expected filename without /
    fname,fpath=filename[fnameIdx:],filename
    #try 4 char extension if not "." will be founded
    extension,nameID=  fname[-4:],fname[:-4] 
    extIndx = fname.rfind(".")  # last dot
    if extIndx != -1:
        if nameIdFirstDot:  extIndx = fname.find(".")  # first dot
        nameID, extension = fname[:extIndx], fname[extIndx + 1:]
    if PATH_ID: nameID=fpath[:fnameIdx]+nameID 
    return extension, nameID


def skipFname(extension):
    """
    return True if given fname with the extracted extension don't match any
    extension of IMG , GIF, METADATA or Video 
    """
    skip = not (GIF_TUMBRL_EXTENSION in extension or \
         IMG_TUMBRL_EXTENSION in extension or METADATA_EXTENSION in extension)
    for ext in VIDEO_MULTIMEDIA_EXTENSION:
        if not skip or ext in extension:    return False
    return skip


def GetItems(rootPath=".", vidItems=dict(), PATH_ID=False,forceMetadataGen=FORCE_METADATA_GEN, limit=float("inf"), followlinks=True):
    """
    scan for vid objs from rootPathStr recursivelly
    will be builded a Vid objfor each founded group of files with the same nameID if the extension is in a defined set (see skipFname)
    from each founded vid file name will be determined a nameKey = name less extension -> see extractExtension
    files with the same nameId will populate Vid obj fields accordingly to their extensions
    metadata read/parse/generation is computed in parallel with a poll of workers if num of jobs is above POOL_TRESHOLD

    @param rootPath:     start path for the recursive vid file search
    @param vidItems:        dict of Vid items: nameID -> Vid obj (dflt empty dict). Useful to increment a previous scan
    @param PATH_ID:      item nameKey = path of the video file without the extension -> match metadata / tumbnail in same folder
    @param forceMetadataGen:force the generation of metadata of each Vidobj without metadata's fields
    @param limit:           up bound of Vid items to found (dflt inf)
    @param followlinks:     follow sym links during file search (dflt True)
    @return: updated @vidItems dict with the newly founded vids
    """
    start = perf_counter()
    doubleCounter=0
    for root, directories, filenames in walk(rootPath, followlinks=followlinks):
        for filename in filenames:
            fpath = path.join(path.abspath(root), filename)
            # extract nameKey and extension from filename, skip it if skipFname gives true
            extension, nameKey = extractExtension(fpath,PATH_ID)
            if skipFname(extension):                          continue
            # update vidItems dict with the new vid file founded
            item = vidItems.get(nameKey)
            if item == None:
                item = Vid(nameKey)
                vidItems[nameKey] = item
            # populate Vid fields with the current file informations by looking at the extension
            if GIF_TUMBRL_EXTENSION in extension:
                item.gifPath = fpath
            elif IMG_TUMBRL_EXTENSION in extension:
                item.imgPath = fpath
            elif METADATA_EXTENSION in extension:
                item.metadataPath = fpath
            else:
                if extension not in VIDEO_MULTIMEDIA_EXTENSION:
                    print("not handled extension",extension,item,file=stderr)
                    continue
                if item.pathName != None: 
                    print("already founded a vid with same nameID",item.nameID,item.pathName,\
                    fpath," ... overwriting field",file=stderr);doubleCounter+=1
                item.pathName = fpath
                item.extension=extension

            if len(vidItems) == limit:  print("reached", limit, "vid items ... breaking the recursive search");break
    missingPath= [i for i in vidItems.values() if i.pathName==None ]
    missingMetdPath= [i for i in vidItems.values() if i.metadataPath == None and i.pathName!=None ]
    metadataFilesQueue = [i for i in vidItems.values() if i.metadataPath != None and i.pathName!=None]
    print("double nameID founded: ",doubleCounter,"tot num of items founded:",len(vidItems))
    print("metadata file to read queue len:",len(metadataFilesQueue))
    if len(metadataFilesQueue) > POOL_TRESHOLD:
        # concurrent metadata files parse in order
        metadataFilesPathQueue = [i.metadataPath for i in metadataFilesQueue]
        processed = list(concurrentPoolProcess(metadataFilesPathQueue, parseMultimedialStreamsMetadata,"badJsonFormat",POOL_SIZE ))
        for i in range(len(metadataFilesQueue)):
            metadata, item = processed[i], metadataFilesQueue[i]
            if metadata == None or metadata[1]==None:
                print("None metadata at ",item.metadataPath,file=stderr);continue
            item.sizeB, item.metadata, item.duration = metadata
    else:  # sequential version if num of jobs is too little -> only pickle/spawn/... overhead in pool
        for item in metadataFilesQueue:
            item.sizeB, item.metadata, item.duration = parseMultimedialStreamsMetadata(item.metadataPath)

    if forceMetadataGen:  # generate missing metadata with run() calls -> ffprobe + parse
        metadataFilesQueue=         [ i for i in vidItems.values()  if i.metadata == None and i.pathName!= None  ]
        metadataFilesPathQueue =    [i.pathName for i in metadataFilesQueue]  # src vid files path to generate metadata
        print("metadata to gen queue len:", len(metadataFilesPathQueue))
        if len(metadataFilesQueue) > POOL_TRESHOLD:  # concurrent version
            processed = list(concurrentPoolProcess(metadataFilesPathQueue, ffprobeMetadataGen, "metadata build err",POOL_SIZE))
            # manually set processed metadata fields (pool.map work on different copies of objs)
            for i in range(len(metadataFilesPathQueue)):
                item, processedMetadata = metadataFilesQueue[i], processed[i]
                if processedMetadata != None and processedMetadata[1]!=None:    #avaible at least metadata dict
                    item.sizeB, item.metadata, item.duration,metadataFull = processedMetadata
                    if SAVE_GENERATED_METADATA: item.saveFullMetadata(metadataFull)
                else: print("invalid metadata gen at ",item.pathName,file=stderr)
        else:  # sequential version if num of jobs is too little -> only pickle/spawn/... overhead in pool
            for item in metadataFilesQueue: item.genMetadata();
    end = perf_counter()
    print("founded Vids: ", len(vidItems), "in secs: ", end - start)
    return vidItems

def ConvertItemsTuplelist(items):
    #convert Vid items to Tuplelist
    out=list()
    for i in items: out.append(i.toTupleList())
    return out

def GetGroups(srcItems=None, grouppingRule=ffmpegConcatDemuxerGroupping,startSearch=".",\
    filterTumbnail=False,filterGif=False):
    """
    group items in a dict by a custom rule
    @srcItems:    vid items list to group as dict itemNameID->item,
                  if None will be generated by a recoursive search from @startSearch
    @grouppingRule: func: vidItem->label = immutable key for groupping in dict
    @filterTumbnail: filter away vids without a tumbnail img file
    @filterGif: filter away vids without a gif preview file
    @return: items groupped in a dict: groupKey->list of vid items
    """
    groups = dict()  # groupKey->itemList
    if srcItems == None:  srcItems = list(GetItems(startSearch).values())
    for item in FilterItems(srcItems,tumbnailPresent=filterTumbnail,gifPresent=filterGif):
        try:  # add item to the group it belongs to
            itemKeyGroup = grouppingRule(item)
            if groups.get(itemKeyGroup) == None: groups[itemKeyGroup] = list()
            groups[itemKeyGroup].append(item)
        except Exception as e:
            print(e, "\tNOT ComputableGroupKey at ", item.pathName, "OTHERS GROUP")
            itemKeyGroup = "OTHERS"
            continue
    return groups

def FilterGroups(groups, minSize, mode="len"):
    """
    filter groups by items len and/or cumulative duration
    @param groups:  dict of groupK -> items
    @param minSize: min items len or cumulative items duration
    @param mode:    either len dur or both
    @return:        filtered items in dict as groups
    """
    filteredGroup=dict()
    for groupK,items in groups.items():
        keepGroup,keepGroupDur,keepGroupLen=False,False,False
        gDur=sum([i.duration for i in items])
        if (mode == "len" or mode == "both") and len(items)>=minSize:
            keepGroupLen,keepGroup=True,True
        if (mode == "dur" or mode == "both") and \
            gDur>=minSize: keepGroupDur,keepGroup=True,True
        if mode=="both":    keepGroup=keepGroupDur and keepGroupLen

        if keepGroup:        filteredGroup[groupK]=items
        elif AUDIT_MISSERR:  print("filtered group\tlen:",len(items),"dur:",gDur,file=stderr)
    return filteredGroup

def selectGroupTextMode(groups,joinGroupItems=True):
    """
    select groups of items by choosing their groupKeys
    @param groups:  dict of groupK->groupItems as list of Vids
    @param joinGroupItems: if True elements of selected groups will be joined in 1! items list
    @return: items of the selected groups, merged in 1! list if joinGroupItems True,
            otherwise separated list returned
    """
    groupItems=list(groups.items())
    groupItems.sort(key=lambda g: len(g[1]), reverse=True)
    groupKeys=[g[0] for g in groupItems]
    groupVals=[g[1] for g in groupItems]
    #show groups
    for i in range(len(groupKeys)):
        cumulativeSize, cumulativeDur = 0, 0
        for item in groups[groupKeys[i]]:
            cumulativeDur += int(item.duration)
            cumulativeSize += int(item.sizeB)
        print("\n\n::> group:", i, "numItem:", len(groups[groupKeys[i]]), \
            "cumulative Duration Sec:", cumulativeDur,"cumulativeSize MB:",cumulativeSize/2**20,\
            "\ngrouppingKey hash:",hash(groupKeys[i]), "grouppingKey ", groupKeys[i])
    out = list()
    #select
    while len(out)==0:
        selectedGroupIDs = input("ENTER EITHER GROUPS NUMBER SPACE SEPARATED,\
             ALL for all groups\t ")
        if "ALL" in selectedGroupIDs.upper(): out = groupVals
        else:
            for gid in selectedGroupIDs.split():
                if joinGroupItems:  out += groups[groupKeys[int(gid)]]
                else:               out.append(groups[groupKeys[int(gid)]])
    print("selected items: ",len(out))
    return out

def FilterItems(items, pathPresent=True,tumbnailPresent=False,gifPresent=False,\
         metadataPresent=True,durationPos=True,filterKW=FilterKW):
    """
    filter items by the optional flags passed
    @items: source items list
    @pathPresent: filter away items without pathname set  (dflt true)
    @tumbnailPresent:  filter away items without tumbnail img path set
    @metadataPresent:  filter away items without metadata dict set
    @filterKW:  list of keywords to match to item.pathName to discard vids
    @return: filtered items in a new list
    """
    outList = list()
    for i in items:
        keep=       (not pathPresent or i.pathName != None) \
                and (not tumbnailPresent or i.imgPath !=None) \
                and (not gifPresent or i.gifPath !=None) \
                and (not metadataPresent or i.metadata !=None)\
                and (not durationPos or i.duration>0)

        for kw in filterKW:
            if not keep or kw in i.pathName:
                keep=False
                break
        if keep:    outList.append(i)

        if AUDIT_MISSERR or not keep:
            if i.pathName == None:print("missing pathName at",i);continue
            if i.imgPath == None: print("Missing thumbnail at \t", i.pathName,file=stderr)
            if i.gifPath == None: print("Missing gif at \t", i.pathName,file=stderr)
            if i.metadata==None:  print("None metadata", i.metadataPath, file=stderr)
            elif i.duration <= 0 and i.metadataPath != None:
                print("invalid duration", i.duration, i.metadataPath, file=stderr)
    
    filtered=len(items)-len(outList)
    if filtered>0: print("filtered:",filtered,"items")
    return outList
######
### iterative play trim - selection of items support
def _printCutPoints(cutPoints):  # print cutPoints as string vaild for  TrimSegmentsIterative
    outStr = ""
    for seg in cutPoints:
        start, end = seg[0], seg[1]
        outStr += " start " + str(start)+" "
        if end != None: outStr += str(end)
    return outStr


def TrimSegmentsIterative(itemsList, skipNameList=None, dfltStartPoint=None, dfltEndPoint=None, RADIUS_DFLT=1.5,overwriteCutPoints=True):
    """
    iterativelly play each Vid items and prompt for  select/replay video or trim in segments by specifing cut times
    segmentation times, if given will be embedded in cutPoints of Vid as a list of [[start,end],...]
    in segmentation times can be specified an  "hole": will be split the last segment avaible among cutPoints pairs
        into 2 segs where the whole time range is removed
    @param itemsList:       Vid objects to play, select and cut with the promt cmd
    @param skipNameList:    pathnames of items not to play
    @param dfltStartPoint:  default start time for the first segment of each selected Vid
    @param dfltEndPoint:    default end time for the last segmenet (if negative added to item duration) of each selected Vid
    @param overwriteCutPoints: if True old cutPoints in the given items will be overwritten with the new defined ones
    @return:  when no more video in itemsList or quitted inputted returned tuple
        thelist of selected itmes (along with embeded cut points), list skipped items) returned
    """
    selection,skipList = list(),list()
    ## handle fix start-end of videos
    if dfltStartPoint == None: dfltStartPoint = 0  # clean
    end = dfltEndPoint
    for item in itemsList:
        if skipNameList != None and item.pathName in skipNameList: continue     #skip item
        if end == None:             end = item.duration
        elif end < 0:               end = item.duration + end

        # iteration play-selection loop
        item.play(" mpv --hwdec=auto ")
        if len(item.cutPoints)>0:
            print("curr cutPoints:\t", _printCutPoints(item.cutPoints))
            #drawSegmentsTurtle([item]) #TODO turtle.Terminator
        # Prompt String
        cmd = input("Add Vid with dur " +str(item.duration/60) + "min, size MB "+str(item.sizeB/2**20)+" to targets?? "
             "  SKIP || QUIT || DEL [start START_TIME,END_TIME] [ringRange ringCenter,[radiousNNDeflt]] [hole HOLESTART HOLEEND ]\n\t")
        if "SKIP" in cmd.upper() or cmd == "":
            skipList.append(item)
            continue
        if "Q" in cmd.upper(): return selection, skipList
        if "DEL" in cmd.upper(): item.remove(); continue
        fields = cmd.split()
        segmentationPoints = list()  # new segmentation points for the vid
        tmpSelectionBackup=open(TMP_SEL_FILE,"w")
        replay=True
        while replay:   
            replay=False
            try:
                for f in range(len(fields)):#TODO separate parsing logic for simple GUI call
                    # parse cmd fields
                    fieldCurr = fields[f].lower()
                    if "start" in fieldCurr or "s" in fieldCurr:
                        startTime, endTime = parseTimeOffset(fields[f + 1]), end  # allocate seg with given start and default end time
                        # retrieve end time if specified
                        if f + 2 < len(fields):   endTime = parseTimeOffset(fields[f + 2])
                        segmentationPoints.append([startTime, endTime])

                    elif "rr" in fieldCurr or "ringRange" in fieldCurr:  # ring range center, radious
                        radious = RADIUS_DFLT
                        center = parseTimeOffset(fields[f + 1], True)
                        if f + 2 < len(fields) and fields[f + 2].replace(".","").isdigit():   radious = float(fields[f + 2])
                        segmentationPoints.append([str(center - radious), str(center + radious)])

                    elif "hole" in fieldCurr:  # dig hole in the last seg, splitting it in 2 new segs
                        holeStart, holeEnd = parseTimeOffset(fields[f + 1]), parseTimeOffset(fields[f + 2])
                        lastSeg = [dfltStartPoint, end]
                        #cut away the specified hole in the last segment of current item
                        if len(segmentationPoints) > 0: lastSeg = segmentationPoints.pop()
                        # resulting segments from the hole splitting
                        hseg0, hseg1 = [lastSeg[0], holeStart], [holeEnd, lastSeg[1]]  # split the last seg in 2
                        segmentationPoints.append(hseg0)
                        segmentationPoints.append(hseg1)
            except Exception as e:
                print("invalid cut cmd: ", fields, "\t\t", e)
                replay=True
        item.cutPoints.extend(segmentationPoints)
        if overwriteCutPoints:
            item.cutPoints=segmentationPoints
        selection.append(item)
        #write selection to a tmp file with selected items json serialized to not lost partial selection
        tmpSelectionBackup.seek(0)
        tmpSelectionBackup.write(dumps([i.__dict__ for i in selection]))
    return selection, skipList

def argParseMinimal(args):
    # minimal arg parse use to parse optional args
    parser = ArgumentParser(
        description=__doc__ + '\nMagment of vid clips along with their metadata and tumbnails with an optional minimal GUI')
    parser.add_argument("pathStart", type=str, help="path to start recursive search of vids")
    parser.add_argument("--operativeMode", type=str, default="TUMBNAIL_MANAGMENT",choices=["TUMBNAIL_MANAGMENT", "ITERATIVE_TRIM_SELECT","CONVERT_SELECTION_FILE_TRIM_SCRIPT"],
                        help="Operating mode, TUMBNAIL_MANAGMENT(dflt, require GUI): select videos with a GUI grid view of tumbnails, ITERATIVE_TRIM_SELECT: select and trim vids 1 at time")
    parser.add_argument("--videoTrimOldSelectionFileAction", type=str, default="SKIP",choices=["SKIP","MERGE","REVISION"],
                        help="action to do with the content of the old selection file:"
                        "SKIP -> skip old selected items but append to new selection,"
                        "MERGE ->  these items with their cutpoints to the new items, then go totrim selection loop, "
                        "REVISION -> overwrite cut points of the old selected items, not search for other vids")
    parser.add_argument("--videoTrimOldSelectionFile", type=str, default=None,help="ols json serialized selection file")
    parser.add_argument("--dstCutDir", type=str, default="cuts",help="dir where to save trimmed segments, default same dir of source vids")
    parser.add_argument("--videoTrimSelectionStartTime", type=float, default=None,help="default start time for the selected video in ITERATIVE_TRIM_SELECT operating Mode")
    parser.add_argument("--videoTrimSelectionEndTime", type=float, default=None,help="default end time for the selected video in ITERATIVE_TRIM_SELECT operating Mode, if negative added to the end of current vid in selection...")
    parser.add_argument("--videoTrimSelectionOutput", type=int, default=2, choices=[0, 1, 2],
                        help="logging mode of ITERATIVE_TRIM_SELECT mode: 0 (dflt) json serialization of selected file with embeddd cut points, 1 bash ffmpeg trim script with -ss -to -c: copy -avoid_negative_ts (commented rm source files lines ), 2 both")
    parser.add_argument("--selectionMode", type=str, default="GROUP", choices=["ALL", "GROUP"],
                        help="selection mode of vids to serve to operativeMode: either ALL (all vids founded taken), GROUP (dflt selected vids in groups obtained with grouppingRule opt)")
    parser.add_argument("--grouppingRule", type=str, default=ffmpegConcatDemuxerGroupping.__name__,choices=list(GrouppingFunctions.keys()), help="groupping mode of items")
    parser.add_argument("--groupFiltering", type=str, default="both",choices=["len","dur","both"],help="filtering mode of groupped items: below len or duration threshold the group will be filtered away")
    parser.add_argument("--itemsSorting", type=str, default="shuffle",choices=["shuffle", "size", "duration", "nameID"],
                        help="how sort items in the GUI when showed the tumbnails ")
    nsArgParsed = parser.parse_args(args)
    nsArgParsed.grouppingRule = GrouppingFunctions[nsArgParsed.grouppingRule]   #set groupping function by selected name

    # args combo validity check
    if nsArgParsed.videoTrimOldSelectionFileAction=="REVISION" and (nsArgParsed.operativeMode!= "ITERATIVE_TRIM_SELECT" or nsArgParsed.videoTrimOldSelectionFile==None)\
        or (nsArgParsed.videoTrimOldSelectionFileAction=="CONVERT_SELECTION_FILE_TRIM_SCRIPT" and  nsArgParsed.videoTrimOldSelectionFile==None):
        raise Exception("bad args combo")
    return nsArgParsed

if __name__ == "__main__":
    nsArgParsed = argParseMinimal(argv[1:])
    skipSelection=nsArgParsed.videoTrimOldSelectionFileAction=="REVISION" or nsArgParsed.operativeMode=="CONVERT_SELECTION_FILE_TRIM_SCRIPT"
    if not skipSelection:
        items = list(GetItems(nsArgParsed.pathStart).values())
        items=FilterItems(items)
        if nsArgParsed.selectionMode == "GROUP":
            groups = GetGroups(items, grouppingRule=nsArgParsed.grouppingRule)
            #filter groups
            minSize=MIN_GROUP_LEN
            if nsArgParsed.groupFiltering == "dur": minSize=MIN_GROUP_DUR
            groups=FilterGroups(groups,minSize,nsArgParsed.groupFiltering)
    # GUI based selection of vid items
    if nsArgParsed.operativeMode == "TUMBNAIL_MANAGMENT":  # sorting hardcoded TODO partial arg pass
        if DISABLE_GUI: raise Exception(
            "unable to start tumbnails grid with tkinter, enable GUI with enviorn variable: export DISABLE_GUI=False")
        if nsArgParsed.selectionMode == "GROUP":
            guiMinimalStartGroupsMode(groupsStart=groups)
        elif nsArgParsed.selectionMode == "ALL":
            itemsGridViewStart(list(items.values()))

    elif nsArgParsed.operativeMode=="ITERATIVE_TRIM_SELECT":
        # recoverSelectionOld
        oldSelection,skipOldNames = list(),None
        if nsArgParsed.videoTrimOldSelectionFile != None:  # extend current new selection with the old one
            oldSelection = DeserializeSelectionSegments(open(nsArgParsed.videoTrimOldSelectionFile).read())
            if nsArgParsed.videoTrimOldSelectionFileAction=="REVISION": items=oldSelection
            elif nsArgParsed.videoTrimOldSelectionFileAction=="SKIP": skipOldNames = [item.pathName for item in oldSelection]
            elif nsArgParsed.videoTrimOldSelectionFileAction=="MERGE": items+=oldSelection

        if nsArgParsed.selectionMode == "GROUP" and not skipSelection :
            if not DISABLE_GUI:items = guiMinimalStartGroupsMode(trgtAction=SelectWholeGroup, groupsStart=groups)
            else:items = selectGroupTextMode(groups)
        if nsArgParsed.itemsSorting != None:  vidItemsSorter(items,nsArgParsed.itemsSorting)

        selected, skipped = TrimSegmentsIterative(items, skipNameList=skipOldNames,
                                                  dfltStartPoint=nsArgParsed.videoTrimSelectionStartTime,
                                                  dfltEndPoint=nsArgParsed.videoTrimSelectionEndTime)
        print("selected: ", selected, "num", len(selected))
        selected.extend(oldSelection)
        # output selection
        logging = nsArgParsed.videoTrimSelectionOutput
        if logging == 0 or logging == 2: SerializeSelectionSegments(selected, SELECTION_FILE)
        if logging == 1 or logging == 2: GenTrimReencodinglessScriptFFmpeg(selected, outFname=TRIM_RM_SCRIPT,dstCutDir=nsArgParsed.dstCutDir)
    elif nsArgParsed.operativeMode == "CONVERT_SELECTION_FILE_TRIM_SCRIPT":
        oldSelection = DeserializeSelectionSegments(open(nsArgParsed.videoTrimOldSelectionFile).read())
        GenTrimReencodinglessScriptFFmpeg(oldSelection, outFname=TRIM_RM_SCRIPT)
    else:   raise Exception("BAD OPERATIVE MODE")
