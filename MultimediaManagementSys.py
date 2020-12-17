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
ScanItems                ->      recursive search from a start dir, files relative to Vid items
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

from grouppingFunctions import *
from configuration import *
from scriptGenerator import GenTrimReencodinglessScriptFFmpeg
from utils import * #concurrentPoolProcess, parseMultimedialStreamsMetadata,ffprobeMetadataGen, parseTimeOffset,vidItemsSorter

from collections import namedtuple
from os import environ,walk,path,system
from sys import argv,stderr
from subprocess import run,Popen,DEVNULL
from argparse import ArgumentParser
from json import loads, dumps, dump
from time import perf_counter
from re import search

attributes = ["nameID","pathName", "sizeB", "gifPath","imgPath","metadataPath",\
     "metadata","duration", "extension","cutPoints","trimCmds","segPaths","info","date"]
VidTuple = namedtuple("Vid", attributes)

class Vid:
    """Video items attributes plus useful operation on an item"""
    def __init__(self, multimediaNameK):
        self.nameID = multimediaNameK  # AS UNIQUE ID -> MULTIMEDIA NAME (no path and no suffix)
        #basic metadata for a video
        self.pathName = None
        self.sizeB = 0
        self.gifPath = None
        self.imgPath = None
        self.metadataPath = None
        self.metadata =None #list of vid's streams metadata (ffprobe)
        self.duration = 0   #in secs
        self.extension = None
        #trimSeg informations
        self.cutPoints = list() #cut times for segments generation [[start,end],...] 
        self.trimCmds  = list() #cmds to gen cutPoints (just for quick segs backup)
        self.segPaths  = list() #vid's segment trimmed file paths as .mp4.SEGMENT_NUM.mp4
        #var additional
        self.info=[""]  #additional infos - label like
        self.date=None  #vid file last access date TODO UNBINDED

    def __str__(self):
        outS="Item: id:"+self.nameID+" path: " + truncString(self.pathName) + \
            "size: " + str(self.sizeB) + " imgPath: " + truncString(self.imgPath)
        if self.gifPath!=None: outS+=" gifPath: "+truncString(self.gifPath)
        if not CONF["AUDIT_VIDINFO"]: outS="Item: "+ self.nameID
        return outS

    def genMetadata(self):
        assert self.pathName!=None,"missing vid to gen metadata"
        self.sizeB,self.metadata,self.duration,metadataFull=ffprobeMetadataGen(self.pathName)
        if CONF["SAVE_GENERATED_METADATA"]: self.saveFullMetadata(metadataFull)
        else:                       return metadataFull


    def fromJson(self, serializedDict, deserializeDictJson=False):
        """
        @param  deserializeDictJson: if true @serializedDict is json serialized string
                otherwhise is just a python dict with the target attributes to set
        @return:current Vid object with overwritten attributes
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
    
    def toTuplelist(self):
        """ save ram converting to a namedtuple the current object """
        return VidTuple(self.nameID,self.pathName,self.sizeB,self.gifPath,self.imgPath,\
         self.metadataPath,self.metadata,self.duration,self.extension,self.cutPoints,\
         self.trimCmds,self.segPaths,self.info,self.date)


vidNamedTuple2Obj=lambda trgt: Vid().fromJson(trgt._asdict(), False)


#support function
def play(vidPath, playBaseCmd=CONF["PLAY_CMD"]):
    """play the given Vids with playBaseCmd 
       vids may be a single path or space separated pathnames of vids """
    cmd = playBaseCmd+" "+vidPath
    print("to play: ", cmd)
    #out = Popen(cmd.split(), stderr=DEVNULL, stdout=DEVNULL)
    out = system(cmd+" 1>/dev/null 2>/dev/null &\n")


def remove(vid, confirm=True):
    #remove this item, if confirm ask confirmation onthe backed terminal
    #return True if item actually removed
    cmd = "rm "
    if vid.pathName!=None: cmd+= " " + vid.pathName
    if vid.imgPath!=None: cmd+= " " + vid.imgPath
    if vid.metadataPath!=None: cmd+= " " + vid.metadataPath
    if confirm and "Y" in input(cmd+" ???(y||n)\t").upper():
        # out = Popen(cmd.split(), stderr=DEVNULL, stdout=DEVNULL).wait()
        out = run(cmd.split())
        print("rm returned:",out.returncode)
        return out.returncode==0
    return False

### (de) serialization of Vids list
def SerializeSelection(selectedItems, filename=None,toTuple=True): #TODO __dict__ serialization deprecated -> so do this func
    """
        trivial serialization given @selectedItems in json 
        using namedtuple or  __dict__ ( accordingly to @toTuple)
        if @filename given output will be written to file
        @Returns serialized json string
    """
    if toTuple: outList = [ i.toTuplelist() for i in selectedItems ]
    else:            outList = [ i.__dict__  for i in selectedItems ]
    serialization = dumps(outList, indent=JSON_INDENT)
    if filename != None:
        f = open(filename, "w")
        f.write(serialization)
        f.close()
    return serialization


def deserializeSelection(dumpFp,backupCopyPath="/tmp/selectionBackup.json"):
    """ deserialize json list vid itemas as namedtuple 
		if backupCopyPath != None: save a copy of dumpFp to backupCopyPath
	"""
    serializedStr=dumpFp.read()
    serialized=loads(serializedStr)
    out=[VidTuple(*x) for x in serialized]
    if backupCopyPath: open(backupCopyPath,"w").write(serializedStr)
    return out


def updateCutpointsFromSerialization(items,itemsDumped,overWrFieldsNNEmpty=CONF["OVERWR_FIELDS_NEMPTY"]):
    """update trimSegments fields of Vids in @items  list
       with the ones in items in @itemsDumped list if they have a common nameId field
       if @overWrFieldsNNEmpty overwrite fields of items in @items 
        with all fields !None in the corresponding matching items in @itemsDumped

       compatible with normal Vid object or namedtuple version (same fields) 
        in both @items and @itemsDumped
	"""
    it = { items[i].nameID:i for i in range(len(items)) }
    for i in itemsDumped: 
        #update items matching nameid with corresponding dumped ones
        if i.nameID in it:  
                target=items[it[i.nameID]]
                #recognize readonly namedtuple in both target and matching one
                target_isTuple,matching_isTuple=isNamedtuple(target),isNamedtuple(i)
                #set trim infos in the same list obj (compatible with namedtuple)
                target.cutPoints.clear();target.cutPoints.extend(i.cutPoints)
                target.trimCmds.clear();target.trimCmds.extend(i.trimCmds)
                
                if overWrFieldsNNEmpty: #set other fields not empty
                    #get fields to replace 
                    fieldsNNEmpty=list() #fields to replace in target (name,newVal) 
                    if matching_isTuple:
                        fieldsNNEmpty=[x for x in i._asdict().items() if nnEmpty(x[1])]
                    else:   #normal object
                        fieldsNNEmpty=[x for x in vars(i).items() if nnEmpty(x[1])]

                    if target_isTuple:    target=vidNamedTuple2Obj(target) #create a target tmp copy writable
                    #replace fields
                    for x in fieldsNNEmpty: setattr(target,x[0],x[1])
                    if CONF["AUDIT_DSCPRINT"]: print("overwritten extra fields on",target.nameID,":",fieldsNNEmpty)
                    if target_isTuple:   #reset target as a namedtuple (better perf )
                        target=target.toTuplelist()
                        items[it[i.nameID]]=target 
                

### Vid Item gather from filesystem
def extractExtension(filename, PATH_ID,nameIdFirstDot=CONF["NameIdFirstDot"]):
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

def genMetadata(vidItems):
    """ @param vidItems either dict nameId->Vid object or just list of vid object
        inplace add metadata
    """
    start=perf_counter()

    itemsList=vidItems
    if type(vidItems)==type(dict()): itemsList=vidItems.values()

    metadataFilesQueue = [i for i in itemsList if i.metadata == None and i.pathName != None]
    metadataFilesPathQueue = [i.pathName for i in metadataFilesQueue]  # src vid files path to generate metadata
    print("metadata to gen queue len:", len(metadataFilesPathQueue))
    if len(metadataFilesQueue) > CONF["POOL_TRESHOLD"]:  # concurrent version
        processed = list(concurrentPoolProcess(metadataFilesPathQueue, ffprobeMetadataGen,\
                "metadata build err", CONF["POOL_SIZE"]))
        # manually set processed metadata fields (pool.map work on different copies of objs)
        for i in range(len(metadataFilesPathQueue)):
            item, processedMetadata = metadataFilesQueue[i], processed[i]
            if processedMetadata != None and processedMetadata[1] != None:  # avaible at least metadata dict
                item.sizeB, item.metadata, item.duration, metadataFull = processedMetadata
                if CONF["SAVE_GENERATED_METADATA"]: item.saveFullMetadata(metadataFull)
            else:
                print("invalid metadata gen at ", item.pathName, file=stderr)
    else:  # sequential version if num of jobs is too little -> only pickle/spawn/... overhead in pool
        for item in metadataFilesQueue: item.genMetadata();
    
    end=perf_counter()
    print("metadatas gen in:",end-start,"workPoolUsed:",len(metadataFilesQueue)>CONF["POOL_SIZE"])

def ScanItems(rootPath=".", vidItems=dict(), PATH_ID=False,forceMetadataGen=CONF["FORCE_METADATA_GEN"], limit=float("inf"), \
             followlinks=True,skipKw=FilterKW):
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
    @param skipKw:          list of keyword that if any of them is in a filepath -> skip item
    @return: updated @vidItems dict with the newly founded vids
    """
    start = perf_counter()
    doubleCounter=0
    for root, directories, filenames in walk(rootPath, followlinks=followlinks):
        for filename in filenames:
            fpath = path.join(path.abspath(root), filename)
            skip=False
            for kw in skipKw:
                if kw in fpath: skip=True
            # extract nameKey and extension from filename, skip it if skipFname gives true
            extension, nameKey = extractExtension(fpath,PATH_ID)
            if skip or skipFname(extension):                     continue
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
                notHandledExt=True
                for ext in VIDEO_MULTIMEDIA_EXTENSION:
                    if ext in extension: notHandledExt=False;break
                if notHandledExt:
                    print("not handled extension",extension,item,file=stderr)
                    continue
                
                if item.pathName != None: 
                    print("already founded a vid with same nameID",item.nameID,item.pathName,\
                        fpath," ... overwriting pathName",file=stderr);doubleCounter+=1
                isSegment=False
                if search(REGEX_VID_SEGMENT,fpath) == None: #normal vid
                    item.pathName = fpath
                    item.extension=extension
                else:   #segment trimmed file
                    print(fpath)
                    #set "fullvideo" path to a tmp fake path, to avoid later filtering
                    if item.pathName==None: item.pathName=TMP_FULLVID_PATH_CUTS
                    if lastPartPath(fpath) in [lastPartPath(f) for f in item.segPaths]:
                        print("segment",fpath," already included...",item.segPaths)
                        continue
                    item.segPaths.append(fpath)

            if len(vidItems) == limit:  print("reached", limit, "vid items ... breaking the recursive search");break
    missingPath= [i for i in vidItems.values() if i.pathName==None ]
    missingMetdPath= [i for i in vidItems.values() if i.metadataPath == None and i.pathName!=None ]
    metadataFilesQueue = [i for i in vidItems.values() if i.metadataPath != None and i.pathName!=None]
    print("double nameID founded: ",doubleCounter,"tot num of items founded:",len(vidItems))
    print("metadata file to read queue len:",len(metadataFilesQueue))
    startRdMetadata=perf_counter()
    if len(metadataFilesQueue) > CONF["POOL_TRESHOLD"]:
        # concurrent metadata files parse in order
        metadataFilesPathQueue = [i.metadataPath for i in metadataFilesQueue]
        processed = list(concurrentPoolProcess(metadataFilesPathQueue, parseMultimedialStreamsMetadata,"badJsonFormat",CONF["POOL_SIZE"] ))
        for i in range(len(metadataFilesQueue)):
            metadata, item = processed[i], metadataFilesQueue[i]
            if metadata == None or metadata[1]==None:
                print("None metadata readed at ",item.metadataPath,file=stderr);continue
            item.sizeB, item.metadata, item.duration = metadata
    else:  # sequential version if num of jobs is too little -> only pickle/spawn/... overhead in pool
        for item in metadataFilesQueue:
            item.sizeB, item.metadata, item.duration = parseMultimedialStreamsMetadata(item.metadataPath)
    endRdMetadata=perf_counter()
    startGenMetadata=perf_counter()
    if forceMetadataGen:        genMetadata(vidItems) # generate missing metadata with run() calls -> ffprobe + parse
    end = perf_counter()
    print("founded Vids: ", len(vidItems),"metadataRead:",endRdMetadata-startRdMetadata,"metaGen:",end-startGenMetadata)
    return vidItems


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
    if srcItems == None:  srcItems = list(ScanItems(startSearch).values())
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
        elif CONF["AUDIT_DSCPRINT"]:  print("filtered group\tlen:",len(items),"dur:",gDur,file=stderr)
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
        selectedGroupIDs = input("ENTER EITHER GROUPS NUMBER SPACE SEPARATED,ALL for all groups\t ")
        if "ALL" in selectedGroupIDs.upper(): out = groupVals
        else:
            for gid in selectedGroupIDs.split():
                if joinGroupItems:  out += groups[groupKeys[int(gid)]]
                else:               out.append(groups[groupKeys[int(gid)]])
    print("selected items: ",len(out))
    return out

