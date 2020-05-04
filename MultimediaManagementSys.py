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
#!/usr/bin/env python2.7
#Multimedia management system
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
MultimediaObj __str__ output mode:
    METADATA_VIDEO
    REAL_PATH
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
DISABLE_GUI=False
if "DISABLE_GUI" in environ and "T" in environ["DISABLE_GUI"].upper():DISABLE_GUI=True
if not DISABLE_GUI:
    from GUI import *
    import argparse


#################       MULTIMEDIA ITEM OBJ STR OUTPUT OPTION SET BY ENV VARS  #############################
verbose=environ.get("VERBOSE")
VERBOSE=verbose!=None and "T" in verbose.upper()

metadata=environ.get("METADATA_VIDEO")
METADATA=metadata!=None and "T" in metadata.upper()

realPath=environ.get("REAL_PATH")
REAL_PATH=realPath!=None and "T" in realPath.upper()
##### ENV VAR SET
SELECTION_LOGFILE="selected.list"
if environ.get("SELECTION_LOGFILE")!=None: SELECTION_LOGFILE=environ["SELECTION_LOGFILE"]
NameIdFirstDot=True
if environ.get("NameIdFirstDot")!=None and "F" in environ["NameIdFirstDot"].upper(): NameIdFirstDot=False
FORCE_METADATA_GEN=True
if environ.get("FORCE_METADATA_GEN")!=None and "F" in environ["FORCE_METADATA_GEN"].upper(): FORCE_METADATA_GEN=False

############################################### Items Groupping Functions       #######################################
ffprobeComputeResolutionSize=lambda itemStreamList: int(itemStreamList[0]["width"])*int(itemStreamList[0]["height"])
def ffprobeExtractResolution(item):    return str(item.metadata[0]["width"])+" X "+str(item.metadata[0]["height"])
#label element to group them by metadata s.t. they may be concateneted with the concat demuxer
def ffmpegConcatDemuxerGroupping(item):     return GroupByMetadataValuesFlexible(item,["duration", "bit_rate", "nb_frames", "tags", "disposition", "avg_frame_rate", "color"],True,True)
GrouppingFunctions={ f.__name__ : f for f in [ffprobeExtractResolution,ffmpegConcatDemuxerGroupping]}


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

