#!/usr/bin/env python3
#Copyright Andrea Di Iorio
#This file is part of FFmpegFastTrimConcat
#FFmpegFastTrimConcat is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#FFmpegFastTrimConcat is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with FFmpegFastTrimConcat.  If not, see <http://www.gnu.org/licenses/>.
#
#!/usr/bin/env python3
"""
This module define a struct for videos as a generic MultimediaItem
each of these item is identified by name ID that is a truncation of the file name up to first or last "." -> see NameIdFirstDot
it's supported to store metadata as a json format for each item identified by nameid ID as ID.json ( code is written for ffprobe all stream output in json)
        also supported run time generation of metadata for a given video with the run method -> running on an underlining shell
Main Exported Function:
GetItems        ->      recursive search from a start dir, files buildining items along with NameIdFirstDot, returning a dict (nameID->itemObj)
GetGroups       ->      gruop items, with a groupping function, that classify item with a KEY (e.g. resoulution, core metadata (fieldName,value)
SelectItemPlay  ->      iterativelly play item with an specified base cmd (default is ffplay), prompt for selection and segmentation time
GenPlayIterativeScript  ->      from a selection returned from the above cmd -> generate a bash script to play all segment of all selected videos

GUI METHODS: itemsGridViewStart;        guiMinimalStartGroupsMode
________________________________________________________________________________________________________________________
ENVIRON OVERRIDE OPTIONS
VERBOSE
DISABLE_GUI
NameIdFirstDot -> (dflt True )filename truncated to first dot to extract file nameID
SELECTION_LOGFILE       -> logFileName
FORCE_METADATA_GEN -> (dflt True) force metadata generation for items
----for show items with tumbnails---
MODE <- ALL <- show items not groupped, otherwise deflt grouppingRule given at guiMinimalStartGroupsMode 
"""

from os import walk,path,environ
from sys import argv
from json import load,loads,dumps
from random import shuffle
from subprocess import run,Popen,DEVNULL
from time import ctime
from argparse import ArgumentParser
DISABLE_GUI=False
if "DISABLE_GUI" in environ and "T" in environ["DISABLE_GUI"].upper():DISABLE_GUI=True
if not DISABLE_GUI:
    try:
        from GUI import *
    except: DISABLE_GUI=True


######## ENV VAR CONFI##################
SELECTION_LOGFILE="selected.list"
if environ.get("SELECTION_LOGFILE")!=None: SELECTION_LOGFILE=environ["SELECTION_LOGFILE"]
NameIdFirstDot=True
if environ.get("NameIdFirstDot")!=None and "F" in environ["NameIdFirstDot"].upper(): NameIdFirstDot=False
FORCE_METADATA_GEN=True
if environ.get("FORCE_METADATA_GEN")!=None and "F" in environ["FORCE_METADATA_GEN"].upper(): FORCE_METADATA_GEN=False