#convert pathnames list to nameID list
pathsToNameIDlist=lambda paths: [extractExtension(p)[1] for p in paths]
    
def FilterItems(items, pathPresent=True,tumbnailPresent=False,gifPresent=False,\
         metadataPresent=True,durationPos=False,filterKW=FilterKW,keepNIDS=list()):
    """
    filter items by the optional flags passed
    @items: source items list
    @pathPresent: filter away items without pathname set  (dflt true)
    @tumbnailPresent:  filter away items without tumbnail img path set
    @metadataPresent:  filter away items without metadata dict set
    @filterKW:  list of keywords to match to item.pathName to discard vids
    @keepNIDS:  white list of acceptable nameID of the items to keep
                if empty keep al items not filter with the rest of the logic
    @return: filtered items in a new list
    """
    outList = list()
    if len(keepNIDS)>THRESHOLD_L_TO_HMAP: keepNIDS={ k:0 for k in keepNIDS}
    for i in items:
        keep=       (not pathPresent or i.pathName != None) \
                and (not tumbnailPresent or i.imgPath !=None) \
                and (not gifPresent or i.gifPath !=None) \
                and (not metadataPresent or i.metadata !=None)\
                and (not durationPos or i.duration>0)
        #audit missing fields for manual operations
        if CONF["AUDIT_MISSERR"] or (not CONF["QUIET"] and not keep):
            if i.pathName == None:print("missing pathName at",i,file=stderr);continue
            if i.imgPath == None and i.gifPath == None: #if at least one of them is fine
                if i.imgPath == None : print("Missing thumbnail at \t", i.pathName,file=stderr)
                if i.gifPath == None:  print("Missing gif at \t", i.pathName,file=stderr)
            if i.metadata==None:  print("None metadata", i.metadataPath, file=stderr)
            elif i.duration <= 0 and i.metadataPath != None:
                print("invalid duration", i.duration, i.metadataPath, file=stderr)

        if len(keepNIDS)>0 and i.nameID not in keepNIDS:
            print("filtered ",i,"not in nameID s whitelist")
            keep=False;continue

        for kw in filterKW:
            if not keep or kw in i.pathName:
                keep=False
                if i.pathName != None and kw in i.pathName: 
                    print("filtered keyword",kw," at ",i.pathName)
                break
        if keep:    outList.append(i)

    
    filtered=len(items)-len(outList)
    if filtered>0: print("filtered:",filtered,"items",tumbnailPresent,gifPresent)
    return outList