sizeBatching=lambda item,groupByteSize=(100*(2**20)): str(groupByteSize/2**20)+"MB_Group:\t"+ str(item.sizeB // groupByteSize)        #dflt group by size in batch of 500MB each
durationBatching=lambda item,groupTime=5*60: str(groupTime/60)+"Min_Group:\t"+str(item.duration // groupTime)                #dflt group by duration in batch of 5 min each
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
        def __str__(self):
                if VERBOSE: return "MultimediaOBJ\tname: "+self.nameID+" path: "+self.pathName+" size: "+str(self.sizeB)\
                                   +" imgPath: "+self.imgPath+" metadata: "+str(self.metadata)+"\n"
                elif METADATA: return self.nameID+str(self.metadata["streams"][0])
                elif REAL_PATH: return self.pathName
                #dflt ret basic infos
                return "MultimediaOBJ\t  path: "+self.pathName+" imgPath: "+self.imgPath
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
                out=Popen(cmd.split(),stderr=DEVNULL,stdout=DEVNULL)
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
        return list of Multimedia Obj items from current dir content
        """
        i=0
        for root, directories, filenames in walk(rootPathStr,followlinks=True):
                #print(root,"\t",directories,"\t",filenames)
                #pathName=path.join(path.abspath(root),filename)
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
                        #different cases on file in processing img,metadata,
                        #set needed field in accord on file in processing
                        fpath=path.join(path.abspath(root),filename)
                        if IMG_TUMBRL_EXTENSION in extension:
                                item.imgPath=fpath
                        elif METADATA_EXTENSION in extension:
                                try:
                                    item.sizeB,item.metadata,item.duration=parseMultimMetadata(fpath) #skip bad/not fully formatted jsons
                                    item.metadataPath=fpath
                                except:print("badJsonFormat at ",fpath)
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
                    except: print("BAD VID",i)

        return multimediaItems

GetItemsListRecurisve=lambda startPath=".":list(GetItems(".").values())
def GetGroups(srcItems=None,grouppingRule=ffmpegConcatDemuxerGroupping,startSearch="."):
        """
        group items in a dict by a custom rule
        :param srcItems:  multimedia items to group
        :param grouppingRule: function multimediaItem->label (immutable key for groups dict)
        :return: dict: groupKey->itemsList groupped
        """
        groups=dict()   #groupKey->itemList
        if srcItems==None:  srcItems=GetItems(startSearch)
        for item in FilterItems(srcItems.values()):
                try:
                        itemKeyGroup=grouppingRule(item)
                        if groups.get(itemKeyGroup) == None: groups[itemKeyGroup] = list()
                        groups[itemKeyGroup].append(item)
                except Exception as e:
                    itemKeyGroup="OTHERS"
                    print(e,"\tnoComputableGroupKey at ",item.nameID)
                    continue
        return groups
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
def _printCutPointsAsInputStr(cutPoints):       #print cutPoints as input string of SelectionItemPlay
        outStr=""
        for seg in cutPoints:
                start,end=seg[0],seg[1]
                outStr="start "+str(start)
                if end!=None:outStr+="end "+str(end)
        return outStr

def SelectItemPlay(itemsList,skipNameList=None,dfltStartPoint=None,dfltEndPoint=None):
        """
        iterativelly play items in supporting video selection and after will be prompted cmds
        for selection/replay video and segment cut times to add for the item
        segmentation times, if given will be embedded in cutPoints as a list of [[start,end],...]
        segmentation times can be specified with the extra hole, that will split the last seg (or the whole video) into 2 segs where the whole range times is removed
        returned this selection when no more video in itemsList or quitted inputted
        :param itemsList: items to play and cut with the promt cmd
        :param skipNameList: item pathnames list not to play
        :param dfltStartPoint: default start time for the first segment
        :param dfltEndPoint:    default end time for the last segmenet (if negative added to item duration
        :return: list of selected itmes (along with embeded cut points)
        """
        selection=list()
        skipList=list()
        if dfltStartPoint==None:dfltStartPoint=0
        for item in itemsList:
            #skip items if some given
            if skipNameList != None and item.pathName in skipNameList: continue
            item.play()
            replay=True
            while replay:
                replay=False    #default 1 play
                print("curr cutPoints:\t",_printCutPointsAsInputStr(item.cutPoints))
                include=input("Add vid to targets?? (Y || SKIP || QUIT || REPLAY ) [start XSECX] [end XSECX] ?\t\t")
                if "REPLAY" in include.upper():
                    item.play()
                    replay=True
            if "SKIP" in include.upper(): 
                skipList.append(item)
                continue
            if "Q" in include.upper(): return selection
            fields=include.split()
            # append with selected item eventual segmentation points as [startSec,endSec] parsed from input string
            #default start/end point for current segment
            end=dfltEndPoint
            if end==None:end=item.duration
            elif end<0: end=item.duration+end
            segmentationPointsOverride=list()
            for f in range(len(fields)):
                #basic parser of cut point, start alloc a new seg with deflt end,end ovverride this dflt end,
                #hole split the last  seg or the whole video in 2 seg where the hole start<--to-->end times are removed
                if "start" in fields[f].lower():
                        segmentationPointsOverride.append([float(fields[f+1]),end])    #allocate also default end time not specified for this seg
                if "end" in fields[f].lower(): segmentationPointsOverride[-1][1]=float(fields[f+1])
                if "hole" in fields[f].lower(): #dig hole in the last seg -> new 2 seg
                        holeStart,holeEnd=float(fields[f+1]),float(fields[f+2])
                        lastSeg=[dfltStartPoint,end]
                        if len(segmentationPointsOverride)>0:
                                lastSeg=segmentationPointsOverride[-1]
                                segmentationPointsOverride.pop(-1)      #will be replaced with itself splitted
                        hseg0,hseg1=[lastSeg[0],holeStart],[holeEnd,lastSeg[1]] #split the last seg in 2
                        segmentationPointsOverride.append(hseg0)
                        segmentationPointsOverride.append(hseg1)

            item.cutPoints.extend(segmentationPointsOverride) #append the segment times given to the one maybe already specified for the item
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
        outLines=list()
        for i in selectedItems: outLines.append(i.__dict__)
        # out="\n".join(outLines)
        outList=outLines
        if append:
                try:
                    f=open(filename,"r+")
                    prevItems=load(f)
                    outLines.extend(prevItems)
                except: append=False
        serialization=dumps(outList)
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
        return outLines

def IntersectItemsAndFilenames(items,filenames):
        #intersect itmes.nameID with list of fnames in filenames
        intersectedItems=list()
        for fn in filenames:
                for i in items:
                        if i.nameID in fn:	  #matching remoteFilename == item i
                                intersectedItems.append(i)
        return intersectedItems

printList = lambda l: list(map(print, l))  #basic print list, return [None,...]
def argParseMinimal(args):
    #minimal arg parse use to parse optional args
    parser=argparse.ArgumentParser(description=__doc__+'Magment of multimedia clips along with their metadata and tumbnails with a minimal GUI')
    parser.add_argument("--pathStart",type=str,default="/home/andysnake/DATA2/all/all",help="path to start recursive search of vids")
    parser.add_argument("--mode",type=str,default="GROUP",choices=["ALL","GROUP"],help="Mode of View, either ALL -> show all, Groups show a init screen to select the group of items to show, used defined group function")
    parser.add_argument("--grouppingRule",type=str,default=ffmpegConcatDemuxerGroupping.__name__,choices=list(GrouppingFunctions.keys()),help="groupping mode of items")
    parser.add_argument("--itemsSorting",type=str,default="shuffle",choices=["shuffle","size","duration"],help="how sort items in the GUI when showed the tumbnails ")
    nsArgParsed = parser.parse_args(args)
    nsArgParsed.grouppingRule=GrouppingFunctions[nsArgParsed.grouppingRule]
    return nsArgParsed

if __name__=="__main__":
        nsArgParsed = argParseMinimal(argv[1:])
        items = GetItems(nsArgParsed.pathStart)
        if nsArgParsed.mode=="ALL":
            itemsGridViewStart(list(items.values()))
        elif nsArgParsed.mode=="GROUP":
            groups=GetGroups(items,grouppingRule=nsArgParsed.grouppingRule)
            guiMinimalStartGroupsMode(groupsStart=groups)