############################################### Items Groupping Functions       ####################################
def sizeBatching(item,groupByteSize=(100*(2**20))): return str(groupByteSize/2**20)+"MB_Group:\t"+ str(item.sizeB // groupByteSize)        #dflt group by size in batch of 500MB each
def durationBatching(item,groupMinNum=5): return str(groupMinNum*(item.duration // (60*groupMinNum)))+" ~Min_Group"   #dflt group by duration in batch of 5 min each
def ffprobeExtractResolution(item):    #just get resolution   
    return str(item.metadata[0]["width"])+" X "+str(item.metadata[0]["height"])+" SAR "+str(item.metadata[0]["sample_aspect_ratio"])

def ffmpegConcatDemuxerGroupping(item): #label element to group them by metadata s.t. they may be concateneted with the concat demuxer
    return GroupByMetadataValuesFlexible(item,["duration", "bit_rate", "nb_frames", "tags", "disposition", "avg_frame_rate", "color"],True,True)

GrouppingFunctions={ f.__name__ : f for f in [ffprobeExtractResolution,ffmpegConcatDemuxerGroupping,sizeBatching,durationBatching]}


def GroupByMetadataValuesFlexible(item,groupKeysList,EXCLUDE_ON_KEYLIST=False,EXCLUDE_WILDCARD=True):
        """
        categorize multimedia item by its values in some metadata field expressed in groupKeysList
        if EXCLUDE_ON_KEYLIST is true the categorization will be based on values of all fields not in groupKeysList
            so groupKeysList  will act as a black list actually
        returned group Key for the item as a list of pairs MetadataFieldKey->(item metadata val on that fild)
        """
        groupsDict=dict()   #dict (valueOfK_0,...,valueOfK_N) -> LIST Files with this metadata values groupped
        groupKeysList.sort()
        fMetadata=item.metadata[0]  #get video stream of multimedia obj.metadata
        fMetadataValues=list()  #list of values associated to groupKeysList for the target groupping of files
        fKeysAll=list(fMetadata.keys())
        fKeysAll.sort()
        for k in fKeysAll:
                if EXCLUDE_ON_KEYLIST:  #the given groupKeysList is a black list
                        if EXCLUDE_WILDCARD:    #blackList will be used has a pattern to exclude actual f metadata keys
                                kInExcludeList=False
                                for kEx in groupKeysList:
                                        if kEx in k:
                                                kInExcludeList=True
                                                break
                                if kInExcludeList==False:fMetadataValues.append((k,fMetadata[k]))
                        else:
                                if k not in groupKeysList: fMetadataValues.append((k,fMetadata[k]))
                else:
                        if k in groupKeysList: fMetadataValues.append((k,fMetadata[k]))
        groupK=tuple(fMetadataValues)
        return groupK

#MULTIMEDIA FILES HANDLED EXTENSIONS
IMG_TUMBRL_EXTENSION="jpg"
VIDEO_MULTIMEDIA_EXTENSION="mp4"
METADATA_EXTENSION="json"
#############	MODEL  ##############
class MultimediaItem:
        """class rappresenting a video with same metadata"""
        def __init__(self,multimediaNameK):
                self.nameID=multimediaNameK	 #AS UNIQUE ID -> MULTIMEDIA NAME (no path and no suffix)
                self.pathName=""
                self.sizeB=0
                self.imgPath=""
                self.metadataPath=""
                self.metadata=""
                self.duration=0                 #num of secs for the duration
                self.extension=""
                self.cutPoints=list()           #may hold cut times for segment generation as [[start,end],...]  (support for SelectItemPlay)
        def __str__(self):                 return "Item: path: "+self.pathName+" size: "+str(self.sizeB)+" imgPath: "+self.imgPath
        def generateMetadata(self,FFprobeJsonCmd="ffprobe -v quiet -print_format json -show_format -show_streams"):
                """generate metadata for item with subprocess.run """
                FFprobeJsonCmdSplitted=FFprobeJsonCmd.split(" ")+ [self.pathName]
                out=run(FFprobeJsonCmdSplitted,capture_output=True)
                metadata=loads(out.stdout.decode())
                self.sizeB,self.metadata,self.duration=_extractMetadataFFprobeJson(metadata)
                return out
        def play(self,playBaseCmd="ffplay -autoexit -fs "):
                """play the MultimediaItem with the given playBaseCmd given """
                cmd=playBaseCmd+self.pathName
                #run(cmd.split())
                #out=Popen(cmd.split(),stderr=DEVNULL,stdout=DEVNULL)
                out=Popen(cmd.split(),stderr=DEVNULL)
        def remove(self):
                cmd="rm "+self.pathName+" "+self.imgPath+" "+self.metadataPath
                #out = Popen(cmd.split(), stderr=DEVNULL, stdout=DEVNULL).wait()
                out=run(cmd.split())
                print(out.returncode)

        def toJson(self): return dumps(self.__dict__)   #trivial json serialization of __dict__
        def fromJson(self,serializedDict,deserializeDictJson=False):
                #simply deserialize serializedDict into object fields
                #if deserializeDictJson: input dict is serialized in json
                #WILL OVERRIDE ALL CURRENT FIELDS
                deserializedDict=serializedDict
                if deserializeDictJson: deserializedDict=loads(serializedDict)
                for k,v in deserializedDict.items(): setattr(self,k,v)
                return self

## utils
printList = lambda l: list(map(print, l))  #basic print list, return [None,...]
def _extractMetadataFFprobeJson(metadata):
        fileSize=int(metadata["format"]["size"])
        streamsDictMetadata=metadata["streams"]
        #make sure video stream is at the first position in metadata.streams
        if len(streamsDictMetadata) > 1 and "video" in  streamsDictMetadata[1]["codec_type"]:
                streamsDictMetadata[0],streamsDictMetadata[1]=streamsDictMetadata[1],streamsDictMetadata[0]
        dur=streamsDictMetadata[0].get("duration",0)
        fileDur=float(dur)
        return fileSize,streamsDictMetadata,fileDur
def parseMultimMetadata(fname):
        #parse ffprobe generated json metadata of fname file
        #return fileSize,streams array of dict metadata # that will have video stream as first
        fileMetadata=open(fname)
        metadata=load(fileMetadata)
        fileMetadata.close()
        return _extractMetadataFFprobeJson(metadata)
def _getLastDotIndex(string):
    for s in range(len(string)-1,-1,-1):
        if string[s]==".": return s
    return -1

################### Item selection-groupping
#true if given fname with the extracted extension is uselss -> not contain Multimedia data by looking at the extension
skipFname=lambda fname,extension: not(IMG_TUMBRL_EXTENSION in extension or METADATA_EXTENSION in extension or VIDEO_MULTIMEDIA_EXTENSION in fname)
def GetItems(rootPathStr=".",multimediaItems=dict(),forceMetadataGen=FORCE_METADATA_GEN,limit=float("inf")):
        """
        scan for multimedia objs from rootPathStr recursivelly
        will be builded multimedia obj for each founded multimedia file
        all multimedia objs will be structured in a dict itemNameKey->MultimediaObj, 
            where itemNameKey is the file name until last dot (extension excluded)
        multimediaItems can be given so it will updated in place
        if forceMetadataGen True -> for the vids missing metadata will be generated it sequentially with a subprocess.run cmd
        return dict of fileNameKey->Multimedia Obj where fileNameKey is the extension truncated filename
        """
        i=0
        for root, directories, filenames in walk(rootPathStr,followlinks=True):
                #print(root,"\t",directories,"\t",filenames)            #pathName=path.join(path.abspath(root),filename)
                for filename in filenames:
                        #parse a name ID as the extension removed from each fname founded during the path walk
                        extension=filename[-5:]
                        extIndx=filename.rfind(".")
                        name=filename
                        if extIndx!=-1:
                            extension=filename[extIndx+1:]
                            if NameIdFirstDot: name=filename[:filename.find(".")] #take until first dot
                            else: name=filename[:extIndx]  

                        if skipFname(filename,extension): continue
                        #init multimedia item obj if not already did
                        item=multimediaItems.get(name)
                        if item==None:
                                item=MultimediaItem(name)
                                multimediaItems[name]=item
                        #recnoize if the file is a video a tumrl o a metadata file
                        fpath=path.join(path.abspath(root),filename)
                        if IMG_TUMBRL_EXTENSION in extension:   item.imgPath=fpath
                        elif METADATA_EXTENSION in extension:
                                try:
                                    item.sizeB,item.metadata,item.duration=parseMultimMetadata(fpath) #skip bad/not fully formatted jsons
                                    item.metadataPath=fpath
                                except Exception as e: print("badJsonFormat at ",fpath,"\t",e)
                        #elif VIDEO_MULTIMEDIA_EXTENSION in lastSuffix:
                        elif VIDEO_MULTIMEDIA_EXTENSION in filename:    #match extension embeded in fname before extension part
                        #else:	#take all possible other extension as video multimedia extension
                                item.pathName=path.join(path.abspath(root),filename)
                                item.extension=extension
                        i+=1
                        if i>limit: break
                if i>limit: break
        print("MultimediaItems founded: ",len(multimediaItems))
        if forceMetadataGen:
            for i in multimediaItems.values():
                if i.metadata=="" and len(i.pathName)>0:
                    print("try Generate missing metadata at:\t",i.pathName)
                    try:i.generateMetadata()
                    except Exception as e: print("not possible to generate json metadata at:",i,"\t",e)
                    

        return multimediaItems

GetItemsListRecurisve=lambda startPath=".":list(GetItems(".").values())
def GetGroups(srcItems=None,grouppingRule=ffmpegConcatDemuxerGroupping,startSearch=".",filterTumbNailPresent=False):
        """
        group items in a dict by a custom rule
        :param srcItems:  multimedia items to group as dict itemNameID->item, if None will be generated by a recoursive search from :param startSearch
        :param grouppingRule: function: multimediaItem->label (label= immutable key for groups dict)
        :return: items groupped in a dict: groupKey->itemsList groupped
        """
        groups=dict()   #groupKey->itemList
        if srcItems==None:  srcItems=GetItems(startSearch)
        for item in FilterItems(srcItems.values(),tumbNailPresent=filterTumbNailPresent):
                try:
                        itemKeyGroup=grouppingRule(item)
                        if groups.get(itemKeyGroup) == None: groups[itemKeyGroup] = list()
                        groups[itemKeyGroup].append(item)
                except Exception as e:
                    itemKeyGroup="OTHERS"
                    print(e,"\tNOT ComputableGroupKey at ",item.nameID)
                    continue
        return groups
def selectGroupTextMode(groups):
    """
    select group items among all groups given
    return a list of MultimediaItems
    """
    groupKeys=list(groups.keys())
    for i in range(len(groupKeys)):
        cumulativeSize, cumulativeDur = 0, 0
        for item in groups[groupKeys[i]]:
            cumulativeDur += int(item.duration)
            cumulativeSize += int(item.sizeB)
        print("::> group:",i,"numItem:",len(groups[groupKeys[i]]),"cumulative Duration:",cumulativeDur,"cumulativeSize:",cumulativeSize,"\ngrouppingKey:",groupKeys[i])
    selectedGroupID=int(input("ENTER GROUP NUMBER"))
    return groups[groupKeys[selectedGroupID]]

def FilterItems(items,pathPresent=True,tumbNailPresent=True,metadataPresent=False):
        """ filter items by optional flags passed
            return a new list with the filtered items
        """
        outList=list()
        for i in items:
                if (not pathPresent or i.pathName!="") and (not tumbNailPresent or i.imgPath!="") and (not metadataPresent or i.metadata!=""):
                        outList.append(i)
                elif i.pathName!="" and i.imgPath=="": print("!!!!Missing thumbnail at \t",i)       #DUMP MISSING TUMBNAILS
                else: print("filtered item ", i)
        print(len(items),len(outList))
        return outList

### iterative play selection of items support
def _printCutPointsAsInputStr(cutPoints):       #print cutPoints as string
        outStr=""
        for seg in cutPoints:
                start,end=seg[0],seg[1]
                outStr="start "+str(start)
                if end!=None:outStr+="end "+str(end)
        return outStr

def parseTimeOffset(timeStr):
    #parse time specification string
    if ":" in timeStr:  return timeStr #[HH]:MM:SS.dec
    secOffs=-1
    try:    secOffs=float(timeStr)
    return secOffs                      #sec.dec

def SelectItemPlay(itemsList,skipNameList=None,dfltStartPoint=None,dfltEndPoint=None):
        """
        iterativelly play items and prompt for cmd insertion for selection/replay video, trim in segment by specifing cut times 
        segmentation times, if given will be embedded in cutPoints as a list of [[start,end],...]
        in segmentation times can be specified an "hole": will be split the last segment (specified before hole kw in cmd )
            into 2 segs where the whole range times is removed
        :param itemsList:       items to play and cut with the promt cmd
        :param skipNameList:    pathnames of items not to play not to play
        :param dfltStartPoint:  default start time for the first segment
        :param dfltEndPoint:    default end time for the last segmenet (if negative added to item duration)
        :return:(list of selected itmes (along with embeded cut points),list skipped items) returned when no more video in itemsList or quitted inputted
        """
        assert len(itemsList)>0,"given empty list for selection"
        selection=list()
        skipList=list()
        ## handle fix start-end of videos
        if dfltStartPoint==None:dfltStartPoint=0    #clean
        end=dfltEndPoint
        for item in itemsList:
            #skip items if some given
            if skipNameList != None and item.pathName in skipNameList: continue

            if end==None:end= item.duration
            elif end<0: end=item.duration+end
        #iteration play-selection loop
            replay=True
            while replay:
                item.play(" vlc ")
                replay=False    #default 1 play
                print("curr cutPoints:\t",_printCutPointsAsInputStr(item.cutPoints))
                #Prompt String
                vidDurStr="duration "+str(item.duration)
                cmd=input("Add Vid with "+vidDurStr+" to targets?? ( [Y] || SKIP || QUIT || REPLAY ) [start XSECX] [end XSECX] [hole XSEC_HOLESTART XSEC_HOLEEND ] \t\t")
                if "REPLAY" in cmd.upper(): replay=True
            if "SKIP" in cmd.upper(): 
                skipList.append(item)
                continue
            if "Q" in cmd.upper(): return selection,skipList
            fields=cmd.split()
            segmentationPoints=list()           #new segmentation points for the vid to append to the current one
            try:
                for f in range(len(fields)):
                    #parse cmd fields
                    if "start" in fields[f].lower():
                            segmentationPoints.append([parseTimeOffset(fields[f+1]),end])    #allocate seg with given start and default end time 
                    if "end" in fields[f].lower(): segmentationPoints[-1][1]=parseTimeOffset(fields[f+1]) #override last (dflt)  seg end time
                    if "hole" in fields[f].lower(): #dig hole in the last seg -> new 2 seg
                            holeStart,holeEnd=parseTimeOffset(fields[f+1]),parseTimeOffset(fields[f+2])
                            lastSeg=[dfltStartPoint,end]
                            if len(segmentationPoints)>0:lastSeg=segmentationPoints.pop() #remove last segment,if exist, because is going to be cutted
                            #resulting segment from the hole splitting 
                            hseg0,hseg1=[lastSeg[0],holeStart],[holeEnd,lastSeg[1]] #split the last seg in 2
                            segmentationPoints.append(hseg0)
                            segmentationPoints.append(hseg1)
            except Exception as e:  print("invalid cut cmd: ",fields,"\t\t",e)
            #extend current segmentation point with the new given
            item.cutPoints.extend(segmentationPoints) 
            print(item.cutPoints)
            selection.append(item)
        return selection,skipList

def SerializeSelectionSegments(selectedItems,filename=None,append=False):
        """
            trivial serialization given selectedItems in json using __dict__
            if filename given output will be written to file
            if appendToFilename, new selectedItems will be appended to the previous in filename as a json list
            return serialized json string
        """
        outList=list()
        for i in selectedItems: outList.append(i.__dict__)
        if append:
                try:
                    f=open(filename,"r+")
                    prevItems=load(f)
                    outList.extend(prevItems)
                except: append=False
        serialization=dumps(outList,indent=2)
        if filename!=None:
                if not append:f=open(filename,"w")
                f.seek(0)
                f.write(serialization)
        return serialization
def DeserializeSelectionSegments(serializedItemsStr):

    """ deserialize json list of MultimediaItem.__dict__ into list of multimedia items"""
    deserialized=loads(serializedItemsStr)
    out=list()
    for i in deserialized:      out.append(MultimediaItem("").fromJson(i))
    print("deserialized: ",len(out)," items")
    return out

MODE_ABSTIME="MODE_ABSTIME"   #time points specified as num of second
MODE_DURATION="MODE_DURATION" #time identified as floating point in (0,1) as a proportion of the full time of the mItem
SegGenOptionsDflt={"segsLenSecMin":None,"segsLenSecMax":None,"maxSegN":1,"minStartConstr":0,"maxEndConstr":None,"mode":MODE_ABSTIME }
#python3 -c from MultimediaManagementSys import *; SegGenOptionsDflt['maxEndConstr']=-5;GenPlayIterativeScript(DeserializeSelectionSegments(open('selection.list').read()),outFilePath='selectionPlaySegs.sh')

def GenPlayIterativeScript(items, baseCmd="ffplay -autoexit ",segGenConfig=SegGenOptionsDflt ,outFilePath=None):
        """generate a bash script to play all items selected segments
           if no segmenet embedded inside MultimediaItem -> play the whole video
           UC review a serialized selection file
        """
        outLines=list()
        j=0
        startConstr=segGenConfig["minStartConstr"]
        endConstr=segGenConfig["maxEndConstr"]
        for i in items:
                if i.cutPoints!=list():
                        for s in i.cutPoints:
                                playCmd=baseCmd
                                playCmd+=" -ss "+str(s[0])
                                #set segEndTime default overridable by nn None seg end
                                end= endConstr
                                if s[1]!=None: end =s[1]
                                if end<=0:end+=i.duration
                                t=end-s[0]                       #compute end with duration from seeked start
                                playCmd+=" -t "+str(t)
                                playCmd+=" -window_title "+str(j)
                                playCmd+=" '"+i.pathName+"'\n"
                                outLines.append(playCmd)
                                j+=1
                else:   #no segs defined for current item
                        playCmd = baseCmd + " -window_title " + str(j) + " '" + i.pathName+"'\n"
                        outLines.append(playCmd)
                        j+=1

        if outFilePath!=None:
                fp=open(outFilePath,"w")
                fp.writelines(outLines)
                fp.close()
        else: print(outLines)
        return outLines

def GenTrimReencodinglessScriptFFmpeg(items,accurateSeek=False,outFname=None):
    """ generate a bash script to trim items by their embedded cutpoints
        video cut will be done with ffmpeg -ss -to -c copy (reencodingless video/audio out) -avoid_negative_ts 1 (ts back to 0 in cutted)
        video segements cutted will be written in the same path of source items with appended .1 .2 ... .numOfSegments
        if accurateSeek given True will be seeked as ffmpeg output option-> -i inFilePath before -ss,-to
        if outFname given, the script will be written in that path, otherwise printed to stdout
    """
    outLines=list()
    outLines.append("FFMPEG=ffmpeg #set custom ffmpeg path here")
    for i in items:
        cutPointsNum=len(i.cutPoints)
        if cutPointsNum==0: continue    #skip items without segments  -> no trimming required
        outLines.append("#rm "+i.pathName+"\n") #commented remove cmd for currnt vid
        ffmpegInputPath=" -i "+i.pathName
        #for each segments embedded generate ffmpeg -ss -to -c copy ...
        for s in range(cutPointsNum):
            seg=i.cutPoints[s]
            trimSegCmd="eval $FFMPEG "
            if accurateSeek:trimSegCmd+=ffmpegInputPath
            trimSegCmd+=" -ss " +str(seg[0])
            if seg[1]!=None: trimSegCmd+=" -to "+ str(seg[1])
            if not accurateSeek: trimSegCmd+=ffmpegInputPath    #seek as output option
            trimSegCmd+=" -c copy -avoid_negative_ts 1 "
            trimSegCmd+=i.pathName+"."+str(s)+".mp4"               #progressive suffix for segments to generate
            outLines.append(trimSegCmd+"\n")
    if outFname!=None:
        fp=open(outFname,"w")
        fp.writelines(outLines)
        fp.close()
    else:   print(outLines)

def argParseMinimal(args):
    #minimal arg parse use to parse optional args
    parser=ArgumentParser(description=__doc__+'Magment of multimedia clips along with their metadata and tumbnails with a minimal GUI')
    parser.add_argument("pathStart",type=str,help="path to start recursive search of vids")
    parser.add_argument("--selectionMode",type=str,default="TUMBNAIL_GRID",choices=["TUMBNAIL_GRID","VIDEO_TRIM_SELECTION"],help="Operating mode, TUMBNAIL_GRID(dflt): select videos with a GUI grid view of tumbnails, VIDEO_TRIM_SELECTION: select videos and segments to trim in videos with a loop of play and cmd promt")
    parser.add_argument("--videoTrimOldSelectionFile",type=str,default=None,help="ols json serialized selection file to deserialize and append to current new selection, require selectionMode:VIDEO_TRIM_SELECTION")
    parser.add_argument("--videoTrimSelectionStartTime",type=int,default=None,help="default start time for the selected vid3eo in VIDEO_TRIM_SELECTION operating Mode")
    parser.add_argument("--videoTrimSelectionEndTime",type=int,default=None,help="default end time for the selected vid3eo in VIDEO_TRIM_SELECTION operating Mode, if negative added to the end of current vid in selection...")
    parser.add_argument("--videoTrimSelectionLog",type=int,default=0,choices=[0,1,2],help="logging mode of VIDEO_TRIM_SELECTION mode: 0 (dflt) json serialization of selected file with embeddd cut points, 1 bash ffmpeg trim script with -ss -to -c: copy -avoid_negative_ts (commented rm source files lines ), 2 both")
    parser.add_argument("--mode",type=str,default="GROUP",choices=["ALL","GROUP"],help="Mode of View, either ALL -> show all, Groups show a init screen to select the group of items to show, used defined group function")
    parser.add_argument("--grouppingRule",type=str,default=ffmpegConcatDemuxerGroupping.__name__,choices=list(GrouppingFunctions.keys()),help="groupping mode of items")
    parser.add_argument("--itemsSorting",type=str,default="shuffle",choices=["shuffle","size","duration","nameID"],help="how sort items in the GUI when showed the tumbnails ")
    nsArgParsed = parser.parse_args(args)
    nsArgParsed.grouppingRule=GrouppingFunctions[nsArgParsed.grouppingRule]
    return nsArgParsed

def multimediaItemsSorter(itemsSrc,sortMethod):
    if sortMethod=="duration":            itemsSrc.sort(key=lambda x:float(x.duration), reverse=True)
    elif sortMethod=="size":              itemsSrc.sort(key=lambda x:int(x.sizeB), reverse=True)
    elif sortMethod=="sizeName":          itemsSrc.sort(key=lambda x:(x.nameID,int(x.sizeB)), reverse=True)
    elif sortMethod=="nameID":            itemsSrc.sort(key=lambda x:x.nameID )
    elif sortMethod=="shuffle":           shuffle(itemsSrc)
    else:                           print("not founded sorting method")

#VIDEO_TRIM_SELECTION mode out filenames
SELECTION_FILE="selection.list"
TRIM_RM_SCRIPT="trimReencodingless.sh"
if __name__=="__main__":
        nsArgParsed = argParseMinimal(argv[1:])
        items = GetItems(nsArgParsed.pathStart)
        if nsArgParsed.mode=="GROUP":  groups=GetGroups(items,grouppingRule=nsArgParsed.grouppingRule)
        else: items=list(items.values()) #extract the multimedia items list from if grouppings not required
        if nsArgParsed.selectionMode=="TUMBNAIL_GRID":   #sorting hardcoded TODO partial arg pass
            if DISABLE_GUI: raise Exception("unable to start tumbnails grid with tkinter, enable GUI with enviorn variable DISABLE_GUI=True")
            if nsArgParsed.mode=="GROUP":
                guiMinimalStartGroupsMode(groupsStart=groups)
            elif nsArgParsed.mode=="ALL":
                itemsGridViewStart(list(items.values()))
        else:   # VIDEO_TRIM_SELECTION
            if nsArgParsed.mode=="GROUP":
                if not DISABLE_GUI: items=guiMinimalStartGroupsMode(grouppings,trgtAction=SelectWholeGroup,groupsStart=groups)
                else: items=selectGroupTextMode(groups)
            if nsArgParsed.itemsSorting!=None:  multimediaItemsSorter(items,nsArgParsed.itemsSorting)   #sort items with the target method
            skipOldNames,oldSelection=None,list()
            if nsArgParsed.videoTrimOldSelectionFile!=None: #extend current new selection with the old one
                oldSelection=DeserializeSelectionSegments(open(nsArgParsed.videoTrimOldSelectionFile).read())
                skipOldNames=[item.pathName for item in oldSelection]
            selected,skipped=SelectItemPlay(items,skipNameList=skipOldNames,dfltStartPoint=nsArgParsed.videoTrimSelectionStartTime,dfltEndPoint=nsArgParsed.videoTrimSelectionEndTime)
            print("selected: ",selected,"num",len(selected))
            selected.extend(oldSelection)
            logging=nsArgParsed.videoTrimSelectionLog
            if logging==0 or logging==2: SerializeSelectionSegments(selected,SELECTION_FILE,True)
            if logging==1 or logging==2: GenTrimReencodinglessScriptFFmpeg(selected,outFname=TRIM_RM_SCRIPT)