#filter items with nameid contained in a pathname in nameListFilterFile
ItemsNamelistRestrict=lambda itemsList,nameListFilterFile: \
    FilterItems(itemsList,\
    keepNIDS=pathsToNameIDlist(open(nameListFilterFile).readlines())) 

######
### iterative play trim - selection of items support
def _printCutPoints(cutPoints):  # print cutPoints as string vaild for  TrimSegmentsIterative
    outStr = ""
    for seg in cutPoints:
        start, end = seg[0], seg[1]
        outStr += " start " + str(start)+" "
        if end != None: outStr += str(end)
    return outStr

trimSelectionPrompt="SKIP || QUIT || DEL || start START_TIME[,END_TIME] || ringRange ringCenter,[radiousNNDeflt] || hole HOLESTART HOLEEND\n\n"
timeStrToNumeric=lambda s: s.replace(".","").replace(":","")
def trimSegCommand(vid,cmd,start=0,end=None,newCmdOnErr=True,overwriteCutPoints=True,backUpCmdsFile="/tmp/trimCmds.string"):
    """ 
    parse @cmd to trim @vid, writing cutPoints field inplace
    @Returns: cutPoints added to vid
    specifiable default trimmedSeg @start or @end 

    eventual exception caused from a bad cmd are catched,
    if @newCmdOnErr a new cmd will be prompted

    possible commands (short version with the first letter of the commands below)
    start startTime[,endTime] -> just add a segment of the given next times (if not endTime use @end)
    ringrange ringCenter[,radious] -> add a segment of ringCenter-radious,ringCenter+radious
    hole hStart,hEnd->take the last selected segment (whole,dflt bounded, vid if not any) 
                      and remove an hole creating 2 segs [lSegStart:hStart] [hEnd:lSegEnd]
    """

    if end == None: end=vid.duration
    segmentationPoints = list()  #trim segmentation points for vid
    fields = cmd.split()
    replay=True
    # iteration play-selection loop
    while replay:   
        replay=False
        try:
            for f in range(len(fields)):
                # parse cmd fields
                fieldCurr = fields[f].lower()

                #start[,end]
                if "start" in fieldCurr or "s" in fieldCurr:      
                    startTime, endTime = parseTimeOffset(fields[f+1]),end
                    if f+2 < len(fields) and timeStrToNumeric(fields[f+2]).isdigit():
                        endTime = parseTimeOffset(fields[f + 2])
                    segmentationPoints.append([startTime, endTime])
                
                #ringrange center[,radious]
                elif "r" in fieldCurr or "ringRange" in fieldCurr:
                    radious = CONF["RADIUS_DFLT"]
                    center = parseTimeOffset(fields[f + 1], True) #convert to secs (float)
                    if f + 2 < len(fields) and fields[f + 2].replace(".","").isdigit():   
                        radious = float(fields[f + 2])
                    segmentationPoints.append([str(center - radious), str(center + radious)])

                # dig hole in the last seg (or the whole vid if not any), splitting it in 2 new segs
                elif "hole" in fieldCurr or "h" in fieldCurr:  
                    holeStart, holeEnd = parseTimeOffset(fields[f + 1]), parseTimeOffset(fields[f + 2])
                    lastSeg = [start, end]
                    if len(segmentationPoints) > 0: lastSeg = segmentationPoints.pop()
                    #cut away the specified hole in the last segment
                    hseg0, hseg1 = [lastSeg[0], holeStart], [holeEnd, lastSeg[1]]  # split the last seg in 2
                    segmentationPoints.append(hseg0)
                    segmentationPoints.append(hseg1)
                
        except Exception as e:
            print("invalid cut cmd: ", cmd, e,"!!!!",file=stderr)
            if newCmdOnErr: 
                fields=input("re-enter a valid trim command:\n"+trimSelectionPrompt).split()
                play(vid,CONF["PLAY_CMD"])
                replay=True

    #backup the cmds 
    try:
        if backUpCmdsFile!=None:
            open(backUpCmdsFile,"a").write(vid.pathName+"\t"+cmd+"\n")
    except: print("failed to open backUpCmdsFile:",backUpCmdsFile,"to append:",cmd)
    
    #embed cutpoints 
    if overwriteCutPoints:  vid.cutPoints.clear()
    vid.cutPoints.extend(segmentationPoints)
    
    print("selected these cutpoints:",segmentationPoints,"with cmd:\t"+cmd,sep="\n")
    return segmentationPoints


def appendVidInfoStr(item,infoStr): item.info[0] += infoStr

def TrimSegmentsIterative(itemsList, skipNameList=None, dfltStartPoint=0, dfltEndPoint=None, overwriteCutPoints=True):
    """
    iterativelly play each Vid items and prompt for  select/replay video or trim in segments by specifing cut times
    segmentation times, if given will be embedded in cutPoints of Vid as a list of [[start,end],...]
    in segmentation times can be specified an  "hole": will be split the last segment avaible among cutPoints pairs
        into 2 segs where the whole time range is removed
    @param itemsList:       Vid objects to play, select and cut with the promt cmd
    @param skipNameList:    pathnames of items not to play
    @param dfltStartPoint:  default start time for the first segment of each selected Vid
    @param dfltEndPoint:    default end time for the last segment (if negative added to item duration) of each selected Vid
    @param overwriteCutPoints: if True old cutPoints in the given items will be overwritten with the new defined ones
    @return:  when no more video in itemsList or quitted inputted returned tuple
        thelist of selected itmes (along with embeded cut points), list skipped items) returned
    """
    selection,skipList = list(),list()
    ## handle fix start-end of videos
    tmpSelectionBackup=open(TMP_SEL_FILE,"w")
    for item in itemsList:
        if skipNameList != None and item.pathName in skipNameList: continue     #skip item
        end = item.duration
        if dfltEndPoint != None:             end = dfltEndPoint
        elif end < 0:                        end += item.duration #seek from end

        if len(item.cutPoints)>0:
            print("curr cutPoints:\t", _printCutPoints(item.cutPoints))
            #drawSegmentsTurtle([item]) #TODO turtle.Terminator
        
        play(item.pathName ,CONF["PLAY_CMD"])
        # Prompt String
        cmd = input("Add Vid "+item.nameID+" dur " +str(item.duration/60) + "min, size "+\
                str(item.sizeB/2**20)+"MB"+ trimSelectionPrompt)

        if "SKIP" in cmd.upper() or cmd == "":  skipList.append(item);continue
        if "Q" in cmd.upper():                  return selection, skipList
        if "DEL" in cmd.upper():                remove(item); continue

        trimSegCommand(item,cmd,dfltStartPoint,end,overwriteCutPoints=overwriteCutPoints)
        info=input("addition infos to add [dflt=""]\t")
        appendVidInfoStr(item,info)
        selection.append(item)
        #write selection to a tmp file with selected items json serialized to not lost partial selection
        tmpSelectionBackup.seek(0)
        tmpSelectionBackup.write(dumps([i.__dict__ for i in selection]))
    tmpSelectionBackup.close()
    return selection, skipList

def argParseMinimal(args):
    # minimal arg parse use to parse optional args
    parser = ArgumentParser(
        description=__doc__ + '\nMagment of vid clips along with their metadata and tumbnails with an optional minimal GUI')
    parser.add_argument("pathStart", type=str, help="path to start recursive search of vids")

    parser.add_argument("--operativeMode", type=str, default="ITERATIVE_TRIM_SELECT",choices=["ITERATIVE_TRIM_SELECT","CONVERT_SELECTION_FILE_TRIM_SCRIPT"],
                        help="Operating mode, ITERATIVE_TRIM_SELECT: select and trim vids 1 at time;CONVERT_SELECTION_FILE_TRIM_SCRIPT: convert serialized selection to a ffmpeg cut script")
    
    parser.add_argument("--videoTrimOldSelectionFile", type=str, default=None,help="ols json serialized selection file")
    parser.add_argument("--videoTrimOldSelectionFileAction", type=str, default="SKIP",choices=["SKIP","MERGE","REVISION"],
                        help="action to do with the content of the old selection file:"
                        "SKIP -> skip old selected items but append to new selection,"
                        "MERGE ->  merge saved items with cutpoints to the new items, then go totrim selection loop, "
                        "REVISION -> overwrite cut points of the old selected items, not search for other vids")

    parser.add_argument("--dstCutDir", type=str, default="cuts",help="dir where to save trimmed segments, default ./cuts/ ")

    parser.add_argument("--videoTrimSelectionStartTime", type=float, default=None,\
        help="default start time for the selected videos in ITERATIVE_TRIM_SELECT operating Mode")
    parser.add_argument("--videoTrimSelectionEndTime", type=float, default=None,\
    help="default end time for the selected video in ITERATIVE_TRIM_SELECT operating Mode, if negative added to the end of current vid in selection...")
    
    parser.add_argument("--videoTrimSelectionOutput", type=int, default=2, choices=[0, 1, 2],
                        help="output mode of ITERATIVE_TRIM_SELECT mode: 0 (dflt) json serialization of selected file with embeddd cut points, 1 bash ffmpeg trim script with -ss -to -c: copy -avoid_negative_ts (commented rm source files lines ), 2 both")

    parser.add_argument("--selectionMode", type=str, default="ALL", choices=["ALL", "GROUP"],
                        help="how to select the items for ITERATIVE_TRIM_SELECT,either  ALL (all vids founded taken), GROUP (dflt selected vids in groups obtained with grouppingRule opt)")
    parser.add_argument("--grouppingRule", type=str, default=ffmpegConcatDemuxerGroupping.__name__,choices=list(GrouppingFunctions.keys()), help="groupping mode of items")
    parser.add_argument("--groupFiltering", type=str, default="both",choices=["len","dur","both"],help="filtering mode of groupped items: below len or duration threshold the group will be filtered away")
    parser.add_argument("--itemsSorting", type=str, default="shuffle",choices=["shuffle", "size", "duration", "nameID"],help="how sort items ")

    nsArgParsed = parser.parse_args(args)
    nsArgParsed.grouppingRule = GrouppingFunctions[nsArgParsed.grouppingRule]   #set groupping function by selected name

    # args combo validity check
    if nsArgParsed.videoTrimOldSelectionFileAction=="REVISION" and (nsArgParsed.operativeMode!= "ITERATIVE_TRIM_SELECT" or nsArgParsed.videoTrimOldSelectionFile==None)\
        or (nsArgParsed.videoTrimOldSelectionFileAction=="CONVERT_SELECTION_FILE_TRIM_SCRIPT" and  nsArgParsed.videoTrimOldSelectionFile==None):
        raise Exception("bad args combo")
    return nsArgParsed

if __name__ == "__main__":
    args = argParseMinimal(argv[1:])
    skipSelection= args.videoTrimOldSelectionFileAction == "REVISION" or args.operativeMode == "CONVERT_SELECTION_FILE_TRIM_SCRIPT"
    items = list()
    if not skipSelection:
        if args.selectionMode == "ALL":
            items = list(ScanItems(args.pathStart).values())
            items=FilterItems(items)
        elif args.selectionMode == "GROUP":
            groups = GetGroups(items, grouppingRule=args.grouppingRule)
            #filter groups
            minSize=CONF["MIN_GROUP_LEN"]
            if args.groupFiltering == "dur": minSize=CONF["MIN_GROUP_DUR"]
            groups=FilterGroups(groups, minSize, args.groupFiltering)
            for x in groups.values():
                for y in x: items.append(x)
    if args.operativeMode== "ITERATIVE_TRIM_SELECT":
        # recoverSelectionOld
        oldSelection,skipOldNames = list(),None
        if args.videoTrimOldSelectionFile != None:  # extend current new selection with the old one
            oldSelection = deserializeSelection(open(args.videoTrimOldSelectionFile).read())
            if args.videoTrimOldSelectionFileAction == "REVISION": items=oldSelection
            elif args.videoTrimOldSelectionFileAction == "SKIP": skipOldNames = [item.pathName for item in oldSelection]
            elif args.videoTrimOldSelectionFileAction == "MERGE": items+=oldSelection

        if args.selectionMode == "GROUP" and not skipSelection :
            items = selectGroupTextMode(groups) #guiMinimalStartGroupsMode(trgtAction=SelectWholeGroup, groupsStart=groups)
        if args.itemsSorting != None:  vidItemsSorter(items, args.itemsSorting)

        selected, skipped = TrimSegmentsIterative(items, skipNameList=skipOldNames,
                                                  dfltStartPoint=args.videoTrimSelectionStartTime,
                                                  dfltEndPoint=args.videoTrimSelectionEndTime)
        print("selected: ", selected, "num", len(selected))
        selected.extend(oldSelection)
        # output selection
        logging = args.videoTrimSelectionOutput
        if logging == 0 or logging == 2: SerializeSelection(selected, SELECTION_FILE)
        if logging == 1 or logging == 2: GenTrimReencodinglessScriptFFmpeg(selected, outFname=TRIM_RM_SCRIPT, dstCutDir=args.dstCutDir)
    elif args.operativeMode == "CONVERT_SELECTION_FILE_TRIM_SCRIPT":
        oldSelection = deserializeSelection(open(args.videoTrimOldSelectionFile).read())
        GenTrimReencodinglessScriptFFmpeg(oldSelection, outFname=TRIM_RM_SCRIPT)
    else:   raise Exception("BAD OPERATIVE MODE")
